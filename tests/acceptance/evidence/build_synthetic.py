#!/usr/bin/env python3
"""Part four: build synthetic repositories (no remote) whose histories exercise
the rule under real merges as well as squash, then run proposed_list2 over
their tags and check the result against the list stated in advance.

Main scenario (synthetic/main-scenario), two tags:
  v0.1.0 (first release)
    root            docs: start the changelog                  CHANGELOG.md only           -> bookkeeping (ii)
    #1  squash      chore: scaffold the project (#1)                                       -> Maintenance
    #2  squash      feat: greet by name (#2)                                               -> Features
    #3  real merge  feat: report command (#3)  branch of three commits and one merge of
                    develop into the branch; one branch commit carries BREAKING CHANGE     -> Breaking changes
    #4  squash      docs: usage guide (#4)  (lands on develop while #3 is open)            -> Docs
    local promotion merge  Release: develop -> main for v0.1.0                             -> bookkeeping (iii)
    #6  squash on develop after the promotion; cherry-picked onto main (no trailer)        -> Bug fixes (R2 c)
    release v0.1.0  pyproject.toml + uv.lock                                               -> bookkeeping (i)
  v0.2.0
    docs(changelog): v0.1.0 [skip ci] by github-actions[bot]                               -> bookkeeping (ii)
    #8  back-merge pull request main -> develop, default title (carrier)                   -> not listed (R3)
    chore: open 0.1.1.dev0 dev cycle  pyproject.toml + uv.lock                             -> bookkeeping (i)
    #6's original squash now in range                                                      -> not listed (R4)
    #5  merge at GitHub's default title, title from the pull request                       -> Bug fixes
    #7  squash      feat!: rename the greeting API (#7)                                    -> Breaking changes
    direct commit   build: cap requests below 3  (pyproject.toml dependency + uv.lock)     -> Direct commits
    local promotion merge                                                                  -> bookkeeping (iii)
    release v0.2.0  pyproject.toml + uv.lock                                               -> bookkeeping (i)

Supplementary scenario (synthetic/extra-scenario): the cases the rule must report
or cannot see: a merge whose tree differs from the automatic merge, a '(#N)'
suffix on a commit GitHub did not make, `git cherry-pick -m 1` of a real merge,
and a real merge picked commit by commit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import proposed_list2 as P  # noqa: E402

ROOT = HERE / "synthetic"
DEV = ("Dev Person", "dev@example.org")
GH = ("GitHub", "noreply@github.com")
BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")

PYPROJECT = """[project]
name = "synth-app"
version = "{version}"
requires-python = ">=3.11"
dependencies = ["requests{spec}"]
"""
UVLOCK = """version = 1
requires-python = ">=3.11"

[[package]]
name = "requests"
version = "2.32.3"
source = {{ registry = "https://pypi.org/simple" }}

[[package]]
name = "synth-app"
version = "{version}"
source = {{ editable = "." }}
dependencies = [
    {{ name = "requests" }},
]

[package.metadata]
requires-dist = [{{ name = "requests", specifier = "{spec}" }}]
"""


class Repo:
    def __init__(self, path: Path):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        self.path = path
        self.t = 1_780_000_000
        self.git("init", "-q", "-b", "main")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")

    def env(self, author, committer):
        self.t += 60
        e = dict(os.environ)
        e.update(GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1],
                 GIT_COMMITTER_NAME=committer[0], GIT_COMMITTER_EMAIL=committer[1],
                 GIT_AUTHOR_DATE=f"{self.t} +0000", GIT_COMMITTER_DATE=f"{self.t} +0000")
        return e

    def git(self, *a, author=DEV, committer=DEV, check=True) -> str:
        p = subprocess.run(["git", "-C", str(self.path), *a], capture_output=True, text=True,
                           env=self.env(author, committer))
        if check and p.returncode:
            raise RuntimeError(f"git {a}: {p.stderr}")
        return p.stdout.strip()

    def write(self, rel: str, text: str) -> None:
        f = self.path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def append(self, rel: str, text: str) -> None:
        f = self.path / rel
        f.write_text((f.read_text() if f.exists() else "") + text)

    def commit(self, msg: str, author=DEV, committer=DEV) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg, author=author, committer=committer)
        return self.git("rev-parse", "HEAD")

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def set_version(self, version: str, spec: str) -> None:
        self.write("pyproject.toml", PYPROJECT.format(version=version, spec=spec))
        self.write("uv.lock", UVLOCK.format(version=version, spec=spec))


def pr(n, title, body, base, head, oid):
    return {"number": n, "title": title, "body": body, "baseRefName": base, "headRefName": head,
            "mergeCommit": {"oid": oid}, "mergedAt": "2026-09-17T00:00:00Z"}


def build_main() -> tuple[Repo, list[dict]]:
    r = Repo(ROOT / "main-scenario")
    prs = []
    spec = ">=2.31"
    r.write("CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n")
    r.commit("docs: start the changelog")
    r.git("checkout", "-q", "-b", "develop")
    # 1: squash, scaffold (creates the version source of truth and the lockfile)
    r.set_version("0.1.0.dev0", spec)
    r.write("src/app.py", "def greet():\n    return 'hello'\n")
    prs.append(pr(1, "chore: scaffold the project", "Scaffold.", "develop", "scaffold",
                  r.commit("chore: scaffold the project (#1)\n\n* scaffold", DEV, GH)))
    # 2: squash
    r.write("src/app.py", "def greet(name='world'):\n    return f'hello {name}'\n")
    prs.append(pr(2, "feat: greet by name", "Adds a name.", "develop", "greet-by-name",
                  r.commit("feat: greet by name (#2)\n\n* greet by name", DEV, GH)))
    # 3: real merge; branch of three commits and one merge of develop into the branch
    r.git("checkout", "-q", "-b", "feature/report")
    r.write("src/report.py", "def report():\n    return 'report'\n")
    r.commit("report: skeleton")
    r.git("checkout", "-q", "develop")
    r.write("docs/usage.md", "# Usage\n")
    prs.append(pr(4, "docs: usage guide", "Usage.", "develop", "docs-usage",
                  r.commit("docs: usage guide (#4)\n\n* usage guide", DEV, GH)))
    r.git("checkout", "-q", "feature/report")
    r.git("merge", "-q", "--no-ff", "develop", "-m", "Merge branch 'develop' into feature/report")
    r.write("src/report.py", "import json\n\ndef report():\n    return json.dumps({'report': True})\n")
    r.commit("report: JSON output\n\nBREAKING CHANGE: report() now returns JSON text.")
    r.write("tests/test_report.py", "def test_report():\n    assert True\n")
    r.commit("report: tests")
    r.git("checkout", "-q", "develop")
    r.git("merge", "-q", "--no-ff", "feature/report", "-m", "feat: report command (#3)",
          "-m", "Adds the report command.", committer=GH)
    prs.append(pr(3, "feat: report command", "Adds the report command.", "develop", "feature/report", r.head()))
    # local release promotion
    r.git("checkout", "-q", "main")
    r.git("merge", "-q", "--no-ff", "develop", "-m", "Release: develop → main for v0.1.0")
    # 6: squash on develop after the promotion, then cherry-picked onto main (no -x)
    r.git("checkout", "-q", "develop")
    r.write("src/unicode.py", "def safe(name):\n    return name.encode('utf-8', 'replace').decode()\n")
    six = r.commit("fix: survive unicode names (#6)\n\n* survive unicode names", DEV, GH)
    prs.append(pr(6, "fix: survive unicode names", "Unicode.", "develop", "unicode-names", six))
    r.git("checkout", "-q", "main")
    r.git("cherry-pick", six)
    pick = r.head()
    # release bump, tag
    r.set_version("0.1.0", spec)
    r.commit("release v0.1.0")
    r.git("tag", "v0.1.0")
    # the release job's changelog commit on main
    r.append("CHANGELOG.md", "\n## [v0.1.0]\n\n- entries\n")
    r.commit("docs(changelog): v0.1.0 [skip ci]", BOT, BOT)
    # 8: back-merge pull request, main -> develop, default title (carrier)
    r.git("checkout", "-q", "develop")
    r.git("merge", "-q", "--no-ff", "main", "-m", "Merge pull request #8 from example/main",
          "-m", "Back-merge main into develop", committer=GH)
    prs.append(pr(8, "Back-merge main into develop", "", "develop", "main", r.head()))
    # open-cycle bump, direct push
    r.set_version("0.1.1.dev0", spec)
    r.commit("chore: open 0.1.1.dev0 dev cycle")
    # 5: merge at GitHub's default title
    r.git("checkout", "-q", "-b", "fix-typo")
    r.write("src/app.py", "def greet(name='world'):\n    return f'Hello, {name}'\n")
    r.commit("correct the greeting typo")
    r.git("checkout", "-q", "develop")
    r.git("merge", "-q", "--no-ff", "fix-typo", "-m", "Merge pull request #5 from example/fix-typo",
          "-m", "fix: correct the greeting typo", committer=GH)
    prs.append(pr(5, "fix: correct the greeting typo", "Typo.", "develop", "fix-typo", r.head()))
    # 7: squash, breaking by '!'
    r.write("src/app.py", "def salute(name='world'):\n    return f'Hello, {name}'\n")
    prs.append(pr(7, "feat!: rename the greeting API", "Renames greet to salute.", "develop", "rename-api",
                  r.commit("feat!: rename the greeting API (#7)\n\n* rename", DEV, GH)))
    # the one direct commit: a dependency pin in manifest and lockfile (not a version change)
    r.set_version("0.1.1.dev0", ">=2.31,<3")
    r.commit("build: cap requests below 3")
    # local promotion, bump, tag
    r.git("checkout", "-q", "main")
    r.git("merge", "-q", "--no-ff", "develop", "-m", "Release: develop → main for v0.2.0")
    r.set_version("0.2.0", ">=2.31,<3")
    r.commit("release v0.2.0")
    r.git("tag", "v0.2.0")
    r.pick = pick  # type: ignore[attr-defined]
    return r, sorted(prs, key=lambda p: p["number"])


def build_extra() -> tuple[Repo, list[dict]]:
    r = Repo(ROOT / "extra-scenario")
    prs = []
    spec = ">=2.31"
    r.write("CHANGELOG.md", "# Changelog\n")
    r.commit("docs: start the changelog")
    r.git("checkout", "-q", "-b", "develop")
    r.set_version("1.0.0.dev0", spec)
    r.write("src/a.py", "A = 1\n")
    r.write("src/b.py", "B = 1\n")
    prs.append(pr(1, "chore: scaffold", "", "develop", "scaffold", r.commit("chore: scaffold (#1)", DEV, GH)))
    r.git("checkout", "-q", "main")
    r.git("merge", "-q", "--no-ff", "develop", "-m", "Promote develop for v1.0.0")
    r.git("checkout", "-q", "develop")
    # 2: real merge, later picked onto main with `git cherry-pick -m 1`
    r.git("checkout", "-q", "-b", "parser")
    r.write("src/a.py", "A = 2\n")
    r.commit("parser: first edge case")
    r.write("src/c.py", "C = 1\n")
    r.commit("parser: second edge case")
    r.git("checkout", "-q", "develop")
    r.git("merge", "-q", "--no-ff", "parser", "-m", "fix: parser edge cases (#2)", committer=GH)
    m2 = r.head()
    prs.append(pr(2, "fix: parser edge cases", "", "develop", "parser", m2))
    # 3: real merge, later picked onto main commit by commit
    r.git("checkout", "-q", "-b", "exporter")
    r.write("src/d.py", "D = 1\n")
    e1 = r.commit("exporter: module")
    r.write("src/e.py", "E = 1\n")
    e2 = r.commit("exporter: wiring")
    r.git("checkout", "-q", "develop")
    r.git("merge", "-q", "--no-ff", "exporter", "-m", "feat: exporter (#3)", committer=GH)
    prs.append(pr(3, "feat: exporter", "", "develop", "exporter", r.head()))
    # a local merge whose tree differs from the automatic merge (an extra edit made in the merge)
    r.git("checkout", "-q", "-b", "side")
    r.write("src/f.py", "F = 1\n")
    r.commit("side: add f")
    r.git("checkout", "-q", "develop")
    r.git("merge", "-q", "--no-ff", "--no-commit", "side")
    r.write("src/b.py", "B = 2  # changed inside the merge\n")
    r.git("add", "-A")
    r.git("commit", "-q", "-m", "Merge branch 'side' into develop")
    # a '(#N)' suffix on a commit GitHub did not make
    r.write("src/g.py", "G = 1\n")
    r.commit("fix: tidy g (#99)")
    # release line: pick #2 with -m 1, pick #3's two commits one by one, bump, tag v1.0.0
    r.git("checkout", "-q", "main")
    r.git("cherry-pick", "-m", "1", m2)
    r.git("cherry-pick", e1)
    r.git("cherry-pick", e2)
    r.set_version("1.0.0", spec)
    r.commit("release v1.0.0")
    r.git("tag", "v1.0.0")
    # next release promotes develop
    r.git("merge", "-q", "--no-ff", "develop", "-m", "Promote develop for v1.1.0")
    r.set_version("1.1.0", spec)
    r.commit("release v1.1.0")
    r.git("tag", "v1.1.0")
    return r, sorted(prs, key=lambda p: p["number"])


def truth(r: Repo, prs: list[dict], prev: str | None, tag: str) -> list[int]:
    rng = set(r.git("rev-list", f"{prev}..{tag}" if prev else tag).split())
    return sorted(p["number"] for p in prs if p["mergeCommit"]["oid"] in rng)


def run(r: Repo, prs: list[dict], tags: list[str]) -> list[dict]:
    (r.path.parent / f"{r.path.name}.prs.json").write_text(json.dumps(prs, indent=1))
    out, prev = [], None
    for t in tags:
        res = P.build(str(r.path), prev, t, prs)
        carriers = [p["number"] for p in prs if p["baseRefName"] == "main" or p["headRefName"] in ("main", "develop")
                    or p["headRefName"].startswith("back-merge")]
        tr = truth(r, prs, prev, t)
        exp = sorted(set(tr) - set(carriers))
        out.append({"tag": t, "prev": prev, "truth": tr, "expected": exp, "result": res})
        prev = t
    return out


def main() -> None:
    results = {}
    r, prs = build_main()
    main_runs = run(r, prs, ["v0.1.0", "v0.2.0"])
    stated = {
        "v0.1.0": {"groups": {"Breaking changes": [3], "Features": [2], "Bug fixes": [6], "Docs": [4],
                              "Maintenance": [1]},
                   "direct": [], "already_shipped": [], "carriers": []},
        "v0.2.0": {"groups": {"Breaking changes": [7], "Bug fixes": [5]},
                   "direct": ["build: cap requests below 3"], "already_shipped": [6], "carriers": [8]},
    }
    checks = []
    for run_ in main_runs:
        res, want = run_["result"], stated[run_["tag"]]
        got = {"groups": {g: [e["number"] for e in v] for g, v in res["groups"].items()},
               "direct": [d["subject"] for d in res["direct_commits"]],
               "already_shipped": [a["number"] for a in res["already_shipped"]],
               "carriers": [c["number"] for c in res["carriers"]]}
        checks.append({"tag": run_["tag"], "stated": want, "got": got, "match": got == want})
    results["main_scenario"] = {"runs": main_runs, "checks": checks, "pick_commit": r.pick}
    rx, prsx = build_extra()
    results["extra_scenario"] = {"runs": run(rx, prsx, ["v1.0.0", "v1.1.0"])}
    (HERE / "synthetic" / "results.json").write_text(json.dumps(results, indent=1))
    for c in checks:
        print(c["tag"], "MATCH" if c["match"] else "MISMATCH", json.dumps(c["got"]))
    for run_ in results["extra_scenario"]["runs"]:
        res = run_["result"]
        print("extra", run_["tag"], "truth", run_["truth"], "listed", res["listed"],
              "direct", [d["subject"] for d in res["direct_commits"]],
              "shipped", [a["number"] for a in res["already_shipped"]])
        for w in res["warnings"]:
            print("   W", w)


if __name__ == "__main__":
    main()
