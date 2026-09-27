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

def pyproject_text(name: str, version: str, head: str = "") -> str:
    # head: text before the [project] table, such as a [tool] table
    return head + (
        "[project]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = ["idna"]\n'
        "\n[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )


def uv_lock_text(name: str, version: str, bulk: int = 0, twin: str | None = None,
                 project_version: bool = True) -> str:
    # A dependency's block comes first, so that a version line which is not the
    # project's can be told apart from the project's own. bulk adds that many
    # dependency blocks after the project's, as a real lockfile has: well over a
    # pipe buffer of text after the version line, once bulk is in the thousands.
    # twin adds a dependency whose version is always twin; project_version=False
    # leaves the project's block without a version line, as uv writes it for a
    # dynamic version.
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
        + (f'version = "{version}"\n' if project_version else "") +
        'source = { editable = "." }\n'
        "dependencies = [\n"
        '    { name = "idna" },\n'
        "]\n"
    ) + (f'\n[[package]]\nname = "twin"\nversion = "{twin}"\n'
         'source = { registry = "https://pypi.org/simple" }\n' if twin else "") + "".join(
        f'\n[[package]]\nname = "dep-{i:05d}"\nversion = "1.0.{i}"\n'
        'source = { registry = "https://pypi.org/simple" }\n' for i in range(bulk))


def package_json_text(name: str, version: str) -> str:
    return json.dumps({"name": name, "version": version, "private": True,
                       "dependencies": {"left-pad": "^1.3.0"}}, indent=2) + "\n"


def package_lock_text(name: str, version: str, bulk: int = 0, twin: str | None = None) -> str:
    packages = {
        "": {"name": name, "version": version, "dependencies": {"left-pad": "^1.3.0"}},
        "node_modules/left-pad": {"version": "1.3.0",
                                  "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz"},
    }
    if twin:
        packages["node_modules/twin"] = {"version": twin}
    for i in range(bulk):
        packages[f"node_modules/dep-{i:05d}"] = {
            "version": f"1.0.{i}", "resolved": f"https://registry.npmjs.org/dep-{i:05d}/-/dep-{i:05d}-1.0.{i}.tgz"}
    return json.dumps({"name": name, "version": version, "lockfileVersion": 3, "requires": True,
                       "packages": packages}, indent=2) + "\n"


def normalised(name: str) -> str:
    """A package name as uv records it (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def set_pyproject_version(wt: Path, version: str, lock: bool = True) -> None:
    p = wt / "pyproject.toml"
    text = p.read_text()
    name = re.search(r'(?m)^name = "([^"]*)"', text).group(1)
    p.write_text(re.sub(r'(?m)^version = "[^"]*"', f'version = "{version}"', text, count=1))
    if lock and (wt / "uv.lock").exists():
        set_uv_lock_version(wt, normalised(name), version)


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


def write_json(path: Path, data: dict, crlf: bool) -> None:
    text = json.dumps(data, indent=2) + "\n"
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode())


def set_package_version(wt: Path, version: str, lock: bool = True) -> None:
    # as npm does, the line endings the file has are kept
    pj = wt / "package.json"
    raw = pj.read_bytes().decode()
    data = json.loads(raw)
    data["version"] = version
    write_json(pj, data, "\r\n" in raw)
    pl = wt / "package-lock.json"
    if lock and pl.exists():
        raw = pl.read_bytes().decode()
        data = json.loads(raw)
        data["version"] = version
        data["packages"][""]["version"] = version
        write_json(pl, data, "\r\n" in raw)


TWIN_UPGRADE = {"pyproject": "0.2.0", "package": "4.0.0"}


def upgrade_twin(repo: "ReleasedRepo") -> None:
    """A change merged into develop that upgrades the dependency named twin in the
    lockfile (ReleasedRepo's lock_twin), to TWIN_UPGRADE's version."""
    wt, version = repo.releaser, TWIN_UPGRADE[repo.kind]
    if repo.kind == "pyproject":
        set_uv_lock_version(wt, "twin", version)
    else:
        pl = wt / "package-lock.json"
        raw = pl.read_bytes().decode()
        data = json.loads(raw)
        data["packages"]["node_modules/twin"]["version"] = version
        write_json(pl, data, "\r\n" in raw)
    repo.g("commit", "-q", "-am", "build: upgrade twin (#7)")


FIX_LINE_2 = ("app.txt", "line 1\nline 2 (fixed)\nline 3\n")   # a hotfix's fix to line 2 of app.txt


def rework_line_2(repo: "ReleasedRepo") -> None:
    """A change merged into develop after the fix, to the line the fix changed."""
    ReleasedRepo.edit(repo.releaser, "app.txt", "line 1\nline 2 (fixed, then reworked)\nline 3\n")
    repo.g("commit", "-q", "-am", "feat: rework line 2 (#9)")


def next_placeholder(kind: str, version: str) -> str | None:
    """The next-patch placeholder after a release, as _sot.sh computes it; None for VERSION.txt."""
    x, y, z = version.split(".")
    if kind == "pyproject":
        return f"{x}.{y}.{int(z) + 1}.dev0"
    if kind == "package":
        return f"{x}.{y}.{int(z) + 1}-dev0"
    return None


# ---------------------------------------------------------------- the fakes

FAKE_UV = r'''#!/usr/bin/env python3
# A fake uv: `uv version <v>` and `uv run --quiet python -c <code>`, all _sot.sh needs.
import os, re, subprocess, sys
a = sys.argv[1:]
if a[:1] == ["version"] and len(a) >= 2:
    if os.environ.get("FAKE_UV_LOG"):
        open(os.environ["FAKE_UV_LOG"], "a").write("UV_NO_SYNC=%s\n" % os.environ.get("UV_NO_SYNC", ""))
    v = [x for x in a[1:] if not x.startswith("-")][0]
    text = open("pyproject.toml").read()
    name = re.sub(r"[-_.]+", "-", re.search(r'(?m)^name = "([^"]*)"', text).group(1)).lower()
    open("pyproject.toml", "w").write(re.sub(r'(?m)^version = "[^"]*"', 'version = "%s"' % v, text, count=1))
    if os.path.exists("uv.lock"):
        lines = open("uv.lock").read().splitlines(True); inside = False
        for i, l in enumerate(lines):
            if l.startswith("[[package]]"): inside = False
            elif l == 'name = "%s"\n' % name: inside = True
            elif inside and l.startswith('version = "'): lines[i] = 'version = "%s"\n' % v; inside = False
        open("uv.lock", "w").write("".join(lines))
    if os.environ.get("FAKE_UV_FAIL"):   # as when the sync after the re-lock fails
        sys.stderr.write("error: Failed to build the project\n"); sys.exit(1)
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
    def write(name, d, raw):   # npm keeps the file's line endings
        text = json.dumps(d, indent=2) + "\n"
        open(name, "wb").write((text.replace("\n", "\r\n") if b"\r\n" in raw else text).encode())
    raw = open("package.json", "rb").read(); d = json.loads(raw); d["version"] = v
    write("package.json", d, raw)
    if os.path.exists("package-lock.json"):
        raw = open("package-lock.json", "rb").read(); d = json.loads(raw)
        d["version"] = v; d["packages"][""]["version"] = v
        write("package-lock.json", d, raw)
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
st.setdefault("gh_repo", []).append(os.environ.get("GH_REPO"))
for once in st.get("fail_once", []):   # a transient failure of the first such call
    if argv[:len(once.split())] == once.split():
        st["fail_once"].remove(once); st.setdefault("failed_once", []).append(once)
        json.dump(st, open(SP, "w"), indent=1)
        sys.stderr.write("HTTP 502: Bad Gateway\n"); sys.exit(1)

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

def api_error(message, status):
    # as real gh: the response body on stdout, unfiltered by --jq; the message on stderr
    save(); print(json.dumps({"message": message, "status": str(status)}))
    sys.stderr.write("gh: %s (HTTP %d)\n" % (message, status)); sys.exit(1)

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
        if str(p["number"]) == str(key) or (p["state"] == "OPEN" and p["head"] == key and not p.get("fork")):
            return p
    return None

def pr_view(p):
    head = ref("refs/heads/" + p["head"]) if p["state"] == "OPEN" else p.get("mergedHead") or p.get("closedHead")
    lag = st.get("view_lag", 0)   # GitHub's reported head lags each push by `lag` reads
    if lag and p["state"] == "OPEN" and head:
        if p.get("_live") != head:
            if p.get("_live"):
                p["_shown"] = p["_live"]; p["_lag_left"] = lag
            else:
                p["_shown"] = head; p["_lag_left"] = 0
            p["_live"] = head
        if p.get("_lag_left", 0) > 0:
            p["_lag_left"] -= 1; st.setdefault("lagged_reads", []).append(p["_shown"][:7])
            head = p["_shown"]
    if p.get("fork"):
        head = p["forkHead"]   # the branch lives in the fork, not in origin
    return {"number": p["number"], "state": p["state"], "headRefName": p["head"], "headRefOid": head,
            "isCrossRepository": bool(p.get("fork")),
            "baseRefName": p["base"], "title": p["title"], "url": p["url"], "labels": [{"name": l} for l in p["labels"]]}

def merge(p):
    head = ref("refs/heads/" + p["head"])
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

def push_branch_commit(branch, name):
    tmp = tempfile.mkdtemp()
    try:
        git("clone", "-q", "--branch", branch, ORIGIN, tmp + "/c")
        open(tmp + "/c/" + name + ".txt", "w").write(name + "\n")
        git("add", name + ".txt", cwd=tmp + "/c")
        git("commit", "-q", "-m", "fix: %s" % name, cwd=tmp + "/c")
        git("push", "-q", "origin", branch, cwd=tmp + "/c")
    finally:
        shutil.rmtree(tmp)

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
    admin = st.get("admin", True)   # GitHub omits the merge settings for a caller without admin rights
    if path == "repos/" + st["repo"]:
        emit({"full_name": st["repo"], **({"allow_merge_commit": st["allow_merge_commit"]} if admin else {})})
    if path == "repos/%s/branches/develop/protection" % st["repo"]:
        if not admin:
            api_error("Not Found", 404)
        if st.get("protection") is None:
            api_error("Branch not protected", 404)
        emit({"required_status_checks": st["protection"]})
    api_error("Not Found", 404)

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
    if any(p["state"] == "OPEN" and p["head"] == head and p["base"] == base and not p.get("fork")
           for p in st.get("prs", [])):
        fail("a pull request for branch %s into %s already exists" % (head, base))
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
    if opt("--json") == "state" and st.get("fail_state_view"):   # the state read after the merge fails
        st["fail_state_view"] -= 1; fail("HTTP 502: Bad Gateway")
    p = pr_by(argv[2])
    if p is None:
        fail("no pull requests found for branch \"%s\"" % argv[2])
    emit(pr_view(p))

if cmd == ["pr", "checks"]:
    if st.get("checks_error"):   # a persistent error, such as a failed authentication
        fail(st["checks_error"])
    p = pr_by(argv[2]); head = ref("refs/heads/" + p["head"])
    c = st.setdefault("checks", {})
    if c.get("_head") != head:
        c["_head"] = head; c["_polls"] = 0
    c["_polls"] += 1
    c["_total"] = c.get("_total", 0) + 1
    if c["_total"] in c.get("move_develop_on", []) or c.get("move_develop_always"):
        push_develop_commit("moved-%d" % c["_total"])
    if c["_total"] == c.get("push_foreign_on"):
        push_branch_commit(p["head"], "foreign")   # a push by another hand, or "Update branch"
    if c["_total"] == c.get("merged_by_another_hand_on"):
        merge(p)   # a person presses the merge button while the command polls
    if c["_total"] == c.get("closed_by_another_hand_on"):
        p["closedHead"] = ref("refs/heads/" + p["head"]); p["state"] = "CLOSED"   # a person closes it
    if c["_total"] == c.get("delete_branch_on"):
        # a person deletes back-merge-<tag> on origin, and GitHub closes the pull request
        p["closedHead"] = ref("refs/heads/" + p["head"]); p["state"] = "CLOSED"
        subprocess.run(["git", "--git-dir", ORIGIN, "update-ref", "-d", "refs/heads/" + p["head"]], check=True)
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
    if st.get("move_develop_before_merge", 0) > 0:
        st["move_develop_before_merge"] -= 1
        push_develop_commit("moved-at-merge")
    if st.get("push_foreign_before_merge", 0) > 0:   # a push to the branch between the checks and the merge
        st["push_foreign_before_merge"] -= 1
        push_branch_commit(p["head"], "foreign-at-merge")
    head = ref("refs/heads/" + p["head"])
    if opt("--match-head-commit") != head:
        fail("Head branch was modified. Review and try the merge again.")
    prot = st.get("protection") or {}
    if prot.get("strict") and not is_ancestor("refs/heads/" + p["base"], head):
        fail("Head branch is out of date. Review and try the merge again.")
    if st.get("refuse_merges", 0) > 0:
        st["refuse_merges"] -= 1
        fail("Pull request is not mergeable")
    merge(p)
    if st.get("merge_then_fail"):
        fail("HTTP 502: Server Error (https://api.github.com/graphql)")
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
    crlf writes package.json and package-lock.json with CRLF line endings, which
    the setters keep, as npm does; pyproject_head is text placed before the
    [project] table. lock_bulk pads the lockfile with that many dependency entries after the
    project's own, to the size of a real one. lock_twin adds a dependency named
    twin whose version is the release's, v2, throughout; lock_project_version=False
    leaves uv.lock without the project's version. first_release_by_fast_forward
    leaves v1 untagged and brings main to develop by a fast-forward rather than a
    promotion merge, so that v2 is a first release with no promotion commit.
    land_back_merge() then lands v2's back-merge on develop, and hotfix() releases
    a fix picked onto main after it.
    `releaser` is a clone used to make the history; `dev` is a clone with develop
    checked out, from which git-back-merge is run.
    """

    VERSIONS = {"pyproject": ("0.1.0", "0.1.1", "0.1.2.dev0", "0.1.1.dev0"),
                "package": ("3.5.0", "3.5.1", "3.5.2-dev0", "3.5.1-dev0"),
                "version-txt": ("0.23.0", "0.23.1", None, None)}
    HOTFIX = {"pyproject": "0.1.2", "package": "3.5.2", "version-txt": "0.23.2"}

    def __init__(self, sb: Sandbox, kind: str = "pyproject", feature_during_release: bool = True,
                 changelog: bool | None = None, lockfile: bool = True, lock_bulk: int = 0,
                 lock_twin: bool = False, lock_project_version: bool = True,
                 project_name: str = "sim-app", crlf: bool = False, pyproject_head: str = "",
                 first_release_by_fast_forward: bool = False) -> None:
        self.sb, self.kind = sb, kind
        self.project_name, self.crlf, self.pyproject_head = project_name, crlf, pyproject_head
        self.lock_bulk, self.lock_twin, self.lock_project_version = lock_bulk, lock_twin, lock_project_version
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
        if not first_release_by_fast_forward:
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
        if first_release_by_fast_forward:
            self.g("merge", "-q", "--ff-only", "develop")
        else:
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
        # the release gh_state describes; hotfix() makes it the hotfix
        self.release_tag, self.release_commit = self.tag2, self.tag_commit
        self.g("switch", "-q", "develop")
        if feature_during_release:
            self.edit(r, "other.txt", "feature F\n")
            self.g("add", "other.txt")
            self.g("commit", "-q", "-m", "feat: feature F (#2)")
            self.g("push", "-q", "origin", "develop")
        self.dev = sb.tmp / "dev"
        sb.git(sb.tmp, "clone", "-q", "--branch", "develop", str(self.origin), str(self.dev))

    def land_back_merge(self, pr: int = 6) -> None:
        """Land v2's back-merge on origin's develop in the shape git back-merge and
        GitHub's merge leave it: the merge M of main into develop, in a code
        repository the open-cycle commit C on it, and GitHub's merge of the
        pull request into develop."""
        g = self.g
        g("fetch", "-q", "origin")
        g("switch", "-q", "-C", "landing", "origin/develop")
        g("merge", "-q", "--no-ff", "origin/main", "-m", f"Back-merge: main → develop after {self.tag2}")
        if self.placeholder:
            self.set_version(self.releaser, self.placeholder)
            g("commit", "-q", "-am", f"chore: open {self.placeholder} dev cycle")
        head = g("rev-parse", "HEAD")
        g("switch", "-q", "develop")
        g("merge", "-q", "--ff-only", "origin/develop")
        g("merge", "-q", "--no-ff", head, "-m",
          f"chore(release): back-merge main into develop after {self.tag2} (#{pr})")
        g("push", "-q", "origin", "develop")
        g("branch", "-q", "-D", "landing")

    def promote(self, commit: str, version: str) -> None:
        """A release by promotion of a develop commit: its merge into main, the bump
        to version and its tag. Promoting a commit that predates the landed
        back-merge (land_back_merge()) crosses the two trunks' histories, so that a
        later back-merge has two merge bases."""
        g = self.g
        g("switch", "-q", "main")
        g("merge", "-q", "--ff-only", "origin/main")
        g("merge", "-q", "--no-ff", commit, "-m", f"Release: develop → main for v{version}")
        self.set_version(self.releaser, version)
        g("commit", "-q", "-am", f"release v{version}")
        g("tag", "-a", f"v{version}", "-m", f"Release v{version}")
        g("push", "-q", "origin", "main", "--follow-tags")
        g("switch", "-q", "develop")

    def hotfix(self, version: str | None = None, fix: tuple[str, str] = ("fix.txt", "fix\n"),
               after_fix=None) -> None:
        """Release a fix picked whole onto main, as the handbook's rule gives it: the
        fix merged into develop by a real merge, as GitHub makes it; on main,
        `git cherry-pick -m 1` of that merge, the bump to the hotfix version (HOTFIX,
        or version), its tag and, where the release writes a changelog, the bot's
        changelog commit. fix is the file the fix writes and its text; after_fix(repo),
        if given, adds commits to develop after the fix's merge. Sets v3, tag3,
        tag3_commit, placeholder3, fix_merge and main_tip, and makes the hotfix the
        release that gh_state describes."""
        g = self.g
        self.v3 = version or self.HOTFIX[self.kind]
        self.tag3, self.placeholder3 = "v" + self.v3, next_placeholder(self.kind, self.v3)
        g("fetch", "-q", "origin")
        g("switch", "-q", "develop")
        g("merge", "-q", "--ff-only", "origin/develop")
        g("switch", "-q", "-c", "fix-x")
        self.edit(self.releaser, fix[0], fix[1])
        g("add", fix[0])
        g("commit", "-q", "-m", "fix: x")
        g("switch", "-q", "develop")
        g("merge", "-q", "--no-ff", "fix-x", "-m", "fix: x (#8)")
        g("branch", "-q", "-D", "fix-x")
        self.fix_merge = g("rev-parse", "HEAD")
        if after_fix:
            after_fix(self)
        g("push", "-q", "origin", "develop")
        g("switch", "-q", "main")
        g("merge", "-q", "--ff-only", "origin/main")
        g("cherry-pick", "-m", "1", self.fix_merge)
        self.set_version(self.releaser, self.v3)
        g("commit", "-q", "-am", f"release {self.tag3}")
        g("tag", "-a", self.tag3, "-m", "Release " + self.tag3)
        g("push", "-q", "origin", "main", "--follow-tags")
        self.tag3_commit = g("rev-parse", self.tag3 + "^{commit}")
        if self.changelog:
            self.edit(self.releaser, "CHANGELOG.md",
                      f"# Changelog\n\n## [{self.tag3}]\n- x\n\n## [{self.tag2}]\n- feature A\n")
            g("commit", "-q", "-am", f"docs(changelog): {self.tag3} [skip ci]", env=BOT)
            g("push", "-q", "origin", "main")
        self.main_tip = g("rev-parse", "main")
        self.release_tag, self.release_commit = self.tag3, self.tag3_commit
        g("switch", "-q", "develop")

    # helpers
    def g(self, *args, env=None) -> str:
        return self.sb.git(self.releaser, *args, env=env)

    @staticmethod
    def edit(wt: Path, name: str, text: str) -> None:
        (wt / name).write_text(text)

    def write_version_files(self, wt: Path, version: str, lockfile: bool = True) -> None:
        if self.kind == "pyproject":
            (wt / "pyproject.toml").write_text(pyproject_text(self.project_name, version, self.pyproject_head))
            if lockfile:
                (wt / "uv.lock").write_text(uv_lock_text(
                    normalised(self.project_name), version, self.lock_bulk, self.v2 if self.lock_twin else None, self.lock_project_version))
        elif self.kind == "package":
            crlf = (lambda t: t.replace("\n", "\r\n")) if self.crlf else (lambda t: t)
            (wt / "package.json").write_bytes(crlf(package_json_text("sim-node", version)).encode())
            if lockfile:
                (wt / "package-lock.json").write_bytes(crlf(package_lock_text(
                    "sim-node", version, self.lock_bulk, self.v2 if self.lock_twin else None)).encode())
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
        tag, commit = self.release_tag, self.release_commit
        state = {
            "repo": "ParkviewLab/sim", "origin": str(self.origin), "allow_merge_commit": True,
            "protection": {"strict": True, "contexts": ["no-version-change", "test"]},
            "runs": [
                {"id": 101, "commit": commit, "headBranch": tag, "workflowName": "Release",
                 "conclusion": "success",
                 "jobs": [{"name": "gate", "conclusion": "success"},
                          {"name": "changelog" if self.changelog else "release", "conclusion": "success"}]},
                {"id": 102, "commit": commit, "headBranch": "main", "workflowName": "Test",
                 "conclusion": "success", "jobs": [{"name": "test", "conclusion": "success"}]},
            ],
            "releases": list(dict.fromkeys([self.tag2, tag])), "labels": [], "prs": [], "next_pr": 7,
            "checks": {"pending_polls": 1, "result": {"no-version-change": "pass", "test": "pass", "reuse": "pass"}},
        }
        state.update(overrides)
        return state
