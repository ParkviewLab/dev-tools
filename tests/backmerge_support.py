# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared fixtures for the tests of back-merge-check, git-back-merge and git-dev-release.

A Sandbox is a temporary directory with its own git configuration and a bin
directory of fakes placed first on PATH: `uv` and `npm` (the two version writers
_sot.sh calls, so the tests need neither installed) and `gh` (a fake GitHub whose
state is a JSON file, with a bare repository standing for origin). The fake `gh`
evaluates `--jq` filters with the system `jq`, which the ubuntu runners and macOS
provide. The scripts run under `bash` from PATH, or the one BACKMERGE_TEST_BASH
names, so the same tests run under macOS's bash 3.2 and the runners' bash 5.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
BASH = os.environ.get("BACKMERGE_TEST_BASH", "bash")

# ---------------------------------------------------------------- version files

def pyproject_text(name: str, version: str) -> str:
    return (
        "[project]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = ["idna"]\n'
        "\n[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )


def uv_lock_text(name: str, version: str, bulk: int = 0) -> str:
    # A dependency's block comes first, so that a version line which is not the
    # project's can be told apart from the project's own. bulk adds that many
    # dependency blocks after the project's, as a real lockfile has: well over a
    # pipe buffer of text after the version line, once bulk is in the thousands.
    return (
        "version = 1\n"
        "revision = 3\n"
        'requires-python = ">=3.11"\n'
        "\n[[package]]\n"
        'name = "idna"\n'
        'version = "3.10"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        "\n[[package]]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        'source = { editable = "." }\n'
        "dependencies = [\n"
        '    { name = "idna" },\n'
        "]\n"
    ) + "".join(
        f'\n[[package]]\nname = "dep-{i:05d}"\nversion = "1.0.{i}"\n'
        'source = { registry = "https://pypi.org/simple" }\n' for i in range(bulk))


def package_json_text(name: str, version: str) -> str:
    return json.dumps({"name": name, "version": version, "private": True,
                       "dependencies": {"left-pad": "^1.3.0"}}, indent=2) + "\n"


def package_lock_text(name: str, version: str, bulk: int = 0) -> str:
    packages = {
        "": {"name": name, "version": version, "dependencies": {"left-pad": "^1.3.0"}},
        "node_modules/left-pad": {"version": "1.3.0",
                                  "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz"},
    }
    for i in range(bulk):
        packages[f"node_modules/dep-{i:05d}"] = {
            "version": f"1.0.{i}", "resolved": f"https://registry.npmjs.org/dep-{i:05d}/-/dep-{i:05d}-1.0.{i}.tgz"}
    return json.dumps({"name": name, "version": version, "lockfileVersion": 3, "requires": True,
                       "packages": packages}, indent=2) + "\n"


def set_pyproject_version(wt: Path, version: str, lock: bool = True) -> None:
    p = wt / "pyproject.toml"
    text = p.read_text()
    name = re.search(r'(?m)^name = "([^"]*)"', text).group(1)
    p.write_text(re.sub(r'(?m)^version = "[^"]*"', f'version = "{version}"', text, count=1))
    if lock and (wt / "uv.lock").exists():
        set_uv_lock_version(wt, name, version)


def set_uv_lock_version(wt: Path, name: str, version: str) -> None:
    lines = (wt / "uv.lock").read_text().splitlines(keepends=True)
    inside = False
    for i, line in enumerate(lines):
        if line.startswith("[[package]]"):
            inside = False
        elif line == f'name = "{name}"\n':
            inside = True
        elif inside and line.startswith('version = "'):
            lines[i] = f'version = "{version}"\n'
            inside = False
    (wt / "uv.lock").write_text("".join(lines))


def set_package_version(wt: Path, version: str, lock: bool = True) -> None:
    pj = wt / "package.json"
    data = json.loads(pj.read_text())
    data["version"] = version
    pj.write_text(json.dumps(data, indent=2) + "\n")
    pl = wt / "package-lock.json"
    if lock and pl.exists():
        data = json.loads(pl.read_text())
        data["version"] = version
        data["packages"][""]["version"] = version
        pl.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------- the fakes

FAKE_UV = r'''#!/usr/bin/env python3
# A fake uv: `uv version <v>` and `uv run --quiet python -c <code>`, all _sot.sh needs.
import os, re, subprocess, sys
a = sys.argv[1:]
if a[:1] == ["version"] and len(a) >= 2:
    v = [x for x in a[1:] if not x.startswith("-")][0]
    text = open("pyproject.toml").read()
    name = re.search(r'(?m)^name = "([^"]*)"', text).group(1)
    open("pyproject.toml", "w").write(re.sub(r'(?m)^version = "[^"]*"', 'version = "%s"' % v, text, count=1))
    if os.path.exists("uv.lock"):
        lines = open("uv.lock").read().splitlines(True); inside = False
        for i, l in enumerate(lines):
            if l.startswith("[[package]]"): inside = False
            elif l == 'name = "%s"\n' % name: inside = True
            elif inside and l.startswith('version = "'): lines[i] = 'version = "%s"\n' % v; inside = False
        open("uv.lock", "w").write("".join(lines))
    sys.exit(0)
if a[:1] == ["run"]:
    rest = [x for x in a[1:] if x != "--quiet"]
    if rest[:1] == ["python"]:
        sys.exit(subprocess.call([sys.executable] + rest[1:]))
sys.stderr.write("fake uv: unsupported %r\n" % a); sys.exit(2)
'''

FAKE_NPM = r'''#!/usr/bin/env python3
# A fake npm: `npm version <v> --no-git-tag-version --allow-same-version`.
import json, os, sys
a = sys.argv[1:]
if a[:1] == ["version"]:
    v = [x for x in a[1:] if not x.startswith("-")][0]
    d = json.load(open("package.json")); d["version"] = v
    open("package.json", "w").write(json.dumps(d, indent=2) + "\n")
    if os.path.exists("package-lock.json"):
        d = json.load(open("package-lock.json")); d["version"] = v; d["packages"][""]["version"] = v
        open("package-lock.json", "w").write(json.dumps(d, indent=2) + "\n")
    sys.exit(0)
sys.stderr.write("fake npm: unsupported %r\n" % a); sys.exit(2)
'''

FAKE_NODE = "#!/bin/sh\nexit 1\n"   # sot_read falls back to python3 for package.json

FAKE_GH = r'''#!/usr/bin/env python3
# A fake gh. Its state is the JSON file FAKE_GH_STATE; origin is the bare
# repository state["origin"]. Every call is logged in state["calls"].
import json, os, subprocess, sys, tempfile, shutil

SP = os.environ["FAKE_GH_STATE"]
st = json.load(open(SP))
argv = sys.argv[1:]
st.setdefault("calls", []).append(argv)

def save():
    json.dump(st, open(SP, "w"), indent=1)

def opt(name, default=None):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) else default
    return default

def emit(value):
    save()
    jq = opt("--jq")
    doc = json.dumps(value)
    if jq is None:
        print(doc); sys.exit(0)
    r = subprocess.run(["jq", "-r", jq], input=doc, capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr); sys.exit(r.returncode)

def fail(msg, code=1):
    save(); sys.stderr.write(msg + "\n"); sys.exit(code)

def git(*a, cwd=None, check=True):
    r = subprocess.run(["git"] + list(a), cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        fail("fake gh: git %s failed: %s" % (" ".join(a), r.stderr))
    return r.stdout.strip()

ORIGIN = st["origin"]
def ref(name):
    r = subprocess.run(["git", "--git-dir", ORIGIN, "rev-parse", "-q", "--verify", name], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

def is_ancestor(a, b):
    return subprocess.run(["git", "--git-dir", ORIGIN, "merge-base", "--is-ancestor", a, b]).returncode == 0

def pr_by(key):
    for p in st.get("prs", []):
        if str(p["number"]) == str(key) or (p["state"] == "OPEN" and p["head"] == key):
            return p
    return None

def pr_view(p):
    head = ref("refs/heads/" + p["head"]) if p["state"] == "OPEN" else p.get("mergedHead") or p.get("closedHead")
    return {"number": p["number"], "state": p["state"], "headRefName": p["head"], "headRefOid": head,
            "baseRefName": p["base"], "title": p["title"], "url": p["url"], "labels": [{"name": l} for l in p["labels"]]}

def push_develop_commit(tag):
    tmp = tempfile.mkdtemp()
    try:
        git("clone", "-q", "--branch", "develop", ORIGIN, tmp + "/c")
        open(tmp + "/c/" + tag + ".txt", "w").write(tag + "\n")
        git("add", tag + ".txt", cwd=tmp + "/c")
        git("commit", "-q", "-m", "feat: %s (#9%d)" % (tag, len(st.get("moves", []))), cwd=tmp + "/c")
        git("push", "-q", "origin", "develop", cwd=tmp + "/c")
        st.setdefault("moves", []).append(tag)
    finally:
        shutil.rmtree(tmp)

cmd = argv[:2]

if cmd == ["repo", "view"]:
    emit({"nameWithOwner": st["repo"]})

if argv[:1] == ["api"]:
    path = argv[1]
    if path == "repos/" + st["repo"]:
        emit({"full_name": st["repo"], "allow_merge_commit": st["allow_merge_commit"]})
    if path == "repos/%s/branches/develop/protection" % st["repo"]:
        if st.get("protection") is None:
            fail('{"message":"Branch not protected","status":"404"}')
        emit({"required_status_checks": st["protection"]})
    fail("fake gh: unknown api path " + path)

if cmd == ["run", "list"]:
    commit = opt("--commit")
    st["run_list_calls"] = st.get("run_list_calls", 0) + 1
    out = []
    for r in st.get("runs", []):
        if r["commit"] != commit:
            continue
        if st["run_list_calls"] <= r.get("appears_after", 0):
            continue
        running = st["run_list_calls"] <= r.get("appears_after", 0) + r.get("in_progress_polls", 0)
        out.append({"databaseId": r["id"], "status": "in_progress" if running else "completed",
                    "conclusion": None if running else r["conclusion"],
                    "headBranch": r["headBranch"], "workflowName": r["workflowName"]})
    emit(out)

if cmd == ["run", "view"]:
    for r in st.get("runs", []):
        if str(r["id"]) == argv[2]:
            emit({"jobs": r.get("jobs", [])})
    fail("fake gh: no run " + argv[2])

if cmd == ["release", "view"]:
    if argv[2] in st.get("releases", []):
        emit({"tagName": argv[2]})
    fail("release not found")

if cmd == ["label", "list"]:
    emit([{"name": n} for n in st.get("labels", [])])
if cmd == ["label", "create"]:
    st.setdefault("labels", []).append(argv[2]); save(); sys.exit(0)

if cmd == ["pr", "list"]:
    out = []
    for p in st.get("prs", []):
        if opt("--state", "open").upper() != p["state"] and opt("--state", "open") != "all":
            continue
        if opt("--head") and p["head"] != opt("--head"):
            continue
        if opt("--base") and p["base"] != opt("--base"):
            continue
        out.append(pr_view(p))
    emit(out)

if cmd == ["pr", "create"]:
    head, base = opt("--head"), opt("--base")
    if ref("refs/heads/" + head) is None:
        fail("fake gh: head branch %s is not on origin" % head)
    if pr_by(head):
        fail("a pull request for branch %s already exists" % head)
    n = st.get("next_pr", 1); st["next_pr"] = n + 1
    labels = [argv[i + 1] for i, a in enumerate(argv) if a == "--label"]
    for l in labels:
        if l not in st.get("labels", []):
            fail("could not add label: '%s' not found" % l)
    url = "https://github.com/%s/pull/%d" % (st["repo"], n)
    st.setdefault("prs", []).append({"number": n, "head": head, "base": base, "title": opt("--title"),
                                     "body": opt("--body"), "labels": labels, "state": "OPEN", "url": url})
    save(); print(url); sys.exit(0)

if cmd == ["pr", "view"]:
    p = pr_by(argv[2])
    if p is None:
        fail("no pull requests found for branch \"%s\"" % argv[2])
    emit(pr_view(p))

if cmd == ["pr", "checks"]:
    p = pr_by(argv[2]); head = ref("refs/heads/" + p["head"])
    c = st.setdefault("checks", {})
    if c.get("_head") != head:
        c["_head"] = head; c["_polls"] = 0
    c["_polls"] += 1
    c["_total"] = c.get("_total", 0) + 1
    if c["_total"] in c.get("move_develop_on", []) or c.get("move_develop_always"):
        push_develop_commit("moved-%d" % c["_total"])
    if c["_polls"] <= c.get("pending_polls", 0):
        emit([{"name": n, "bucket": "pending"} for n in c.get("result", {})])
    emit([{"name": n, "bucket": b} for n, b in c.get("result", {}).items()])

if cmd == ["pr", "merge"]:
    p = pr_by(argv[2])
    if p is None or p["state"] != "OPEN":
        fail("fake gh: #%s is not open" % argv[2])
    if "--admin" in argv:
        fail("fake gh: --admin is refused by this test")
    if "--merge" not in argv:
        fail("fake gh: only merge commits are allowed")
    head = ref("refs/heads/" + p["head"])
    if opt("--match-head-commit") != head:
        fail("Head branch was modified. Review and try the merge again.")
    prot = st.get("protection") or {}
    if prot.get("strict") and not is_ancestor("refs/heads/" + p["base"], head):
        fail("Head branch is out of date. Review and try the merge again.")
    if st.get("refuse_merges", 0) > 0:
        st["refuse_merges"] -= 1
        fail("Pull request is not mergeable")
    tmp = tempfile.mkdtemp()
    try:
        git("clone", "-q", "--branch", p["base"], ORIGIN, tmp + "/c")
        git("merge", "-q", "--no-ff", "origin/" + p["head"], "-m", "%s (#%d)" % (p["title"], p["number"]),
            "-m", p.get("body") or "", cwd=tmp + "/c")
        git("push", "-q", "origin", p["base"], cwd=tmp + "/c")
        if st.get("delete_branch_on_merge", True):
            git("push", "-q", "origin", "--delete", p["head"], cwd=tmp + "/c")
    finally:
        shutil.rmtree(tmp)
    p["state"] = "MERGED"; p["mergedHead"] = head
    save(); sys.exit(0)

if cmd == ["pr", "close"]:
    p = pr_by(argv[2]); p["closedHead"] = ref("refs/heads/" + p["head"])
    p["state"] = "CLOSED"; p["closeComment"] = opt("--comment"); save(); sys.exit(0)

if cmd == ["workflow", "run"]:
    fields = [argv[i + 1] for i, a in enumerate(argv) if a == "-f"]
    st.setdefault("dispatches", []).append({"workflow": argv[2], "ref": opt("--ref"), "fields": fields})
    save(); sys.exit(0)

fail("fake gh: unsupported %r" % argv, 2)
'''


class Sandbox:
    """A temporary directory with its own git configuration and fakes on PATH."""

    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="backmerge-test-")).resolve()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.tmp / "t").mkdir()
        for name, text in (("uv", FAKE_UV), ("npm", FAKE_NPM), ("node", FAKE_NODE), ("gh", FAKE_GH)):
            p = self.bin / name
            p.write_text(text)
            p.chmod(0o755)
        self.state_path = self.tmp / "gh-state.json"
        self.env = dict(os.environ)
        for k in ("GH_TOKEN", "GITHUB_TOKEN", "GIT_DIR", "GIT_WORK_TREE"):
            self.env.pop(k, None)
        self.env.update({
            "GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test Dev", "GIT_AUTHOR_EMAIL": "dev@example.invalid",
            "GIT_COMMITTER_NAME": "Test Dev", "GIT_COMMITTER_EMAIL": "dev@example.invalid",
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "TMPDIR": str(self.tmp / "t"),
            "FAKE_GH_STATE": str(self.state_path),
            "GIT_BACK_MERGE_POLL": "0",
            "GIT_BACK_MERGE_TIMEOUT": "60",
        })
        for key, value in (("init.defaultBranch", "main"), ("advice.detachedHead", "false"),
                           ("merge.conflictStyle", "merge"), ("commit.gpgsign", "false"),
                           ("tag.gpgsign", "false"), ("protocol.file.allow", "always")):
            self.git(self.tmp, "config", "--global", key, value)

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run(self, args, cwd, env=None, check=True) -> subprocess.CompletedProcess:
        e = dict(self.env)
        if env:
            e.update(env)
        r = subprocess.run(args, cwd=str(cwd), env=e, capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"{args} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
        return r

    def git(self, cwd, *args, env=None, check=True) -> str:
        return self.run(["git", *args], cwd, env=env, check=check).stdout.strip()

    def script(self, name: str, *args, cwd, env=None) -> subprocess.CompletedProcess:
        """Run a script; a shell fault in its stderr (a bash 3.2 misparse, say) fails the test."""
        r = self.run([BASH, str(SCRIPTS / name), *args], cwd, env=env, check=False)
        for fault in ("syntax error", "command not found", "unbound variable", "bad substitution"):
            if fault in r.stderr:
                raise AssertionError(f"{name}: shell fault '{fault}':\n{r.stderr}")
        return r

    # --- the fake GitHub's state
    def gh_state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def set_gh_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=1))

    def update_gh_state(self, **changes) -> None:
        s = self.gh_state()
        s.update(changes)
        self.set_gh_state(s)


BOT = {
    "GIT_AUTHOR_NAME": "github-actions[bot]", "GIT_COMMITTER_NAME": "github-actions[bot]",
    "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
    "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
}

RELEASE_YML_CHANGELOG = (
    "name: Release\non:\n  push:\n    tags: ['v*']\njobs:\n  gate:\n    runs-on: ubuntu-latest\n"
    "  changelog:\n    runs-on: ubuntu-latest\n    steps:\n"
    "      - run: git commit -m \"docs(changelog): ${TAG} [skip ci]\"\n"
)
RELEASE_YML_DOCUMENTS = (
    "name: Release\non:\n  push:\n    tags: ['v*']\njobs:\n  gate:\n    runs-on: ubuntu-latest\n"
    "  release:\n    runs-on: ubuntu-latest\n"
)


class ReleasedRepo:
    """An origin with one release made and a second being back-merged.

    kind is 'pyproject', 'package' or 'version-txt'. After construction:
    v1 released and (in a code repository) develop opened at its placeholder;
    feature A merged; develop promoted into main, bumped and tagged v2; where
    the release writes a changelog, the bot's changelog commit on main; and,
    if feature_during_release, feature F merged into develop after the promotion.
    lock_bulk pads the lockfile with that many dependency entries after the
    project's own, to the size of a real one.
    `releaser` is a clone used to make the history; `dev` is a clone with develop
    checked out, from which git-back-merge is run.
    """

    VERSIONS = {"pyproject": ("0.1.0", "0.1.1", "0.1.2.dev0", "0.1.1.dev0"),
                "package": ("3.5.0", "3.5.1", "3.5.2-dev0", "3.5.1-dev0"),
                "version-txt": ("0.23.0", "0.23.1", None, None)}

    def __init__(self, sb: Sandbox, kind: str = "pyproject", feature_during_release: bool = True,
                 changelog: bool | None = None, lockfile: bool = True, lock_bulk: int = 0) -> None:
        self.sb, self.kind = sb, kind
        self.lock_bulk = lock_bulk
        self.v1, self.v2, self.placeholder, self.dev1 = self.VERSIONS[kind]
        self.tag1, self.tag2 = "v" + self.v1, "v" + self.v2
        self.changelog = (kind != "version-txt") if changelog is None else changelog
        self.origin = sb.tmp / "origin.git"
        sb.git(sb.tmp, "init", "-q", "--bare", str(self.origin))
        sb.git(self.origin, "symbolic-ref", "HEAD", "refs/heads/develop")
        self.releaser = sb.tmp / "releaser"
        sb.git(sb.tmp, "clone", "-q", str(self.origin), str(self.releaser))
        r = self.releaser
        sb.git(r, "symbolic-ref", "HEAD", "refs/heads/main")
        (r / ".github" / "workflows").mkdir(parents=True)
        (r / ".github" / "workflows" / "release.yml").write_text(
            RELEASE_YML_CHANGELOG if self.changelog else RELEASE_YML_DOCUMENTS)
        self.write_version_files(r, self.v1, lockfile)
        (r / "CHANGELOG.md").write_text("# Changelog\n")
        (r / "app.txt").write_text("line 1\nline 2\nline 3\n")
        self.g("add", "-A")
        self.g("commit", "-q", "-m", "chore: initial commit")
        self.g("tag", "-a", self.tag1, "-m", "Release " + self.tag1)
        self.g("push", "-q", "origin", "main", "--follow-tags")
        self.g("switch", "-q", "-c", "develop")
        if kind != "version-txt":
            self.set_version(r, self.dev1)
            self.g("commit", "-q", "-am", f"chore: open {self.dev1} dev cycle")
        self.g("push", "-q", "-u", "origin", "develop")
        # feature A, merged by pull request (a squash commit, as before the switch)
        self.edit(r, "app.txt", "line 1\nline 2 (feature A)\nline 3\n")
        self.g("commit", "-q", "-am", "feat: feature A (#1)")
        self.g("push", "-q", "origin", "develop")
        self.promoted = self.g("rev-parse", "develop")
        # the release: promotion, bump, tag, push; then the changelog job's commit
        self.g("switch", "-q", "main")
        self.g("merge", "-q", "--no-ff", "develop", "-m", f"Release: develop → main for {self.tag2}")
        self.set_version(r, self.v2)
        self.g("commit", "-q", "-am", f"release {self.tag2}")
        self.g("tag", "-a", self.tag2, "-m", "Release " + self.tag2)
        self.g("push", "-q", "origin", "main", "--follow-tags")
        self.tag_commit = self.g("rev-parse", self.tag2 + "^{commit}")
        if self.changelog:
            self.edit(r, "CHANGELOG.md", f"# Changelog\n\n## [{self.tag2}]\n- feature A\n")
            self.g("commit", "-q", "-am", f"docs(changelog): {self.tag2} [skip ci]", env=BOT)
            self.g("push", "-q", "origin", "main")
        self.main_tip = self.g("rev-parse", "main")
        self.g("switch", "-q", "develop")
        if feature_during_release:
            self.edit(r, "other.txt", "feature F\n")
            self.g("add", "other.txt")
            self.g("commit", "-q", "-m", "feat: feature F (#2)")
            self.g("push", "-q", "origin", "develop")
        self.dev = sb.tmp / "dev"
        sb.git(sb.tmp, "clone", "-q", "--branch", "develop", str(self.origin), str(self.dev))

    # helpers
    def g(self, *args, env=None) -> str:
        return self.sb.git(self.releaser, *args, env=env)

    @staticmethod
    def edit(wt: Path, name: str, text: str) -> None:
        (wt / name).write_text(text)

    def write_version_files(self, wt: Path, version: str, lockfile: bool = True) -> None:
        if self.kind == "pyproject":
            (wt / "pyproject.toml").write_text(pyproject_text("sim-app", version))
            if lockfile:
                (wt / "uv.lock").write_text(uv_lock_text("sim-app", version, self.lock_bulk))
        elif self.kind == "package":
            (wt / "package.json").write_text(package_json_text("sim-node", version))
            if lockfile:
                (wt / "package-lock.json").write_text(package_lock_text("sim-node", version, self.lock_bulk))
        else:
            (wt / "VERSION.txt").write_text(version + "\n")

    def set_version(self, wt: Path, version: str, lock: bool = True) -> None:
        if self.kind == "pyproject":
            set_pyproject_version(wt, version, lock)
        elif self.kind == "package":
            set_package_version(wt, version, lock)
        else:
            (wt / "VERSION.txt").write_text(version + "\n")

    def version_at(self, rev: str, cwd: Path | None = None) -> str:
        cwd = cwd or self.releaser
        if self.kind == "pyproject":
            text = self.sb.git(cwd, "show", f"{rev}:pyproject.toml")
            return re.search(r'(?m)^version = "([^"]*)"', text).group(1)
        if self.kind == "package":
            return json.loads(self.sb.git(cwd, "show", f"{rev}:package.json"))["version"]
        return self.sb.git(cwd, "show", f"{rev}:VERSION.txt").strip()

    def gh_state(self, **overrides) -> dict:
        state = {
            "repo": "ParkviewLab/sim", "origin": str(self.origin), "allow_merge_commit": True,
            "protection": {"strict": True, "contexts": ["no-version-change", "test"]},
            "runs": [
                {"id": 101, "commit": self.tag_commit, "headBranch": self.tag2, "workflowName": "Release",
                 "conclusion": "success",
                 "jobs": [{"name": "gate", "conclusion": "success"},
                          {"name": "changelog" if self.changelog else "release", "conclusion": "success"}]},
                {"id": 102, "commit": self.tag_commit, "headBranch": "main", "workflowName": "Test",
                 "conclusion": "success", "jobs": [{"name": "test", "conclusion": "success"}]},
            ],
            "releases": [self.tag2], "labels": [], "prs": [], "next_pr": 7,
            "checks": {"pending_polls": 1, "result": {"no-version-change": "pass", "test": "pass", "reuse": "pass"}},
        }
        state.update(overrides)
        return state
