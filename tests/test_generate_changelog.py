# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for scripts/generate-changelog.

Run from the repository root:

    python3 -m unittest discover -s tests -v

Standard library only, and offline. The script has no .py suffix, so it is loaded
by path. Every history is built in a temporary repository, GitHub's commits made
under GitHub's committer identity; the pull requests are supplied as recorded JSON
in the shape GitHub's REST API returns, never read from GitHub; and the model call
is made against a stub anthropic module placed in sys.modules. The tests skip when
git is not installed.

The measurement's histories (tests/acceptance/evidence/build_synthetic.py) are
rebuilt here and checked against what was stated for them, with the correction of
decision 9b; the acceptance run, which needs the network, is tests/acceptance/.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate-changelog"
GIT = shutil.which("git")


def load_script():
    loader = importlib.machinery.SourceFileLoader("generate_changelog", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


gc = load_script()

SLUG = "ParkviewLab/example"
DEV = ("Dev Person", "dev@example.org")
GH = ("GitHub", "noreply@github.com")
BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")

PYPROJECT = '[project]\nname = "synth-app"\nversion = "{version}"\ndescription = "A synthetic app"\nrequires-python = ">=3.11"\ndependencies = ["requests{spec}"]\n'
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
PACKAGE_JSON = '{{\n  "name": "synth-web",\n  "version": "{version}",\n  "description": "A synthetic web app",\n  "dependencies": {{"left-pad": "^1.3.0"}}\n}}\n'
PACKAGE_LOCK = """{{
  "name": "synth-web",
  "version": "{version}",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {{
    "": {{
      "name": "synth-web",
      "version": "{version}",
      "dependencies": {{"left-pad": "^1.3.0"}}
    }},
    "node_modules/left-pad": {{
      "version": "1.3.0"
    }}
  }}
}}
"""
CARGO_TOML = '[package]\nname = "synth-rs"\nversion = "{version}"\nedition = "2021"\n\n[dependencies]\nserde = "1"\n'
CARGO_LOCK = """version = 4

[[package]]
name = "serde"
version = "1.0.210"

[[package]]
name = "synth-rs"
version = "{version}"
dependencies = [
 "serde",
]
"""


class Repo:
    """A temporary repository whose commits carry fixed dates and chosen identities."""

    def __init__(self, path: Path) -> None:
        path.mkdir(parents=True)
        self.path = path
        self.t = 1_780_000_000
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str, author=DEV, committer=DEV) -> str:
        self.t += 60
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(
            GIT_AUTHOR_NAME=author[0],
            GIT_AUTHOR_EMAIL=author[1],
            GIT_COMMITTER_NAME=committer[0],
            GIT_COMMITTER_EMAIL=committer[1],
            GIT_AUTHOR_DATE=f"{self.t} +0000",
            GIT_COMMITTER_DATE=f"{self.t} +0000",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
        )
        result = subprocess.run(
            [GIT, "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "advice.detachedHead=false", *args],
            cwd=self.path,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout.strip()

    def write(self, rel: str, text: str) -> None:
        f = self.path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def append(self, rel: str, text: str) -> None:
        f = self.path / rel
        self.write(rel, (f.read_text(encoding="utf-8") if f.exists() else "") + text)

    def commit(self, message: str, author=DEV, committer=DEV, empty: bool = False) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", *(["--allow-empty"] if empty else []), "-m", message, author=author, committer=committer)
        return self.head()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def checkout(self, branch: str, new: bool = False) -> None:
        self.git("checkout", "-q", *(["-b"] if new else []), branch)

    def merge(self, branch: str, *messages: str, committer=DEV) -> str:
        args = [a for m in messages for a in ("-m", m)]
        self.git("merge", "-q", "--no-ff", branch, *args, committer=committer)
        return self.head()

    def pick(self, sha: str, *options: str) -> str:
        self.git("cherry-pick", *options, sha)
        return self.head()

    def tag(self, name: str) -> None:
        self.git("tag", "-a", name, "-m", name)

    def short(self, sha: str) -> str:
        return sha[:7]


def rest_pr(n: int, title: str, merge_commit: str | None, *, body: str = "", base: str = "develop",
            head: str | None = None, fork: bool = False, merged: bool = True) -> dict:
    """One pull request as GET /repos/{owner}/{repo}/pulls returns it."""
    return {
        "number": n,
        "title": title,
        "body": body,
        "merged_at": "2026-09-17T00:00:00Z" if merged else None,
        "merge_commit_sha": merge_commit,
        "base": {"ref": base, "repo": {"full_name": SLUG}},
        "head": {"ref": head or f"branch-{n}", "repo": {"full_name": "someone/example" if fork else SLUG}},
    }


class StubAnthropic:
    """A stand-in for the anthropic module, recording every call it receives."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response, self.error, self.calls = response, error, []

    def module(self) -> types.ModuleType:
        stub = self
        mod = types.ModuleType("anthropic")

        class Anthropic:
            def __init__(self, **kwargs) -> None:
                self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=stub.create))

        mod.Anthropic = Anthropic
        return mod

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def answer(text: str | None, stop: str = "end_turn", category: str | None = None, model: str = "claude-opus-5"):
    content = [types.SimpleNamespace(type="text", text=text)] if text is not None else []
    details = types.SimpleNamespace(category=category) if stop == "refusal" else None
    return types.SimpleNamespace(stop_reason=stop, content=content, model=model, stop_details=details)


@unittest.skipUnless(GIT, "git is not installed")
class Fixture(unittest.TestCase):
    """A temporary repository, the pull requests GitHub would return for it, and a clean environment."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gc-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "ANTHROPIC_", "GIT_"))}
        env.update(GITHUB_REPOSITORY=SLUG, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.repo = Repo(self.tmp / "repo")
        self.prs: list[dict] = []

    # -- building histories
    def squash(self, n: int, title: str, files: dict[str, str], *, message_body: str | None = None, **pr) -> str:
        for rel, text in files.items():
            self.repo.write(rel, text)
        sha = self.repo.commit(f"{title} (#{n})\n\n{message_body or '* ' + title}", DEV, GH)
        self.prs.append(rest_pr(n, pr.pop("api_title", title), sha, **pr))
        return sha

    def branch_commits(self, branch: str, commits: list[tuple[str, dict[str, str]]]) -> list[str]:
        self.repo.checkout(branch, new=True)
        shas = []
        for message, files in commits:
            for rel, text in files.items():
                self.repo.write(rel, text)
            shas.append(self.repo.commit(message))
        return shas

    def real_merge(self, n: int, title: str, branch: str, into: str, *, titled: bool = True, **pr) -> str:
        self.repo.checkout(into)
        if titled:
            sha = self.repo.merge(branch, f"{title} (#{n})", pr.get("body") or "Merged.", committer=GH)
        else:
            sha = self.repo.merge(branch, f"Merge pull request #{n} from example/{branch}", title, committer=GH)
        self.prs.append(rest_pr(n, pr.pop("api_title", title), sha, head=pr.pop("head", branch), **pr))
        return sha

    # -- running the script
    def pull_requests(self) -> dict:
        prs = (gc.pull_request_from_rest(obj) for obj in self.prs)
        return {pr.number: pr for pr in prs if pr is not None}

    def build(self, tag: str):
        return gc.build_list(gc.Git(self.repo.path), self.pull_requests(), tag)

    def run_main(self, *argv: str, prs: list[dict] | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(gc, "fetch_pull_requests", return_value=list(self.prs if prs is None else prs)) as fetch,
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = gc.main(list(argv))
        self.fetch = fetch
        return code, out.getvalue(), err.getvalue()

    def body(self) -> str:
        return (self.repo.path / "release-body.md").read_text(encoding="utf-8")

    # -- reading a result
    @staticmethod
    def groups(result) -> dict[str, list[int]]:
        return {g: [e.number for e in v] for g, v in result.groups.items()}

    @staticmethod
    def direct(result) -> list[str]:
        return [d.subject for d in result.direct]

    @staticmethod
    def kept_out(result) -> tuple[list[int], list[int]]:
        return [c.number for c in result.carriers], [s.number for s in result.shipped]

    def bookkeeping(self, result) -> dict[str, str]:
        return {b.subject: b.reason for b in result.bookkeeping}


# --------------------------------------------------------------------------- #
# R1: the range
# --------------------------------------------------------------------------- #


class RangeTests(Fixture):
    def test_first_release_is_the_whole_history_and_lists_the_root_commit(self) -> None:
        r = self.repo
        r.write("README.md", "# example\n")
        root = r.commit("chore: initial commit")
        r.checkout("develop", new=True)
        self.squash(1, "feat: greet by name", {"app.py": "print('hello')\n"})
        r.checkout("main")
        r.merge("develop", "Release: develop → main for v0.1.0")
        r.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertIsNone(result.prev)
        self.assertEqual(result.commit_count, 3)
        self.assertEqual(self.groups(result), {"Features": [1]})
        self.assertEqual(
            result.render(),
            f"### Features\n\n- Greet by name (#1)\n\n### Direct commits\n\n- chore: initial commit ({root[:7]})",
        )

    def test_previous_tag_is_the_highest_below_by_its_three_numbers(self) -> None:
        r = self.repo
        for version in ("0.2.0", "0.9.0"):
            r.append("log.txt", f"{version}\n")
            r.commit(f"work before v{version}")
            r.tag(f"v{version}")
        r.append("log.txt", "next\n")
        r.commit("work before v0.10.0")
        r.git("tag", "v0.10.0-rc1")  # not vX.Y.Z: never a previous tag
        r.git("tag", "latest")
        r.append("log.txt", "more\n")
        r.commit("more work before v0.10.0")
        r.tag("v0.10.0")
        git = gc.Git(r.path)
        self.assertEqual(gc.previous_tag(git, "v0.10.0"), "v0.9.0")
        self.assertEqual(gc.previous_tag(git, "v0.9.0"), "v0.2.0")
        self.assertIsNone(gc.previous_tag(git, "v0.2.0"))
        result = self.build("v0.10.0")
        self.assertEqual(result.prev, "v0.9.0")
        self.assertEqual(self.direct(result), ["work before v0.10.0", "more work before v0.10.0"])


# --------------------------------------------------------------------------- #
# R2: the commits of a pull request
# --------------------------------------------------------------------------- #


class AttributionTests(Fixture):
    def setUp(self) -> None:
        super().setUp()
        self.repo.write("README.md", "# example\n")
        self.root = self.repo.commit("chore: initial commit")
        self.repo.checkout("develop", new=True)

    def test_squash_commit_is_its_pull_request_and_the_last_suffix_counts(self) -> None:
        self.squash(2, "feat: greet by name", {"a.py": "A = 1\n"})
        self.repo.write("b.py", "B = 1\n")
        sha = self.repo.commit("fix: after #2 (#2) (#3)\n\n* body", DEV, GH)
        self.prs.append(rest_pr(3, "fix: after #2 (#2)", sha))
        self.repo.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(self.groups(result), {"Features": [2], "Bug fixes": [3]})
        self.assertEqual(result.groups["Bug fixes"][0].line, "after #2 (#2)")
        self.assertEqual(result.groups["Features"][0].routes, ["squash"])

    def test_suffix_on_a_commit_github_did_not_make_is_not_believed(self) -> None:
        self.repo.write("g.py", "G = 1\n")
        sha = self.repo.commit("fix: tidy g (#99)")
        self.repo.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(self.groups(result), {})
        self.assertEqual(self.direct(result), ["chore: initial commit", "fix: tidy g (#99)"])
        self.assertIn(f"- fix: tidy g (#99) ({sha[:7]})", result.render())
        self.assertTrue(any("(#99)" in w and "neither made by GitHub" in w for w in result.warnings))

    def test_titled_real_merge_absorbs_its_commits_and_a_merge_of_develop(self) -> None:
        r = self.repo
        self.branch_commits("feature/report", [("report: skeleton", {"report.py": "def report(): ...\n"})])
        r.checkout("develop")
        self.squash(4, "docs: usage guide", {"docs/usage.md": "# Usage\n"})  # lands while #3 is open
        r.checkout("feature/report")
        r.merge("develop", "Merge branch 'develop' into feature/report")
        r.write("report.py", "def report():\n    return 'json'\n")
        r.commit("report: JSON output")
        self.real_merge(3, "feat: report command", "feature/report", "develop", body="Adds the report command.")
        r.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(self.groups(result), {"Features": [3], "Docs": [4]})
        self.assertEqual(self.direct(result), ["chore: initial commit"])
        entry = result.groups["Features"][0]
        self.assertEqual(entry.routes, ["merge-titled"])
        self.assertEqual(len(entry.own), 3)  # two branch commits and the merge of develop, absorbed
        self.assertEqual(result.bookkeeping, [])

    def test_merge_at_githubs_default_title_takes_the_title_github_records(self) -> None:
        self.branch_commits("fix-typo", [("correct the greeting typo", {"app.py": "print('Hello')\n"})])
        self.real_merge(5, "fix: correct the greeting typo", "fix-typo", "develop", titled=False,
                        api_title="fix: correct the greeting's typo")
        self.repo.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(self.groups(result), {"Bug fixes": [5]})
        self.assertEqual(result.groups["Bug fixes"][0].routes, ["merge-default-title"])
        self.assertIn("- Correct the greeting's typo (#5)", result.render())
        self.assertEqual(self.direct(result), ["chore: initial commit"])

    def test_a_merge_github_gives_no_title_for_takes_its_body_and_warns(self) -> None:
        self.branch_commits("fix-typo", [("correct the greeting typo", {"app.py": "print('Hello')\n"})])
        self.real_merge(5, "fix: correct the greeting typo", "fix-typo", "develop", titled=False)
        self.prs.clear()  # GitHub lists nothing
        self.repo.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertIn("- Correct the greeting typo (#5)", result.render())
        self.assertTrue(any("GitHub gives no title" in w for w in result.warnings))
        self.assertTrue(any("does not list as merged" in w for w in result.warnings))

    def test_a_commit_other_than_githubs_recorded_merge_commit_is_reported(self) -> None:
        self.squash(6, "feat: six", {"six.py": "6\n"})
        self.prs[-1]["merge_commit_sha"] = "0" * 40
        self.repo.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(self.groups(result), {"Features": [6]})
        self.assertTrue(any("claims #6, but GitHub records 0000000000" in w for w in result.warnings))


# --------------------------------------------------------------------------- #
# R2 (c) and R4: cherry-picks and pull requests already shipped
# --------------------------------------------------------------------------- #


class PickTests(Fixture):
    def setUp(self) -> None:
        super().setUp()
        r = self.repo
        r.write("README.md", "# example\n")
        r.commit("chore: initial commit")
        r.checkout("develop", new=True)
        self.squash(1, "feat: first", {"one.py": "1\n"})
        r.checkout("main")
        r.merge("develop", "Release: develop → main for v0.1.0")
        r.tag("v0.1.0")
        r.checkout("develop")

    def promote(self, tag: str) -> None:
        self.repo.checkout("main")
        self.repo.merge("develop", f"Release: develop → main for {tag}")
        self.repo.tag(tag)

    def test_a_pick_without_trailer_is_listed_in_the_hotfix_and_not_again(self) -> None:
        # conception-space #11 and #12: squashed into develop, copied onto the release line
        # minutes later without a trailer, promoted in the next release.
        r = self.repo
        s11 = self.squash(11, "fix: ensure the prebuilt is present", {"ci.sh": "prebuilt\n"})
        s12 = self.squash(12, "fix: pin yauzl", {"deps.txt": "yauzl==1\n"})
        r.checkout("main")
        r.pick(s11)
        r.pick(s12)
        r.tag("v0.1.1")
        hotfix = self.build("v0.1.1")
        self.assertEqual(self.groups(hotfix), {"Bug fixes": [11, 12]})
        self.assertEqual([e.routes for e in hotfix.groups["Bug fixes"]], [["cherry-pick (patch-id)"]] * 2)
        self.assertEqual([e.originals for e in hotfix.groups["Bug fixes"]], [[s11], [s12]])
        r.checkout("develop")
        self.squash(14, "feat: sign the build", {"sign.sh": "sign\n"})
        self.promote("v0.2.0")
        later = self.build("v0.2.0")
        self.assertEqual(self.groups(later), {"Features": [14]})
        self.assertEqual(self.kept_out(later), ([], [11, 12]))
        self.assertEqual(self.direct(later), [])

    def test_a_pick_with_its_trailer_is_recognised_by_the_trailer(self) -> None:
        s7 = self.squash(7, "fix: seven", {"seven.py": "7\n"})
        self.repo.checkout("main")
        self.repo.pick(s7, "-x")
        self.repo.tag("v0.1.1")
        result = self.build("v0.1.1")
        self.assertEqual(self.groups(result), {"Bug fixes": [7]})
        self.assertEqual(result.groups["Bug fixes"][0].routes, ["cherry-pick (trailer)"])

    def test_a_real_merge_picked_with_m1_is_listed_under_its_number(self) -> None:
        self.branch_commits("parser", [("parser: first edge case", {"a.py": "A = 2\n"}),
                                       ("parser: second edge case", {"c.py": "C = 1\n"})])
        merge = self.real_merge(2, "fix: parser edge cases", "parser", "develop")
        self.repo.checkout("main")
        self.repo.pick(merge, "-m", "1")
        self.repo.tag("v0.1.1")
        hotfix = self.build("v0.1.1")
        self.assertEqual(self.groups(hotfix), {"Bug fixes": [2]})
        self.assertEqual(self.direct(hotfix), [])
        self.promote("v0.2.0")
        later = self.build("v0.2.0")
        self.assertEqual(self.groups(later), {})
        self.assertEqual(self.kept_out(later), ([], [2]))
        self.assertEqual(self.direct(later), [])

    def test_a_real_merge_picked_commit_by_commit_is_not_listed_again(self) -> None:
        # D8, decision 9b: the picks are direct commits of the hotfix; the pull request
        # counts as shipped once each of its own commits has a patch-id there.
        e1, e2 = self.branch_commits("exporter", [("exporter: module", {"d.py": "D = 1\n"}),
                                                  ("exporter: wiring", {"e.py": "E = 1\n"})])
        self.real_merge(3, "feat: exporter", "exporter", "develop")
        self.repo.checkout("main")
        self.repo.pick(e1)
        self.repo.pick(e2)
        self.repo.tag("v0.1.1")
        hotfix = self.build("v0.1.1")
        self.assertEqual(self.groups(hotfix), {})
        self.assertEqual(self.direct(hotfix), ["exporter: module", "exporter: wiring"])
        self.promote("v0.2.0")
        later = self.build("v0.2.0")
        self.assertEqual(self.groups(later), {})
        self.assertEqual(self.kept_out(later), ([], [3]))
        self.assertIn("each of its 2 own commits has a patch-id", later.shipped[0].why)
        self.assertEqual(later.render(), "_No changes._")

    def test_a_real_merge_picked_only_in_part_is_listed_when_it_ships(self) -> None:
        e1, _ = self.branch_commits("exporter", [("exporter: module", {"d.py": "D = 1\n"}),
                                                 ("exporter: wiring", {"e.py": "E = 1\n"})])
        self.real_merge(3, "feat: exporter", "exporter", "develop")
        self.repo.checkout("main")
        self.repo.pick(e1)
        self.repo.tag("v0.1.1")
        self.promote("v0.2.0")
        later = self.build("v0.2.0")
        self.assertEqual(self.groups(later), {"Features": [3]})


# --------------------------------------------------------------------------- #
# R3: carriers
# --------------------------------------------------------------------------- #


class CarrierTests(Fixture):
    def test_promotions_and_back_merges_are_carriers_and_the_rest_is_listed(self) -> None:
        r = self.repo
        r.write("README.md", "# example\n")
        r.write("VERSION.txt", "1.0.0\n")
        root = r.commit("chore: initial commit")
        r.checkout("develop", new=True)
        self.squash(1, "feat: first", {"one.py": "1\n"})
        r.write("tool.cfg", "x = 1\n")
        lone = r.commit("tune the tool")  # a promotion that carries it must not swallow it (D7)
        # #2, a release promotion made as a pull request from develop into main
        self.real_merge(2, "Release v1.0.0", "develop", "main", titled=False, base="main", head="develop")
        r.tag("v1.0.0")
        first = self.build("v1.0.0")
        self.assertEqual(self.groups(first), {"Features": [1]})
        self.assertEqual(self.direct(first), ["chore: initial commit", "tune the tool"])
        self.assertEqual(self.kept_out(first), ([2], []))
        self.assertIn("carrier #2's merge: tree equals the automatic merge", self.bookkeeping(first)["Merge pull request #2 from example/develop"])
        self.assertIn(f"({lone[:7]})", first.render())
        self.assertIn(f"({root[:7]})", first.render())

        # #3, a back-merge from main; #4, the second proposal's back-merge branch
        r.checkout("develop")
        self.real_merge(3, "Back-merge main into develop", "main", "develop", titled=False, head="main")
        r.checkout("main")
        r.checkout("back-merge-v1.0.0", new=True)
        r.write("VERSION.txt", "1.0.1-dev\n")
        r.commit("chore: open 1.0.1-dev dev cycle")
        self.real_merge(4, "chore: back-merge v1.0.0", "back-merge-v1.0.0", "develop", head="back-merge-v1.0.0")
        # #5, a feature pull request into main (cogrind-workshop #1), merged at the default title
        r.checkout("main")
        self.branch_commits("ci-node24-action-pins", [("ci: bump action pins to Node 24", {"ci.yml": "node: 24\n"})])
        self.real_merge(5, "ci: bump action pins to Node 24", "ci-node24-action-pins", "main", titled=False, base="main")
        r.checkout("develop")
        # #6, from a fork whose head branch is named main; #7, from here, head back-merge-notes
        self.squash(6, "fix: typo from a fork", {"typo.md": "fixed\n"}, head="main", fork=True)
        self.squash(7, "docs: notes on back-merging", {"notes.md": "notes\n"}, head="back-merge-notes")
        r.checkout("main")
        r.merge("develop", "Release: develop → main for v1.1.0")
        r.tag("v1.1.0")
        later = self.build("v1.1.0")
        self.assertEqual(self.groups(later), {"Bug fixes": [6], "Docs": [7], "Maintenance": [5]})
        self.assertEqual(self.kept_out(later), ([3, 4], []))
        self.assertIn("- Bump action pins to Node 24 (#5)", later.render())
        # the carriers' own commit is examined on its own, and is bookkeeping by its content
        self.assertIn("chore: open 1.0.1-dev dev cycle", self.bookkeeping(later))
        self.assertEqual(self.direct(later), [])

    def test_a_carrier_merged_by_squash_is_left_out_with_a_warning(self) -> None:
        r = self.repo
        r.write("README.md", "# example\n")
        r.commit("chore: initial commit")
        r.write("app.py", "print('x')\n")
        r.commit("Release everything (#9)", DEV, GH)
        self.prs.append(rest_pr(9, "Release everything", r.head(), base="main", head="develop"))
        r.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(self.groups(result), {})
        self.assertEqual(self.kept_out(result), ([9], []))
        self.assertTrue(any("squash merge of carrier pull request #9" in w for w in result.warnings))
        self.assertEqual(self.direct(result), ["chore: initial commit"])

    def test_carrier_heads_and_forks(self) -> None:
        prs = {
            p.number: p
            for p in (
                gc.pull_request_from_rest(o)
                for o in (
                    rest_pr(1, "a", "1" * 40, head="develop", base="main"),
                    rest_pr(2, "b", "2" * 40, head="main"),
                    rest_pr(3, "c", "3" * 40, head="back-merge-v1.2.3"),
                    rest_pr(4, "d", "4" * 40, head="back-merge-notes"),
                    rest_pr(5, "e", "5" * 40, head="main", fork=True),
                    rest_pr(6, "f", "6" * 40, head="feature", base="main"),
                    rest_pr(7, "g", "7" * 40, head="back-merge-v1.2"),
                )
            )
        }
        r = self.repo
        r.write("README.md", "x\n")
        r.commit("init")
        history = gc.History(gc.Git(r.path), prs)
        self.assertEqual([n for n in sorted(prs) if history.is_carrier(n)], [1, 2, 3])


# --------------------------------------------------------------------------- #
# R5: bookkeeping and direct commits
# --------------------------------------------------------------------------- #


class BookkeepingTests(Fixture):
    def test_bookkeeping_is_recognised_by_content(self) -> None:
        r = self.repo
        r.write("CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n")
        r.commit("docs: start the changelog")  # a root commit that adds only CHANGELOG.md
        r.write("pyproject.toml", PYPROJECT.format(version="0.1.0.dev0", spec=">=2.31"))
        r.write("uv.lock", UVLOCK.format(version="0.1.0.dev0", spec=">=2.31"))
        r.commit("chore: scaffold the python app")
        r.write("pyproject.toml", PYPROJECT.format(version="0.1.0", spec=">=2.31"))
        r.write("uv.lock", UVLOCK.format(version="0.1.0", spec=">=2.31"))
        r.commit("release v0.1.0 (python)")
        r.write("web/package.json", PACKAGE_JSON.format(version="0.1.0"))  # not at the root: never a version file
        r.commit("chore: a nested web app")
        r.write("web/package.json", PACKAGE_JSON.format(version="0.1.1"))
        r.commit("bump the nested version")
        r.write("package.json", PACKAGE_JSON.format(version="0.1.0"))
        r.write("package-lock.json", PACKAGE_LOCK.format(version="0.1.0"))
        r.commit("chore: scaffold the web app")
        r.write("package.json", PACKAGE_JSON.format(version="0.2.0"))
        r.write("package-lock.json", PACKAGE_LOCK.format(version="0.2.0"))
        r.commit("release v0.2.0 (node)")
        r.write("Cargo.toml", CARGO_TOML.format(version="0.1.0"))
        r.write("Cargo.lock", CARGO_LOCK.format(version="0.1.0"))
        r.commit("chore: scaffold the rust crate")
        r.write("Cargo.toml", CARGO_TOML.format(version="0.3.0"))
        r.write("Cargo.lock", CARGO_LOCK.format(version="0.3.0"))
        r.commit("release v0.3.0 (rust)")
        r.write("VERSION.txt", "1.0.0-dev\n")
        r.commit("chore: add VERSION.txt")
        r.write("VERSION.txt", "1.0.0\n")
        r.append("CHANGELOG.md", "\nbumped\n")
        r.commit("release v1.0.0 (text), with the changelog")
        r.append("CHANGELOG.md", "\n## [v1.0.0] - 2026-09-17\n\n- entries\n")
        r.commit("docs(changelog): v1.0.0 [skip ci]", BOT, BOT)
        r.commit("chore: nothing at all", empty=True)
        r.write("pyproject.toml", PYPROJECT.format(version="0.1.0", spec=">=2.31,<3"))
        r.write("uv.lock", UVLOCK.format(version="0.1.0", spec=">=2.31,<3"))
        r.commit("build: cap requests below 3")
        r.checkout("side", new=True)
        r.write("f.py", "F = 1\n")
        r.commit("side: add f")
        r.checkout("main")
        r.merge("side", "Merge branch 'side'")  # clean
        r.checkout("edit", new=True)
        r.write("g.py", "G = 1\n")
        r.commit("edit: add g")
        r.checkout("main")
        r.git("merge", "-q", "--no-ff", "--no-commit", "edit")
        r.write("f.py", "F = 2  # changed inside the merge\n")
        r.git("add", "-A")
        edited = r.commit("Merge branch 'edit' with an edit of its own")
        r.tag("v1.0.0")

        result = self.build("v1.0.0")
        books = self.bookkeeping(result)
        self.assertTrue(books["docs: start the changelog"].startswith("changelog only"))
        self.assertEqual(books["release v0.1.0 (python)"],
                         "version only: pyproject.toml 0.1.0.dev0 -> 0.1.0; uv.lock own entry")
        self.assertEqual(books["release v0.2.0 (node)"],
                         "version only: package-lock.json 0.1.0 -> 0.2.0; package.json 0.1.0 -> 0.2.0")
        self.assertEqual(books["release v0.3.0 (rust)"],
                         "version only: Cargo.lock own entry; Cargo.toml 0.1.0 -> 0.3.0")
        self.assertEqual(books["release v1.0.0 (text), with the changelog"],
                         "version only: VERSION.txt 1.0.0-dev -> 1.0.0; CHANGELOG.md")
        self.assertTrue(books["docs(changelog): v1.0.0 [skip ci]"].startswith("changelog only"))
        self.assertEqual(books["chore: nothing at all"], "changes nothing: an empty commit")
        self.assertTrue(books["Merge branch 'side'"].startswith("merge: tree equals the automatic merge"))
        self.assertEqual(len(books), 8)
        self.assertEqual(
            self.direct(result),
            [
                "chore: scaffold the python app",
                "chore: a nested web app",
                "bump the nested version",
                "chore: scaffold the web app",
                "chore: scaffold the rust crate",
                "chore: add VERSION.txt",
                "build: cap requests below 3",
                "side: add f",
                "edit: add g",
                "Merge branch 'edit' with an edit of its own",
            ],
        )
        pin = next(d for d in result.direct if d.subject == "build: cap requests below 3")
        self.assertIn("a changed line is not a version line", pin.note)
        merge = next(d for d in result.direct if d.sha == edited)
        self.assertTrue(merge.merge)
        self.assertIn("differs from the automatic merge: f.py | 2 +-", merge.note)
        self.assertTrue(any(w.startswith(edited[:10]) and "f.py | 2 +-" in w for w in result.warnings))

    def test_a_version_file_added_or_another_value_changed_is_not_bookkeeping(self) -> None:
        r = self.repo
        r.write("README.md", "x\n")
        r.commit("init")
        r.write("pyproject.toml", PYPROJECT.format(version="0.1.0", spec=">=2.31"))
        r.commit("add the manifest")  # added: never version-only
        r.write("pyproject.toml", PYPROJECT.format(version="0.1.1", spec=">=2.31").replace("A synthetic app", "Renamed"))
        r.commit("bump, and a new description")
        r.write("uv.lock", UVLOCK.format(version="0.1.1", spec=">=2.31"))
        r.commit("add the lockfile")
        text = UVLOCK.format(version="0.1.1", spec=">=2.31").replace('version = "2.32.3"', 'version = "2.32.4"')
        r.write("uv.lock", text)
        r.commit("a dependency's version line")  # a version line, but not the project's own
        r.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(
            self.direct(result),
            ["init", "add the manifest", "bump, and a new description", "add the lockfile", "a dependency's version line"],
        )
        notes = {d.subject: d.note for d in result.direct}
        self.assertEqual(notes["bump, and a new description"], "pyproject.toml: a changed line is not a version line")
        self.assertEqual(notes["a dependency's version line"], "uv.lock: a value other than the project's own version changed")


# --------------------------------------------------------------------------- #
# R6 and R7: titles, groups and breaking changes
# --------------------------------------------------------------------------- #


class GroupTests(Fixture):
    def setUp(self) -> None:
        super().setUp()
        self.repo.write("README.md", "x\n")
        self.repo.commit("chore: initial commit")
        self.repo.checkout("develop", new=True)

    def test_every_type_and_the_titles_without_one(self) -> None:
        titles = [
            "feat: a feature", "fix: a fix", "perf: faster", "refactor: tidier", "docs: a guide", "test: more tests",
            "revert: undo a thing", "build: a build change", "chore: a chore", "ci: a workflow", "style: a format",
            "FEAT: in capitals", "feat(api): with a scope", "tools: an unknown type", "no type at all",
            'Revert "feat: a feature"', "fix:no blank after the colon",
        ]
        for n, title in enumerate(titles, start=1):
            self.squash(n, title, {f"f{n}.txt": f"{n}\n"})
        self.repo.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(
            result.render().split("\n\n### Direct commits")[0],
            textwrap.dedent("""\
                ### Features

                - A feature (#1)
                - In capitals (#12)
                - With a scope (#13)

                ### Bug fixes

                - A fix (#2)

                ### Performance

                - Faster (#3)

                ### Refactor

                - Tidier (#4)

                ### Docs

                - A guide (#5)

                ### Tests

                - More tests (#6)

                ### Reverts

                - Undo a thing (#7)

                ### Maintenance

                - A build change (#8)
                - A chore (#9)
                - A workflow (#10)
                - A format (#11)

                ### Other changes

                - Tools: an unknown type (#14)
                - No type at all (#15)
                - Revert "feat: a feature" (#16)
                - Fix:no blank after the colon (#17)"""),
        )

    def test_breaking_changes_by_bang_footer_branch_commit_and_body(self) -> None:
        r = self.repo
        self.squash(1, "feat!: rename the greeting API", {"a.py": "1\n"})
        self.squash(2, "fix: stricter input", {"b.py": "2\n"}, message_body="* stricter\n\nBREAKING CHANGE: rejects empty names")
        self.branch_commits("report", [("report: JSON output\n\nBREAKING-CHANGE: report() returns JSON text", {"r.py": "3\n"}),
                                       ("report: tests", {"t.py": "3\n"})])
        self.real_merge(3, "feat: report command", "report", "develop")
        self.squash(4, "refactor: new config format", {"c.py": "4\n"}, body="Notes.\n\nBREAKING CHANGE: the old format is gone")
        self.squash(5, "fix: not breaking", {"d.py": "5\n"},
                    message_body="mentions a breaking change: in prose\n  BREAKING CHANGE: indented, so not a footer",
                    body="breaking change: lower case")
        r.tag("v0.1.0")
        result = self.build("v0.1.0")
        self.assertEqual(self.groups(result), {"Breaking changes": [1, 2, 3, 4], "Bug fixes": [5]})
        reasons = {e.number: e.breaking for e in result.groups["Breaking changes"]}
        self.assertEqual(reasons[1], ["! in the title"])
        self.assertEqual(reasons[2], ["a BREAKING CHANGE footer in a commit message"])
        self.assertEqual(reasons[3], ["a BREAKING CHANGE footer in a commit message"])
        self.assertEqual(reasons[4], ["a BREAKING CHANGE footer in the pull request's body"])
        self.assertIn("### Breaking changes\n\n- Rename the greeting API (#1)\n- Stricter input (#2)", result.render())
        self.assertNotIn("### Features", result.render())  # listed once, under Breaking changes only

    def test_a_major_version_that_lists_nothing_breaking_is_reported(self) -> None:
        r = self.repo
        self.squash(1, "feat: one", {"a.py": "1\n"})
        r.tag("v1.0.0")
        self.assertFalse(any("major" in w for w in self.build("v1.0.0").warnings))  # never for a first release
        self.squash(2, "feat: two", {"b.py": "2\n"})
        r.tag("v2.0.0")
        self.assertIn("v2.0.0 raises the major version and lists no breaking change", self.build("v2.0.0").warnings)
        self.squash(3, "feat!: three", {"c.py": "3\n"})
        r.tag("v3.0.0")
        self.assertFalse(any("major" in w for w in self.build("v3.0.0").warnings))


# --------------------------------------------------------------------------- #
# The measurement's two synthetic histories (tests/acceptance/evidence/build_synthetic.py)
# --------------------------------------------------------------------------- #


class SyntheticHistoryTests(Fixture):
    def set_version(self, version: str, spec: str) -> None:
        self.repo.write("pyproject.toml", PYPROJECT.format(version=version, spec=spec))
        self.repo.write("uv.lock", UVLOCK.format(version=version, spec=spec))

    def test_main_scenario(self) -> None:
        r, spec = self.repo, ">=2.31"
        r.write("CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n")
        r.commit("docs: start the changelog")
        r.checkout("develop", new=True)
        self.set_version("0.1.0.dev0", spec)
        self.squash(1, "chore: scaffold the project", {"src/app.py": "def greet():\n    return 'hello'\n"})
        self.squash(2, "feat: greet by name", {"src/app.py": "def greet(name='world'):\n    return f'hello {name}'\n"})
        r.checkout("feature/report", new=True)
        r.write("src/report.py", "def report():\n    return 'report'\n")
        r.commit("report: skeleton")
        r.checkout("develop")
        self.squash(4, "docs: usage guide", {"docs/usage.md": "# Usage\n"})
        r.checkout("feature/report")
        r.merge("develop", "Merge branch 'develop' into feature/report")
        r.write("src/report.py", "import json\n\ndef report():\n    return json.dumps({'report': True})\n")
        r.commit("report: JSON output\n\nBREAKING CHANGE: report() now returns JSON text.")
        r.write("tests/test_report.py", "def test_report():\n    assert True\n")
        r.commit("report: tests")
        self.real_merge(3, "feat: report command", "feature/report", "develop", body="Adds the report command.")
        r.checkout("main")
        r.merge("develop", "Release: develop → main for v0.1.0")
        r.checkout("develop")
        six = self.squash(6, "fix: survive unicode names", {"src/unicode.py": "def safe(name):\n    return name\n"})
        r.checkout("main")
        r.pick(six)
        self.set_version("0.1.0", spec)
        r.commit("release v0.1.0")
        r.tag("v0.1.0")
        r.append("CHANGELOG.md", "\n## [v0.1.0]\n\n- entries\n")
        r.commit("docs(changelog): v0.1.0 [skip ci]", BOT, BOT)
        self.real_merge(8, "Back-merge main into develop", "main", "develop", titled=False, head="main")
        self.set_version("0.1.1.dev0", spec)
        r.commit("chore: open 0.1.1.dev0 dev cycle")
        self.branch_commits("fix-typo", [("correct the greeting typo",
                                          {"src/app.py": "def greet(name='world'):\n    return f'Hello, {name}'\n"})])
        self.real_merge(5, "fix: correct the greeting typo", "fix-typo", "develop", titled=False)
        self.squash(7, "feat!: rename the greeting API",
                    {"src/app.py": "def salute(name='world'):\n    return f'Hello, {name}'\n"})
        self.set_version("0.1.1.dev0", ">=2.31,<3")
        pin = r.commit("build: cap requests below 3")
        r.checkout("main")
        r.merge("develop", "Release: develop → main for v0.2.0")
        self.set_version("0.2.0", ">=2.31,<3")
        r.commit("release v0.2.0")
        r.tag("v0.2.0")

        first = self.build("v0.1.0")
        self.assertEqual(self.groups(first), {"Breaking changes": [3], "Features": [2], "Bug fixes": [6],
                                              "Docs": [4], "Maintenance": [1]})
        self.assertEqual((self.direct(first), self.kept_out(first)), ([], ([], [])))
        self.assertEqual(
            first.render(),
            "### Breaking changes\n\n- Report command (#3)\n\n### Features\n\n- Greet by name (#2)\n\n"
            "### Bug fixes\n\n- Survive unicode names (#6)\n\n### Docs\n\n- Usage guide (#4)\n\n"
            "### Maintenance\n\n- Scaffold the project (#1)",
        )
        second = self.build("v0.2.0")
        self.assertEqual(self.groups(second), {"Breaking changes": [7], "Bug fixes": [5]})
        self.assertEqual(self.direct(second), ["build: cap requests below 3"])
        self.assertEqual(self.kept_out(second), ([8], [6]))
        self.assertEqual(
            second.render(),
            "### Breaking changes\n\n- Rename the greeting API (#7)\n\n### Bug fixes\n\n- Correct the greeting typo (#5)"
            f"\n\n### Direct commits\n\n- build: cap requests below 3 ({pin[:7]})",
        )

    def test_extra_scenario_with_decision_9b(self) -> None:
        r, spec = self.repo, ">=2.31"
        r.write("CHANGELOG.md", "# Changelog\n")
        r.commit("docs: start the changelog")
        r.checkout("develop", new=True)
        self.set_version("1.0.0.dev0", spec)
        self.squash(1, "chore: scaffold", {"src/a.py": "A = 1\n", "src/b.py": "B = 1\n"})
        r.checkout("main")
        r.merge("develop", "Promote develop for v1.0.0")
        r.checkout("develop")
        self.branch_commits("parser", [("parser: first edge case", {"src/a.py": "A = 2\n"}),
                                       ("parser: second edge case", {"src/c.py": "C = 1\n"})])
        m2 = self.real_merge(2, "fix: parser edge cases", "parser", "develop")
        e1, e2 = self.branch_commits("exporter", [("exporter: module", {"src/d.py": "D = 1\n"}),
                                                  ("exporter: wiring", {"src/e.py": "E = 1\n"})])
        self.real_merge(3, "feat: exporter", "exporter", "develop")
        r.checkout("side", new=True)
        r.write("src/f.py", "F = 1\n")
        side = r.commit("side: add f")
        r.checkout("develop")
        r.git("merge", "-q", "--no-ff", "--no-commit", "side")
        r.write("src/b.py", "B = 2  # changed inside the merge\n")
        r.git("add", "-A")
        edited = r.commit("Merge branch 'side' into develop")
        r.write("src/g.py", "G = 1\n")
        tidy = r.commit("fix: tidy g (#99)")
        r.checkout("main")
        r.pick(m2, "-m", "1")
        p1, p2 = r.pick(e1), r.pick(e2)
        self.set_version("1.0.0", spec)
        r.commit("release v1.0.0")
        r.tag("v1.0.0")
        r.merge("develop", "Promote develop for v1.1.0")
        self.set_version("1.1.0", spec)
        r.commit("release v1.1.0")
        r.tag("v1.1.0")

        first = self.build("v1.0.0")
        self.assertEqual(
            first.render(),
            "### Bug fixes\n\n- Parser edge cases (#2)\n\n### Maintenance\n\n- Scaffold (#1)\n\n"
            f"### Direct commits\n\n- exporter: module ({p1[:7]})\n- exporter: wiring ({p2[:7]})",
        )
        second = self.build("v1.1.0")
        self.assertEqual(self.kept_out(second), ([], [2, 3]))  # the measurement listed #3 again; 9b does not
        self.assertEqual(
            second.render(),
            f"### Direct commits\n\n- side: add f ({side[:7]})\n- Merge branch 'side' into develop ({edited[:7]})\n"
            f"- fix: tidy g (#99) ({tidy[:7]})",
        )
        self.assertEqual(len(second.warnings), 2)
        self.assertIn("differs from the automatic merge: src/b.py | 2 +-", second.warnings[0])
        self.assertIn("ends in (#99)", second.warnings[1])


# --------------------------------------------------------------------------- #
# The Highlights paragraph
# --------------------------------------------------------------------------- #


class HighlightsInputTests(unittest.TestCase):
    def test_titles_first_then_the_bodies_sharing_what_remains(self) -> None:
        entries = [("#1", "#1 feat: short", "a short body"), ("#2", "#2 fix: long", "x" * 40_000),
                   ("abc1234", "abc1234 a direct commit", "y" * 40_000), ("#3", "#3 docs: no body", "")]
        text = gc.highlights_input(entries)
        self.assertLessEqual(len(text), gc.MAX_INPUT_CHARS)
        self.assertGreater(len(text), gc.MAX_INPUT_CHARS - 100)
        heads = "- #1 feat: short\n- #2 fix: long\n- abc1234 a direct commit\n- #3 docs: no body"
        self.assertTrue(text.startswith(heads + "\n\n--- #1\na short body\n\n--- #2\n"))
        self.assertLess(text.index("--- #2"), text.index("--- abc1234"))
        self.assertNotIn("--- #3", text)  # nothing to add
        second, third = text.split("\n\n--- #2\n")[1].split("\n\n--- abc1234\n")
        self.assertTrue(second.endswith(gc.SHORTENED) and third.endswith(gc.SHORTENED))
        self.assertLessEqual(abs(len(second) - len(third)), 1)

    def test_no_entry_is_lost_to_the_cap(self) -> None:
        # smalt-mcp v1.0.0: #16's text began beyond the old cap on the raw log
        entries = [(f"#{n}", f"#{n} feat: change {n}", "z" * 5_000) for n in range(1, 17)]
        entries[0] = ("#1", "#1 feat: change 1", "z" * 200_000)
        text = gc.highlights_input(entries)
        self.assertLessEqual(len(text), gc.MAX_INPUT_CHARS)
        self.assertIn("- #16 feat: change 16", text.split("\n\n--- ")[0])
        self.assertIn("--- #16\n" + "z" * 100, text)

    def test_titles_alone_beyond_the_cap_leave_no_bodies(self) -> None:
        entries = [(f"#{n}", f"#{n} " + "t" * 100, "body") for n in range(10)]
        text = gc.highlights_input(entries, cap=500)
        self.assertNotIn("---", text)
        self.assertEqual(text.count("\n") + 1, 10)

    def test_share(self) -> None:
        self.assertEqual(gc.share(100, [10, 200, 200]), [10, 45, 45])
        self.assertEqual(gc.share(1000, [10, 20]), [10, 20])
        self.assertEqual(gc.share(0, [10]), [0])


class HighlightsCallTests(Fixture):
    def setUp(self) -> None:
        super().setUp()
        r = self.repo
        r.write("README.md", "x\n")
        r.write("pyproject.toml", PYPROJECT.format(version="0.1.0", spec=">=2.31"))
        r.commit("chore: initial commit\n\nThe first files.")
        self.squash(1, "feat: greet by name", {"a.py": "1\n"}, body="Greets the person by name.")
        r.tag("v0.1.0")
        self.summary = self.tmp / "summary.md"
        os.environ["GITHUB_STEP_SUMMARY"] = str(self.summary)

    def call(self, stub: StubAnthropic | None, key: bool = True) -> tuple[int, str, str]:
        if key:
            os.environ["ANTHROPIC_API_KEY"] = "test-value-not-a-key"
        modules = {"anthropic": stub.module() if stub is not None else None}
        with mock.patch.dict(sys.modules, modules):
            return self.run_main("--mode=generate", "--tag", "v0.1.0", "--repo", str(self.repo.path))

    def paragraph(self) -> str:
        return self.body().split("### Highlights\n\n", 1)[1].split("\n\n", 1)[0]

    def test_a_successful_call(self) -> None:
        stub = StubAnthropic(answer("  A paragraph about greeting people by name.  "))
        code, _, _ = self.call(stub)
        self.assertEqual(code, 0)
        self.assertEqual(self.paragraph(), "A paragraph about greeting people by name.")
        self.assertEqual(len(stub.calls), 1)
        call = stub.calls[0]
        self.assertEqual(call["model"], "claude-opus-5")
        self.assertEqual(call["max_tokens"], 16_000)
        self.assertEqual(call["output_config"], {"effort": "high"})
        self.assertNotIn("fallbacks", call)
        self.assertNotIn("betas", call)
        self.assertNotIn("thinking", call)
        prompt = call["messages"][0]["content"]
        self.assertIn("Project: synth-app — A synthetic app", prompt)
        self.assertIn("This is the FIRST tagged release of synth-app.", prompt)
        self.assertIn("- #1 feat: greet by name\n- ", prompt)
        self.assertIn("--- #1\nGreets the person by name.", prompt)
        self.assertIn("The first files.", prompt)  # a direct commit's body
        self.assertIn("- Highlights: claude-opus-5", self.summary.read_text(encoding="utf-8"))

    def test_the_placeholder_without_a_key_and_no_call(self) -> None:
        stub = StubAnthropic(answer("never used"))
        code, _, _ = self.call(stub, key=False)
        self.assertEqual(code, 0)
        self.assertEqual(self.paragraph(), gc.PLACEHOLDER)
        self.assertEqual(stub.calls, [])
        self.assertIn("ANTHROPIC_API_KEY is not set", self.summary.read_text(encoding="utf-8"))

    def test_the_placeholder_after_a_failed_call(self) -> None:
        code, _, _ = self.call(StubAnthropic(error=RuntimeError("the service is overloaded")))
        self.assertEqual(code, 0)
        self.assertEqual(self.paragraph(), gc.PLACEHOLDER)
        self.assertIn("the Highlights call failed (RuntimeError: the service is overloaded)",
                      self.summary.read_text(encoding="utf-8"))
        self.assertIn("### Features\n\n- Greet by name (#1)", self.body())

    def test_the_placeholder_when_the_sdk_cannot_be_imported(self) -> None:
        code, _, _ = self.call(None)
        self.assertEqual(code, 0)
        self.assertEqual(self.paragraph(), gc.PLACEHOLDER)
        self.assertIn("the anthropic SDK cannot be imported", self.summary.read_text(encoding="utf-8"))

    def test_a_stop_at_max_tokens_gives_the_placeholder_and_a_warning(self) -> None:
        code, _, _ = self.call(StubAnthropic(answer("A paragraph that ran", stop="max_tokens")))
        self.assertEqual(code, 0)
        self.assertEqual(self.paragraph(), gc.PLACEHOLDER)
        self.assertNotIn("A paragraph that ran", self.body())  # a cut-off answer is never published
        summary = self.summary.read_text(encoding="utf-8")
        self.assertIn(
            "- the Highlights call stopped at max_tokens (16000); its paragraph was cut short, "
            "so the placeholder is used",
            summary,
        )
        self.assertIn("- Highlights: the placeholder", summary)
        self.assertNotIn("max_tokens", self.body())  # warnings never enter the notes

    def test_a_stop_at_max_tokens_with_no_text_gives_the_placeholder(self) -> None:
        self.call(StubAnthropic(answer(None, stop="max_tokens")))
        self.assertEqual(self.paragraph(), gc.PLACEHOLDER)
        self.assertIn("stopped at max_tokens (16000); it returned no text", self.summary.read_text(encoding="utf-8"))

    def test_a_refusal_gives_the_placeholder_and_a_warning(self) -> None:
        code, _, _ = self.call(StubAnthropic(answer("partial text", stop="refusal", category="cyber")))
        self.assertEqual(code, 0)
        self.assertEqual(self.paragraph(), gc.PLACEHOLDER)
        self.assertIn("the Highlights call was refused (stop_reason refusal, category cyber)",
                      self.summary.read_text(encoding="utf-8"))

    def test_an_empty_answer_gives_the_placeholder(self) -> None:
        self.call(StubAnthropic(answer("   ")))
        self.assertEqual(self.paragraph(), gc.PLACEHOLDER)
        self.assertIn("returned no text", self.summary.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The command line, the modes and the job summary
# --------------------------------------------------------------------------- #


class CommandLineTests(Fixture):
    def setUp(self) -> None:
        super().setUp()
        r = self.repo
        r.write("README.md", "x\n")
        r.write("package.json", PACKAGE_JSON.format(version="0.1.0"))
        r.commit("chore: initial commit")
        self.squash(1, "feat: greet by name", {"a.py": "1\n"})
        r.tag("v0.1.0")
        self.args = ("--tag", "v0.1.0", "--repo", str(r.path))

    def test_repo_from_another_directory(self) -> None:
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        with contextlib.chdir(elsewhere):
            code, _, err = self.run_main("--mode=generate", *self.args)
        self.assertEqual(code, 0, err)
        self.assertFalse((elsewhere / "release-body.md").exists())
        self.assertTrue(self.body().startswith("## [v0.1.0] - 2026-"))
        self.assertIn("- Greet by name (#1)", self.body())
        self.fetch.assert_called_once_with(SLUG)

    def test_repo_must_be_the_root_of_its_checkout(self) -> None:
        (self.repo.path / "sub").mkdir()
        code, _, err = self.run_main("--mode=generate", "--tag", "v0.1.0", "--repo", str(self.repo.path / "sub"))
        self.assertEqual(code, 2)
        self.assertIn("is not its root", err)
        code, _, err = self.run_main("--mode=generate", "--tag", "v0.1.0", "--repo", str(self.tmp))
        self.assertEqual(code, 2)
        self.assertIn("not a git checkout", err)

    def test_refusal_without_a_tag(self) -> None:
        code, _, err = self.run_main("--mode=generate", "--repo", str(self.repo.path))
        self.assertEqual(code, 2)
        self.assertIn("no tag", err)
        os.environ["GITHUB_REF"] = "refs/heads/main"  # jonobones' re-publish path runs on a branch ref
        code, _, err = self.run_main("--repo", str(self.repo.path))
        self.assertEqual(code, 2)
        self.assertIn("no tag", err)
        self.assertFalse((self.repo.path / "release-body.md").exists())

    def test_a_tag_that_is_not_a_release_or_does_not_exist(self) -> None:
        code, _, err = self.run_main("--mode=generate", "--tag", "0.1.0", "--repo", str(self.repo.path))
        self.assertEqual(code, 2)
        self.assertIn("is not a vX.Y.Z tag", err)
        code, _, err = self.run_main("--mode=generate", "--tag", "v9.9.9", "--repo", str(self.repo.path))
        self.assertEqual(code, 2)
        self.assertIn("no tag v9.9.9", err)

    def test_the_tag_of_a_tag_push(self) -> None:
        os.environ["GITHUB_REF"] = "refs/tags/v0.1.0"
        code, _, err = self.run_main("--mode=generate", "--repo", str(self.repo.path))
        self.assertEqual(code, 0, err)
        self.assertTrue(self.body().startswith("## [v0.1.0]"))

    def test_insert_run_twice_adds_one_section(self) -> None:
        self.assertEqual(self.run_main("--mode=generate", *self.args)[0], 0)
        code, out, _ = self.run_main("--mode=insert", "--repo", str(self.repo.path))
        self.assertEqual(code, 0)
        self.assertIn("added the section for v0.1.0", out)
        changelog = (self.repo.path / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(changelog.startswith(gc.CHANGELOG_SKELETON + "\n## [v0.1.0] - "))
        self.assertTrue(changelog.endswith("- Greet by name (#1)\n\n### Direct commits\n\n"
                                           f"- chore: initial commit ({self.repo.git('rev-list', '--max-parents=0', 'HEAD')[:7]})\n"))
        code, out, _ = self.run_main("--mode=insert", "--repo", str(self.repo.path))
        self.assertEqual(code, 0)
        self.assertIn("already holds a section for v0.1.0; nothing to do", out)
        self.assertEqual((self.repo.path / "CHANGELOG.md").read_text(encoding="utf-8"), changelog)
        self.fetch.assert_not_called()  # insert uses no network

    def test_insert_places_the_section_below_unreleased(self) -> None:
        existing = "# Changelog\n\nPreamble.\n\n## [Unreleased]\n\n## [v0.0.9] - 2026-01-01\n\n- old\n"
        (self.repo.path / "CHANGELOG.md").write_text(existing, encoding="utf-8")
        (self.repo.path / "release-body.md").write_text("## [v0.1.0] - 2026-09-18\n\n### Highlights\n\nNew.\n", encoding="utf-8")
        self.assertEqual(self.run_main("--mode=insert", "--repo", str(self.repo.path))[0], 0)
        self.assertEqual(
            (self.repo.path / "CHANGELOG.md").read_text(encoding="utf-8"),
            "# Changelog\n\nPreamble.\n\n## [Unreleased]\n\n## [v0.1.0] - 2026-09-18\n\n### Highlights\n\nNew.\n\n"
            "## [v0.0.9] - 2026-01-01\n\n- old\n",
        )

    def test_insert_without_a_body_or_with_another_tags_body(self) -> None:
        code, _, err = self.run_main("--mode=insert", "--repo", str(self.repo.path))
        self.assertEqual(code, 2)
        self.assertIn("run --mode=generate first", err)
        (self.repo.path / "release-body.md").write_text("## [v0.0.9] - 2026-01-01\n\nstale\n", encoding="utf-8")
        os.environ["GITHUB_REF"] = "refs/tags/v0.1.0"
        code, _, err = self.run_main("--mode=insert", "--repo", str(self.repo.path))
        self.assertEqual(code, 1)
        self.assertIn("holds the section for v0.0.9, not for v0.1.0", err)

    def test_both_generates_then_inserts(self) -> None:
        code, out, err = self.run_main(*self.args)
        self.assertEqual(code, 0, err)
        self.assertIn("wrote release-body.md", out)
        self.assertIn("added the section for v0.1.0", out)

    def test_reuse_committed_takes_the_section_on_main_and_makes_no_call(self) -> None:
        r = self.repo
        section = "## [v0.1.0] - 2026-09-17\n\n### Highlights\n\nThe committed paragraph.\n\n### Features\n\n- Greet by name (#1)\n"
        r.write("CHANGELOG.md", gc.CHANGELOG_SKELETON + "\n" + section)
        r.commit("docs(changelog): v0.1.0 [skip ci]", BOT, BOT)
        r.git("update-ref", "refs/remotes/origin/main", "HEAD")
        os.environ["ANTHROPIC_API_KEY"] = "test-value-not-a-key"
        stub = StubAnthropic(answer("a new paragraph"))
        with mock.patch.dict(sys.modules, {"anthropic": stub.module()}):
            code, out, err = self.run_main("--mode=generate", "--reuse-committed", *self.args)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.body(), section)
        self.assertEqual(stub.calls, [])
        self.fetch.assert_not_called()
        self.assertIn("already holds the section for v0.1.0", out)

    def test_reuse_committed_builds_afresh_when_main_has_no_section(self) -> None:
        self.repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
        code, _, err = self.run_main("--mode=generate", "--reuse-committed", *self.args)
        self.assertEqual(code, 0, err)
        self.fetch.assert_called_once()
        self.assertIn("- Greet by name (#1)", self.body())

    def test_a_failed_github_read_fails_the_run_and_names_the_cause(self) -> None:
        with (
            mock.patch.object(gc, "fetch_pull_requests", side_effect=gc.ChangelogError("reading the pull requests failed: HTTP 502")),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            code = gc.main(["--mode=generate", *self.args])
        self.assertEqual(code, 1)
        self.assertIn("HTTP 502", err.getvalue())
        self.assertFalse((self.repo.path / "release-body.md").exists())

    def test_the_job_summary(self) -> None:
        summary = self.tmp / "summary.md"
        os.environ["GITHUB_STEP_SUMMARY"] = str(summary)
        code, out, _ = self.run_main("--mode=generate", *self.args)
        self.assertEqual(code, 0)
        text = summary.read_text(encoding="utf-8")
        version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
        self.assertIn(f"- dev-tools: {version}", text)
        self.assertIn(f"- Repository: {SLUG}", text)
        self.assertIn("- Range: `v0.1.0 (the whole history)`, 2 commits", text)
        self.assertIn("### Listed pull requests\n\n- #1, Features: squash commit", text)
        self.assertIn("### Direct commits\n\n- ", text)
        self.assertIn("### Warnings\n\n- ANTHROPIC_API_KEY is not set", text)
        self.assertIn(f"generate-changelog {version} (dev-tools)", out)

    def test_the_report_is_fenced_off_from_workflow_commands_in_a_workflow(self) -> None:
        os.environ["GITHUB_ACTIONS"] = "true"
        self.repo.write("b.py", "2\n")
        self.repo.commit("chore: ::warning::not a command")  # a direct commit: its subject is in the report
        self.repo.git("tag", "-d", "v0.1.0")
        self.repo.tag("v0.1.0")
        code, out, _ = self.run_main("--mode=generate", *self.args)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        start = lines.index("::group::generate-changelog job summary")
        token = lines[start + 1].removeprefix("::stop-commands::")
        self.assertRegex(token, r"^[0-9a-f]{32}$")
        end = lines.index(f"::{token}::")
        self.assertEqual(lines[end + 1], "::endgroup::")
        self.assertTrue(any("::warning::not a command" in ln for ln in lines[start + 2:end]))


class GitHubReadTests(Fixture):
    """The read through gh, against a stand-in gh on PATH."""

    def fake_gh(self, output: str, status: int = 0) -> None:
        bindir = self.tmp / "bin"
        bindir.mkdir()
        (self.tmp / "gh-output").write_text(output, encoding="utf-8")
        gh = bindir / "gh"
        gh.write_text(f'#!/bin/sh\necho "$@" > "{self.tmp}/gh-args"\ncat "{self.tmp}/gh-output"\nexit {status}\n')
        gh.chmod(0o755)
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"

    def test_pages_are_read_and_unmerged_pull_requests_dropped(self) -> None:
        pages = [[rest_pr(1, "feat: one", "1" * 40), rest_pr(2, "closed unmerged", None, merged=False)],
                 [rest_pr(3, "fix: three", "3" * 40, head="main", fork=True)]]
        self.fake_gh("\n".join(json.dumps(p) for p in pages) + "\n")
        repo = gc.Repository(self.repo.path, SLUG)
        prs = gc.read_pull_requests(repo)
        self.assertEqual(sorted(prs), [1, 3])
        self.assertTrue(prs[1].same_repository)
        self.assertFalse(prs[3].same_repository)
        self.assertEqual(prs[3].head, "main")
        args = (self.tmp / "gh-args").read_text(encoding="utf-8").split()
        self.assertEqual(args, ["api", "--paginate", f"repos/{SLUG}/pulls?state=closed&per_page=100"])

    def test_a_failed_read_names_the_cause(self) -> None:
        self.fake_gh("HTTP 401: Bad credentials", status=1)
        with self.assertRaises(gc.ChangelogError) as ctx:
            gc.read_pull_requests(gc.Repository(self.repo.path, SLUG))
        self.assertIn("gh api exited 1", str(ctx.exception))
        self.assertIn("Bad credentials", str(ctx.exception))

    def test_a_deleted_fork_is_not_this_repository(self) -> None:
        obj = rest_pr(4, "feat: from a deleted fork", "4" * 40, head="main")
        obj["head"]["repo"] = None
        self.assertFalse(gc.pull_request_from_rest(obj).same_repository)

    def test_the_repository_is_read_from_origin_else_github_repository(self) -> None:
        self.repo.write("x", "x\n")
        self.repo.commit("x")
        self.assertEqual(gc.resolve_repository(str(self.repo.path)).slug, SLUG)  # GITHUB_REPOSITORY
        for url in ("git@github.com:Other/thing.git", "https://github.com/Other/thing", "ssh://git@github.com/Other/thing.git"):
            self.repo.git("remote", "remove", "origin") if url != "git@github.com:Other/thing.git" else None
            self.repo.git("remote", "add", "origin", url)
            self.assertEqual(gc.resolve_repository(str(self.repo.path)).slug, "Other/thing", url)
        self.repo.git("remote", "remove", "origin")
        del os.environ["GITHUB_REPOSITORY"]
        repo = gc.resolve_repository(str(self.repo.path))
        self.assertIsNone(repo.slug)
        with self.assertRaises(gc.ChangelogError) as ctx:
            gc.read_pull_requests(repo)
        self.assertIn("cannot tell which GitHub repository", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
