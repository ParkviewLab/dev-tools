#!/usr/bin/env python3
"""Second prototype of the changelog list rule of "One changelog generator".

Usage:
    proposed_list2.py <repo_dir> <prev_tag or -> <tag> <prs.json> [--markdown]

<prs.json> is the output of
    gh pr list -R <owner>/<repo> --state merged --limit 1000 \
        --json number,title,body,mergeCommit,baseRefName,headRefName,mergedAt

Prints JSON: the listed pull requests by group, the direct commits, every
commit recognised as bookkeeping with the reason, the pull requests left out
(carriers, already shipped), the commits absorbed into real merges, and
warnings.  With --markdown, prints the rendered section instead.

Rules implemented (numbering as in the design text):
  R1 range, R2 pull-request commits (a squash, b real merge, c cherry-pick),
  R3 carrier pull requests, R4 once only, R5 direct commits and bookkeeping,
  R6 groups, R7 breaking changes.
Implementation decisions are marked "DECISION" in the comments; each is also
reported in measure.md.

What needs the GitHub API (the prs.json file): R3 (base and head branch of a
pull request), R6 for a merge left at GitHub's default title (the title
recorded on the pull request) and R7 (the pull request body).  Everything
else works from git alone: R1, R2, R4, R5 and the rest of R6 and R7.
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import tomllib

GITHUB_EMAIL = "noreply@github.com"
PR_SUFFIX = re.compile(r"\(#(\d+)\)\s*$")
MERGE_DEFAULT = re.compile(r"^Merge pull request #(\d+) from \S+")
PICK_TRAILER = re.compile(r"\(cherry picked from commit ([0-9a-f]{7,40})\)")
# DECISION: Conventional Commit header = type, optional (scope), optional !,
# a colon and at least one blank.  The type is matched case-insensitively
# (the Conventional Commits specification says types are not case sensitive).
CONVENTIONAL = re.compile(
    r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^()\r\n]*)\))?(?P<bang>!)?:[ \t]+(?P<desc>\S.*)$")
BREAKING_LINE = re.compile(r"(?m)^BREAKING[ -]CHANGE:")
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

GROUP_OF_TYPE = {
    "feat": "Features", "fix": "Bug fixes", "perf": "Performance",
    "refactor": "Refactor", "docs": "Docs", "test": "Tests", "revert": "Reverts",
    "build": "Maintenance", "chore": "Maintenance", "ci": "Maintenance", "style": "Maintenance",
}
GROUP_ORDER = ["Breaking changes", "Features", "Bug fixes", "Performance", "Refactor", "Docs",
               "Tests", "Reverts", "Maintenance", "Other changes"]

# Version sources of truth and lockfiles, at the repository root only (DECISION).
SOT_FILES = {"pyproject.toml", "package.json", "Cargo.toml", "VERSION.txt"}
LOCK_FILES = {"uv.lock", "package-lock.json", "Cargo.lock"}
CHANGELOG = "CHANGELOG.md"
VERSION_LINE = re.compile(r'^\s*"?version"?\s*[:=]')


class Git:
    def __init__(self, repo: str):
        self.repo = repo

    def run(self, *args: str, input: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
        p = subprocess.run(["git", "-C", self.repo, *args], input=input, capture_output=True, text=True,
                           errors="replace")
        if check and p.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
        return p

    def out(self, *args: str, input: str | None = None) -> str:
        return self.run(*args, input=input).stdout

    def raw(self, *args: str, input: bytes | None = None) -> bytes:
        """Binary-safe variant, for diffs piped into git patch-id."""
        p = subprocess.run(["git", "-C", self.repo, *args], input=input, capture_output=True)
        if p.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.decode(errors='replace').strip()}")
        return p.stdout

    def show_file(self, rev: str, path: str) -> str | None:
        p = self.run("show", f"{rev}:{path}", check=False)
        return p.stdout if p.returncode == 0 else None


# ---------------------------------------------------------------- history index

class History:
    """Every commit reachable from any ref of the clone (branches, remote-tracking
    branches, tags): 'anywhere in the repository's history' (DECISION)."""

    def __init__(self, git: Git, prs: dict[int, dict]):
        self.git = git
        self.prs = prs
        self.commits: dict[str, dict] = {}
        raw = git.out("log", "--all", "--format=%H%x1f%P%x1f%ce%x1f%cn%x1f%s%x1e")
        for rec in raw.split("\x1e"):
            rec = rec.strip("\n")
            if not rec:
                continue
            sha, parents, ce, cn, subject = rec.split("\x1f", 4)
            self.commits[sha] = {"sha": sha, "parents": parents.split(), "ce": ce, "cn": cn, "subject": subject}
        self._msg: dict[str, str] = {}
        self._pid: dict[str, str | None] = {}
        self._load_patch_ids()
        # GitHub-made commits attributed to a pull request (R2 a and b), anywhere.
        self.github_attr: dict[str, tuple[str, int]] = {}
        for sha, c in self.commits.items():
            a = self._github_attr(c)
            if a:
                self.github_attr[sha] = a
        # R2(c) index: patch-id -> pull requests, over GitHub-made commits of
        # non-carrier pull requests (DECISION: a commit is never taken to be a
        # cherry-pick of a carrier; see measure.md).
        self.pid_index: dict[str, set[int]] = {}
        for sha, (kind, n) in self.github_attr.items():
            if self.is_carrier(n):
                continue
            pid = self.patch_id(sha)
            if pid:
                self.pid_index.setdefault(pid, set()).add(n)

    # -- basic accessors
    def message(self, sha: str) -> str:
        if sha not in self._msg:
            self._msg[sha] = self.git.out("log", "-1", "--format=%B", sha)
        return self._msg[sha]

    def is_github(self, sha: str) -> bool:
        return self.commits[sha]["ce"] == GITHUB_EMAIL

    def is_merge(self, sha: str) -> bool:
        return len(self.commits[sha]["parents"]) >= 2

    def is_carrier(self, n: int) -> bool:
        pr = self.prs.get(n)
        if pr is None:
            return False
        base, head = pr.get("baseRefName") or "", pr.get("headRefName") or ""
        return base == "main" or head in ("main", "develop") or head.startswith("back-merge")

    # -- R2(a) and R2(b)
    def _github_attr(self, c: dict) -> tuple[str, int] | None:
        if c["ce"] != GITHUB_EMAIL:
            return None
        s = c["subject"]
        if len(c["parents"]) >= 2:
            m = MERGE_DEFAULT.match(s)
            if m:
                return ("merge-default-title", int(m.group(1)))
            m = PR_SUFFIX.search(s)
            if m:
                return ("merge-titled", int(m.group(1)))
            return None
        m = PR_SUFFIX.search(s)
        if m:
            return ("squash", int(m.group(1)))
        return None

    # -- patch ids
    def _load_patch_ids(self) -> None:
        """patch-id --stable of every non-merge commit, from one log -p pass."""
        log = self.git.raw("log", "--all", "--no-merges", "--no-renames", "-p", "--format=commit %H")
        out = self.git.raw("patch-id", "--stable", input=log).decode()
        for line in out.splitlines():
            pid, sha = line.split()
            self._pid[sha] = pid

    def patch_id(self, sha: str) -> str | None:
        """Non-merge: the commit's own diff.  Merge: DECISION, the diff against its
        first parent (git diff M^1 M), which is what `git cherry-pick -m 1 M` applies."""
        if sha in self._pid:
            return self._pid[sha]
        if self.is_merge(sha):
            diff = self.git.raw("diff", "--no-renames", f"{sha}^1", sha)
            out = self.git.raw("patch-id", "--stable", input=diff).decode() if diff else ""
            self._pid[sha] = out.split()[0] if out.strip() else None
        else:
            self._pid[sha] = None  # empty commit: no patch-id
        return self._pid[sha]

    # -- attribution of one commit to a pull request under R2 (a, b, c)
    def attribute(self, sha: str) -> tuple[str, int, str | None] | None:
        """Returns (how, N, original) or None.  'original' is the GitHub-made
        commit a cherry-pick copies."""
        if sha in self.github_attr:
            kind, n = self.github_attr[sha]
            return (kind, n, None)
        if self.is_github(sha) and self.is_merge(sha):
            return None
        if self.is_merge(sha):
            return None  # DECISION: a merge not made by GitHub is never a cherry-pick
        # R2(c), trailer first (DECISION: explicit trailer before patch-id)
        for x in PICK_TRAILER.findall(self.message(sha)):
            p = self.git.run("rev-parse", "--verify", "--quiet", f"{x}^{{commit}}", check=False)
            full = p.stdout.strip()
            if p.returncode == 0 and full in self.github_attr:
                n = self.github_attr[full][1]
                if not self.is_carrier(n):
                    return ("cherry-pick (trailer)", n, full)
        pid = self.patch_id(sha)
        if pid and pid in self.pid_index:
            ns = sorted(self.pid_index[pid])
            n = ns[0]  # DECISION: if several pull requests share the patch-id, the lowest number
            orig = next(s for s, (k, m) in self.github_attr.items() if m == n and self.patch_id(s) == pid)
            return ("cherry-pick (patch-id)", n, orig)
        return None


# ---------------------------------------------------------------- bookkeeping (R5)

def _drop_version_pyproject(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    if isinstance(d.get("project"), dict):
        d["project"].pop("version", None)
    return d


def _drop_version_cargo(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    if isinstance(d.get("package"), dict):
        d["package"].pop("version", None)
    return d


def _drop_version_package_json(d: dict) -> dict:
    d = dict(d)
    d.pop("version", None)
    return d


def _drop_version_package_lock(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    d.pop("version", None)
    pk = d.get("packages")
    if isinstance(pk, dict) and isinstance(pk.get(""), dict):
        pk[""].pop("version", None)
    return d


def _own_lock_entry(pkg: dict, own_names: set[str]) -> bool:
    src = pkg.get("source")
    if isinstance(src, dict) and (src.get("editable") == "." or src.get("virtual") == "."):
        return True  # uv.lock: the project itself
    return _norm(pkg.get("name", "")) in own_names


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _drop_version_toml_lock(d: dict, own_names: set[str]) -> dict:
    d = json.loads(json.dumps(d, default=str))
    for pkg in d.get("package", []) or []:
        if isinstance(pkg, dict) and _own_lock_entry(pkg, own_names):
            pkg.pop("version", None)
    return d


def _text_changes_only_version_lines(old: str, new: str) -> bool:
    ol, nl = old.splitlines(), new.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ol, b=nl, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        for line in ol[i1:i2] + nl[j1:j2]:
            if not VERSION_LINE.match(line):
                return False
    return True


def version_only_change(git: Git, parent: str, sha: str, path: str) -> tuple[bool, str]:
    old, new = git.show_file(parent, path), git.show_file(sha, path)
    if old is None or new is None:
        return False, f"{path} added or removed"
    if path == "VERSION.txt":
        ok = bool(re.fullmatch(r"\s*\S+\s*", old)) and bool(re.fullmatch(r"\s*\S+\s*", new))
        return ok, f"VERSION.txt {old.strip()} -> {new.strip()}" if ok else "VERSION.txt not a single value"
    if not _text_changes_only_version_lines(old, new):
        return False, f"{path}: a changed line is not a version line"
    try:
        if path == "pyproject.toml":
            a, b = tomllib.loads(old), tomllib.loads(new)
            same = _drop_version_pyproject(a) == _drop_version_pyproject(b)
            va, vb = a.get("project", {}).get("version"), b.get("project", {}).get("version")
        elif path == "Cargo.toml":
            a, b = tomllib.loads(old), tomllib.loads(new)
            same = _drop_version_cargo(a) == _drop_version_cargo(b)
            va, vb = a.get("package", {}).get("version"), b.get("package", {}).get("version")
        elif path == "package.json":
            a, b = json.loads(old), json.loads(new)
            same = _drop_version_package_json(a) == _drop_version_package_json(b)
            va, vb = a.get("version"), b.get("version")
        elif path == "package-lock.json":
            a, b = json.loads(old), json.loads(new)
            same = _drop_version_package_lock(a) == _drop_version_package_lock(b)
            va, vb = a.get("version"), b.get("version")
        elif path in ("uv.lock", "Cargo.lock"):
            own: set[str] = set()
            manifest = "pyproject.toml" if path == "uv.lock" else "Cargo.toml"
            for rev in (parent, sha):
                t = git.show_file(rev, manifest)
                if t:
                    try:
                        m = tomllib.loads(t)
                        nm = (m.get("project") or m.get("package") or {}).get("name")
                        if nm:
                            own.add(_norm(nm))
                    except tomllib.TOMLDecodeError:
                        pass
            a, b = tomllib.loads(old), tomllib.loads(new)
            same = _drop_version_toml_lock(a, own) == _drop_version_toml_lock(b, own)
            va = vb = "own entry"
        else:
            return False, f"{path} is not a version file"
    except (tomllib.TOMLDecodeError, json.JSONDecodeError) as e:
        return False, f"{path} does not parse: {e}"
    if not same:
        return False, f"{path}: a value other than the project's own version changed"
    return True, f"{path} {va} -> {vb}" if path not in ("uv.lock", "Cargo.lock") else f"{path} own entry"


def bookkeeping_nonmerge(git: Git, sha: str, parents: list[str]) -> tuple[str | None, str]:
    """R5 (i) and (ii).  Returns (reason or None, detail)."""
    if parents:
        ns = git.out("diff-tree", "-r", "--no-renames", "--name-status", parents[0], sha)
        parent = parents[0]
    else:
        ns = git.out("diff-tree", "-r", "--root", "--no-renames", "--name-status", sha)
        parent = None
    changes = [ln.split("\t", 1) for ln in ns.splitlines() if "\t" in ln]
    if not changes:
        return None, "empty commit"
    other = [(st, p) for st, p in changes if p != CHANGELOG]
    if not other:
        return "changelog-only", "changes only CHANGELOG.md"
    if parent is None:
        return None, "root commit"
    details = []
    for st, p in other:
        if st != "M" or p not in SOT_FILES | LOCK_FILES:
            return None, f"changes {p}"
        ok, d = version_only_change(git, parent, sha, p)
        if not ok:
            return None, d
        details.append(d)
    if not any(p in SOT_FILES for _, p in other) and not any(p in LOCK_FILES for _, p in other):
        return None, "no version file"
    return "version-only", "; ".join(details) + ("; CHANGELOG.md" if len(other) < len(changes) else "")


def merge_against_automatic(git: Git, sha: str, parents: list[str]) -> tuple[bool, str]:
    """R5 (iii): does the merge's tree equal the automatic merge of its parents?"""
    if len(parents) != 2:
        return False, f"{len(parents)}-parent merge: no automatic merge to compare with"
    p = git.run("merge-tree", "--write-tree", "--no-messages", "--name-only", parents[0], parents[1], check=False)
    lines = p.stdout.splitlines()
    auto = lines[0].strip() if lines else ""
    conflicted = p.returncode == 1
    tree = git.out("rev-parse", f"{sha}^{{tree}}").strip()
    if auto == tree and not conflicted:
        return True, "tree equals the automatic merge of its parents"
    stat = git.out("diff", "--no-renames", "--stat=200", auto, tree).strip() if auto else ""
    files = [ln for ln in lines[1:] if ln.strip()]
    what = ("automatic merge conflicts in " + ", ".join(sorted(set(files))) + "; ") if conflicted else ""
    return False, what + "differs from the automatic merge: " + (stat.replace("\n", " | ") or "(no textual diff)")


# ---------------------------------------------------------------- the rule

def conventional(title: str) -> dict:
    m = CONVENTIONAL.match(title.strip())
    if not m:
        return {"type": None, "scope": None, "bang": False, "desc": title.strip()}
    return {"type": m.group("type").lower(), "scope": m.group("scope"), "bang": bool(m.group("bang")),
            "desc": m.group("desc").strip()}


def strip_suffix(subject: str) -> str:
    return PR_SUFFIX.sub("", subject).rstrip()


def vkey(tag: str) -> tuple[int, int, int]:
    return tuple(map(int, TAG.match(tag).groups()))  # type: ignore[union-attr]


def build(repo: str, prev: str | None, tag: str, prs_list: list[dict]) -> dict:
    git = Git(repo)
    prs = {p["number"]: p for p in prs_list}
    H = History(git, prs)
    warnings: list[str] = []

    # R1
    rng = git.out("rev-list", "--topo-order", "--reverse", f"{prev}..{tag}" if prev else tag).split()
    in_range = set(rng)

    # Real merges of listed (non-carrier) pull requests in the range: their own commits.
    absorbed: dict[str, int] = {}
    own_commits: dict[int, list[str]] = {}
    for sha in rng:
        a = H.github_attr.get(sha)
        if not a or not a[0].startswith("merge"):
            continue
        n = a[1]
        if H.is_carrier(n):
            continue
        ps = H.commits[sha]["parents"]
        own = git.out("rev-list", *ps[1:], f"^{ps[0]}").split()
        for c in own:
            nested = H.github_attr.get(c)
            if c in in_range and not (nested and not H.is_carrier(nested[1])):
                # DECISION: a GitHub-made commit of another, non-carrier pull request
                # inside this pull request's own commits is still that pull request;
                # everything else inside (branch commits, local merges, carrier
                # merges) belongs to this pull request and is never listed on its own.
                absorbed.setdefault(c, n)
        own_commits[n] = [c for c in own if c in in_range]

    listed: dict[int, dict] = {}
    direct: list[dict] = []
    bookkeeping: list[dict] = []
    carriers: dict[int, dict] = {}
    suffix_not_believed: list[dict] = []

    def add_pr(n: int, sha: str, how: str, original: str | None) -> None:
        e = listed.setdefault(n, {"number": n, "commits": [], "via": [], "_full": [], "_orig": []})
        e["commits"].append(sha[:10])
        e["via"].append(how)
        e["_full"].append(sha)
        if original:
            e.setdefault("originals", []).append(original[:10])
            e["_orig"].append(original)
        if not how.startswith("cherry-pick"):
            recorded = ((prs.get(n) or {}).get("mergeCommit") or {}).get("oid")
            if recorded and recorded != sha:
                warnings.append(f"{sha[:10]} claims #{n}, but GitHub records {recorded[:10]} as its merge commit")

    for sha in rng:
        c = H.commits[sha]
        subj = c["subject"]
        if sha in absorbed:
            continue
        att = H.attribute(sha)
        if att:
            how, n, orig = att
            if H.is_carrier(n):
                carriers.setdefault(n, {"number": n, "commit": sha[:10], "how": how,
                                        "title": prs.get(n, {}).get("title")})
                if how == "squash":
                    warnings.append(f"{sha[:10]} is a squash merge of carrier pull request #{n}; the "
                                    f"changes it carries cannot be identified from the range")
                    continue
                # R3: a carrier merge is examined as if it were not there: the merge
                # commit itself goes to R5 (iii) like any other merge (DECISION).
                ok, why = merge_against_automatic(git, sha, c["parents"])
                if ok:
                    bookkeeping.append({"sha": sha[:10], "subject": subj, "reason": f"carrier #{n} merge: {why}"})
                else:
                    direct.append({"sha": sha[:10], "subject": subj, "merge": True, "note": why})
                    warnings.append(f"{sha[:10]} carrier #{n} merge {why}")
                continue
            if n not in prs:
                warnings.append(f"{sha[:10]} is attributed to #{n}, which is not in the pull-request data")
            add_pr(n, sha, how, orig)
            continue
        if len(c["parents"]) >= 2:
            ok, why = merge_against_automatic(git, sha, c["parents"])
            if ok:
                bookkeeping.append({"sha": sha[:10], "subject": subj, "reason": f"merge: {why}"})
            else:
                direct.append({"sha": sha[:10], "subject": subj, "merge": True, "note": why})
                warnings.append(f"{sha[:10]} merge '{subj}' {why}")
            continue
        reason, detail = bookkeeping_nonmerge(git, sha, c["parents"])
        if reason:
            bookkeeping.append({"sha": sha[:10], "subject": subj, "reason": f"{reason}: {detail}"})
            continue
        entry = {"sha": sha[:10], "subject": subj, "merge": False, "note": detail}
        m = PR_SUFFIX.search(subj)
        if m:
            entry["suffix_not_believed"] = int(m.group(1))
            suffix_not_believed.append(entry)
            warnings.append(f"{sha[:10]} ends in (#{m.group(1)}) but is neither made by GitHub nor a "
                            f"cherry-pick of a GitHub-made commit; listed as a direct commit")
        direct.append(entry)

    # R4: pull requests already shipped (a commit attributed to it reachable from prev).
    already: list[dict] = []
    if prev:
        shipped: dict[int, str] = {}
        for sha in git.out("rev-list", prev).split():
            att = H.attribute(sha)
            if att and att[1] not in shipped:
                shipped[att[1]] = f"{sha[:10]} ({att[0]})"
        for n in sorted(listed):
            if n in shipped:
                already.append({"number": n, "evidence": shipped[n], "commits_in_range": listed[n]["commits"]})
        for a in already:
            listed.pop(a["number"])

    # R6 titles and groups, R7 breaking.
    groups: dict[str, list[dict]] = {g: [] for g in GROUP_ORDER}
    for n in sorted(listed):
        e = listed[n]
        pr = prs.get(n, {})
        src_full = next((s for s in e["_full"] if s in H.github_attr), None) or next(iter(e["_orig"]), None)
        title, title_source = None, None
        if src_full:
            kind = H.github_attr[src_full][0]
            if kind == "merge-default-title":
                if pr.get("title"):
                    title, title_source = pr["title"], "pull request (API)"
                else:
                    body = H.message(src_full).split("\n", 1)[1].strip() if "\n" in H.message(src_full) else ""
                    title = body.splitlines()[0] if body else H.commits[src_full]["subject"]
                    title_source = "merge message body (API title unavailable)"
                    warnings.append(f"#{n}: default-title merge and no title in the pull-request data")
            else:
                title, title_source = strip_suffix(H.commits[src_full]["subject"]), f"{kind} commit first line"
        else:
            title, title_source = pr.get("title", ""), "pull request (API)"
        e["title"] = title
        e["title_source"] = title_source
        if pr.get("title") is not None and pr["title"].strip() != title.strip():
            e["api_title"] = pr["title"]
        cc = conventional(title)
        e["type"] = cc["type"]
        # R7: '!' in the title, or a BREAKING CHANGE line in any commit message of the
        # pull request in the range (its squash, merge or pick, and a real merge's own
        # commits: DECISION) or in the pull-request body.
        msgs = [H.message(s) for s in e["_full"]]
        msgs += [H.message(s) for s in own_commits.get(n, [])]
        why = []
        if cc["bang"]:
            why.append("! in title")
        if any(BREAKING_LINE.search(m) for m in msgs):
            why.append("BREAKING CHANGE line in a commit message")
        if BREAKING_LINE.search(pr.get("body") or ""):
            why.append("BREAKING CHANGE line in the pull-request body")
        e["breaking"] = why
        if why:
            g = "Breaking changes"  # DECISION: listed once, under Breaking changes only
        elif cc["type"] in GROUP_OF_TYPE:
            g = GROUP_OF_TYPE[cc["type"]]
        else:
            g = "Other changes"
        e["group"] = g
        e["line"] = (title if g in ("Other changes",) or cc["type"] is None else cc["desc"])
        groups[g].append(e)

    if prev and vkey(tag)[0] > vkey(prev)[0] and not groups["Breaking changes"]:
        warnings.append(f"{tag} is a major version and lists no breaking change")

    for e in listed.values():
        e.pop("_full", None)
        e.pop("_orig", None)
    res = {
        "repo": repo, "prev": prev, "tag": tag,
        "range": f"{prev}..{tag}" if prev else f"{tag} (git rev-list {tag})",
        "commits_in_range": len(rng),
        "listed": sorted(listed),
        "groups": {g: v for g, v in groups.items() if v},
        "direct_commits": direct,
        "bookkeeping": bookkeeping,
        "carriers": sorted(carriers.values(), key=lambda x: x["number"]),
        "already_shipped": already,
        "absorbed": {str(n): [c[:10] for c in cs] for n, cs in sorted(own_commits.items())},
        "suffix_not_believed": suffix_not_believed,
        "warnings": warnings,
    }
    res["section"] = render(res)
    return res


def render(res: dict) -> str:
    parts = []
    for g, items in res["groups"].items():
        lines = [f"- {e['line'][:1].upper()}{e['line'][1:]} (#{e['number']})" for e in items]
        parts.append(f"### {g}\n\n" + "\n".join(lines))
    if res["direct_commits"]:
        parts.append("### Direct commits\n\n" + "\n".join(
            f"- {d['subject']} ({d['sha'][:7]})" for d in res["direct_commits"]))
    return "\n\n".join(parts) if parts else "_No changes._"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 4:
        sys.exit(__doc__)
    repo, prev, tag, prs_path = args
    res = build(repo, None if prev == "-" else prev, tag, json.load(open(prs_path)))
    if "--markdown" in sys.argv:
        print(render(res))
    else:
        print(json.dumps(res, indent=1))
