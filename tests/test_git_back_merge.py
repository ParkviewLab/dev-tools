# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The unit tests of scripts/git-back-merge.

Each case makes a release in temporary repositories (a bare origin, a clone that
made the history, and a clone with develop checked out, from which the command
runs) and a fake GitHub (tests/backmerge_support.py) whose pull-request merge
really merges into the bare origin's develop. The cases follow the design's
thirteen steps: the refusal before the switch, the wait for the release and the
acceptance of a changelog job repaired by hand, resumption, the rebuild when
develop moves, the two classes of conflict, the three version files, the dry
run, and the back-merge of a release picked onto main (a hotfix).
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

from backmerge_support import FIX_LINE_2, ReleasedRepo, Sandbox, rework_line_2, upgrade_twin

RELEASES_MD = """# Versioning & releases

## Cutting a release

Promote, bump, tag.

## After the release: the back-merge cascade (mandatory)

Merge main into develop and push:

    git -C ../<repo>-develop merge --no-ff main

## Development versioning

Open the next cycle.
"""

# releases.md as the design's handbook change leaves it: the cascade section
# renamed and rewritten, and the transition section added.
RELEASES_MD_TRANSITION = RELEASES_MD.replace(
    "## After the release: the back-merge cascade (mandatory)\n\nMerge main into develop and push:\n\n"
    "    git -C ../<repo>-develop merge --no-ff main\n",
    "## After the release: the back-merge pull request\n\nRun git back-merge.\n",
).replace(
    "## Development versioning",
    "## Until a repository has switched\n\nThe direct back-merge: git merge --no-ff main, then git dev-release --open."
    "\n\n## Development versioning")
RELEASES_MD_RENAMED_ONLY = RELEASES_MD_TRANSITION.split("## Until a repository has switched")[0] + "## Development versioning\n"
# releases.md with the back-merge pull request's section, whose text names
# `git merge --no-ff` too, and no transition section: under the name the section
# first had and under the one it has now, it never gives the direct back-merge.
RELEASES_MD_PR_SECTION = RELEASES_MD.replace(
    "## After the release: the back-merge cascade (mandatory)\n\nMerge main into develop and push:\n\n"
    "    git -C ../<repo>-develop merge --no-ff main\n",
    "## After the release: the back-merge pull request\n\nRun git back-merge, which builds the branch with"
    " `git merge --no-ff origin/main`.\n")
RELEASES_MD_LAST_STEP = RELEASES_MD_PR_SECTION.replace(
    "## After the release: the back-merge pull request", "## The release's last step: the back-merge pull request")


def exception(version: str) -> str:
    """The exception, the direct back-merge (the handbook's releases.md, "The release's last
    step: the back-merge pull request"), with its procedure, one text wherever a refusal of
    git back-merge names it: the owner ruled on 2026-09-26 that a refusal states its full
    repair. version is main's release version, to which the version lines are resolved."""
    return ("Nothing is pushed. Its back-merge is the exception, the direct back-merge (the handbook's"
            " releases.md, \"The release's last step: the back-merge pull request\"): in the develop"
            " worktree, bring main and develop up to date and run git merge --no-ff main;"
            f" resolve the version lines to main's release version, {version}, and every other conflict by"
            " hand; commit the merge; then, in a code repository, run git dev-release --open --direct, which"
            " writes the next placeholder and pushes both commits in one push, or, in a VERSION.txt repository,"
            " push develop. Where administrators are bound, switch enforce_admins off before that push and on"
            " again after it.")


class BackMergeCase(unittest.TestCase):

    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.handbook = self.sb.tmp / "handbook"
        (self.handbook / "docs").mkdir(parents=True)
        (self.handbook / "docs" / "releases.md").write_text(RELEASES_MD)

    def make(self, kind="pyproject", **kw):
        self.repo = ReleasedRepo(self.sb, kind, **kw)
        self.sb.set_gh_state(self.repo.gh_state())
        return self.repo

    def back_merge(self, *args, env=None, cwd=None):
        return self.sb.script("git-back-merge", *args, cwd=cwd or self.repo.dev,
                              env={"PARKVIEWLAB_HANDBOOK": str(self.handbook), **(env or {})})

    def make_layout(self):
        """The handbook's clone layout (docs/repo-layout.md, "Creating the layout"): a
        bare clone with core.bare unset and HEAD on develop, as a clone of a repository
        whose default branch is develop has it, beside the permanent worktrees
        <repo>-main and <repo>-develop. Returns the develop and main worktrees."""
        box = self.sb.tmp / "sim"
        box.mkdir()
        bare = box / "sim.git"
        self.sb.git(box, "clone", "-q", "--bare", str(self.repo.origin), str(bare))
        self.sb.git(bare, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
        self.sb.git(bare, "fetch", "-q", "origin")
        self.sb.git(bare, "config", "--unset", "core.bare")
        self.sb.git(bare, "symbolic-ref", "HEAD", "refs/heads/develop")
        for branch in ("main", "develop"):
            self.sb.git(bare, "worktree", "add", "-q", f"../sim-{branch}", branch)
            self.sb.git(bare, "branch", f"--set-upstream-to=origin/{branch}", branch)
        return box / "sim-develop", box / "sim-main"

    def origin(self, *args, check=True):
        return self.sb.git(self.repo.origin, *args, check=check)

    def out(self, r):
        return r.stdout + r.stderr

    def assertOk(self, r):
        self.assertEqual(r.returncode, 0, self.out(r))

    def assertRefused(self, r, fragment):
        self.assertEqual(r.returncode, 1, self.out(r))
        self.assertIn(fragment, self.out(r))

    def is_ancestor(self, a, b):
        return self.sb.run(["git", "merge-base", "--is-ancestor", a, b], self.repo.origin, check=False).returncode == 0

    def assertNoResidue(self):
        """No temporary worktree, no local back-merge branch, nothing left in TMPDIR."""
        wts = self.sb.git(self.repo.dev, "worktree", "list", "--porcelain")
        self.assertEqual(wts.count("worktree "), 1, wts)
        self.assertEqual(self.sb.git(self.repo.dev, "branch", "--list", "back-merge-*"), "")
        self.assertEqual(os.listdir(self.sb.tmp / "t"), [])

    def push_to_develop(self, name, text, message):
        r = self.repo
        r.g("fetch", "-q", "origin")
        r.g("switch", "-q", "develop")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        ReleasedRepo.edit(r.releaser, name, text)
        r.g("add", name)
        r.g("commit", "-q", "-m", message)
        r.g("push", "-q", "origin", "develop")


class HappyPaths(BackMergeCase):

    def test_pyproject_repository(self):
        r = self.make("pyproject")
        result = self.back_merge()
        self.assertOk(result)
        tip = self.origin("rev-parse", "develop")
        self.assertTrue(self.is_ancestor(r.tag_commit, tip))
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.2.dev0")
        self.assertEqual(self.origin("log", "-1", "--format=%s", tip),
                         "chore(release): back-merge main into develop after v0.1.1 (#7)")
        c = self.origin("rev-parse", tip + "^2")
        self.assertEqual(self.origin("log", "-1", "--format=%s", c), "chore: open 0.1.2.dev0 dev cycle")
        self.assertEqual(self.origin("log", "-1", "--format=%s", c + "^"), "Back-merge: main → develop after v0.1.1")
        self.assertEqual(self.origin("rev-parse", c + "^^2"), r.main_tip)
        self.assertEqual(sorted(self.origin("diff", "--name-only", c + "^", c).split()), ["pyproject.toml", "uv.lock"])
        st = self.sb.gh_state()
        self.assertEqual(len(st["prs"]), 1)
        pr = st["prs"][0]
        self.assertEqual((pr["title"], pr["base"], pr["labels"], pr["state"]),
                         ("chore(release): back-merge main into develop after v0.1.1", "develop",
                          ["release-bookkeeping"], "MERGED"))
        self.assertIn("release-bookkeeping", st["labels"])
        merges = [c for c in st["calls"] if c[:2] == ["pr", "merge"]]
        self.assertEqual(len(merges), 1)
        self.assertIn("--merge", merges[0])
        self.assertIn("--match-head-commit", merges[0])
        self.assertNotIn("--admin", merges[0])
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertEqual(self.sb.git(r.dev, "rev-parse", "develop"), tip)
        self.assertNoResidue()
        # a second run finds the back-merge landed
        again = self.back_merge()
        self.assertOk(again)
        self.assertIn("already an ancestor of origin/develop", again.stdout)
        self.assertEqual(len(self.sb.gh_state()["prs"]), 1)

    def test_package_json_repository(self):
        r = self.make("package")
        self.assertOk(self.back_merge())
        self.assertEqual(r.version_at("develop", cwd=r.origin), "3.5.2-dev0")
        lock = self.origin("show", "develop:package-lock.json")
        self.assertEqual(lock.count('"version": "3.5.2-dev0"'), 2)
        self.assertNoResidue()

    def test_real_sized_lockfile(self):
        # step 9's check reads the lockfile through pipelines; a real one's bulk
        # after the version line once made it exit 141 and refuse a clean branch
        r = self.make("package", lock_bulk=3000)
        self.assertOk(self.back_merge())
        self.assertEqual(r.version_at("develop", cwd=r.origin), "3.5.2-dev0")
        self.assertNoResidue()

    def test_version_txt_repository_takes_no_open_cycle_commit(self):
        r = self.make("version-txt")
        self.assertOk(self.back_merge())
        tip = self.origin("rev-parse", "develop")
        self.assertEqual(self.origin("log", "-1", "--format=%s", tip + "^2"), "Back-merge: main → develop after v0.23.1")
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.23.1")
        self.assertNoResidue()

    def test_no_feature_during_the_release(self):
        # develop is an ancestor of main: --no-ff must still make the merge
        r = self.make("pyproject", feature_during_release=False)
        self.assertOk(self.back_merge())
        tip = self.origin("rev-parse", "develop")
        self.assertEqual(self.origin("log", "-1", "--format=%s", tip + "^2^"), "Back-merge: main → develop after v0.1.1")

    def test_unprotected_develop(self):
        self.make("pyproject")
        self.sb.update_gh_state(protection=None)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("develop's protection cannot be read", result.stdout)

    def test_every_gh_call_names_the_repository(self):
        self.make("pyproject")
        self.assertOk(self.back_merge())
        st = self.sb.gh_state()
        # the one call before it is known: the origin here is a path, so gh repo view names it
        after = [repo for call, repo in zip(st["calls"], st["gh_repo"]) if call[:2] != ["repo", "view"]]
        self.assertEqual(set(after), {"ParkviewLab/sim"})

    def test_the_placeholder_is_written_without_a_sync(self):
        self.make("pyproject")
        log = self.sb.tmp / "uv.log"
        self.assertOk(self.back_merge(env={"FAKE_UV_LOG": str(log)}))
        self.assertEqual(log.read_text(), "UV_NO_SYNC=1\n")

    def test_a_failing_writer_is_reported_and_nothing_is_pushed(self):
        self.make("pyproject")
        result = self.back_merge(env={"FAKE_UV_FAIL": "1"})
        self.assertRefused(result, "writing the placeholder 0.1.2.dev0 failed")
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_pre_release_tag_is_not_taken_for_the_newest_release(self):
        r = self.make("pyproject")
        r.g("tag", "v0.2.0-rc.1", "origin/develop")
        r.g("push", "-q", "origin", "v0.2.0-rc.1")
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("v0.1.1 (", result.stdout)

    def test_a_worktree_left_on_the_branch_does_not_block_the_build(self):
        # as a run killed in step 11 leaves it, or a person opens it to look
        r = self.make("pyproject")
        self.sb.git(r.dev, "worktree", "add", "-q", "-b", "back-merge-v0.1.1", str(self.sb.tmp / "left"), "origin/develop")
        self.assertOk(self.back_merge())
        self.assertTrue(self.is_ancestor(r.tag_commit, "develop"))

    def test_the_command_deletes_its_branch_when_github_does_not(self):
        self.make("pyproject")
        self.sb.update_gh_state(delete_branch_on_merge=False)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("deleted back-merge-v0.1.1 on origin", result.stdout)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")

    def test_develop_without_a_version_file_is_refused(self):
        r = self.make("pyproject")
        r.g("fetch", "-q", "origin")
        r.g("switch", "-q", "develop")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.g("rm", "-q", "pyproject.toml", "uv.lock")
        r.g("commit", "-q", "-m", "chore: the version moves to Cargo.toml (#4)")
        r.g("push", "-q", "origin", "develop")
        self.assertRefused(self.back_merge(), "origin/develop has no version file")

    def test_open_working_branches_are_listed_and_not_merged_into(self):
        r = self.make("pyproject")
        r.g("push", "-q", "origin", f"{r.promoted}:refs/heads/feature-x")
        r.g("push", "-q", "origin", f"{r.promoted}:refs/heads/feature-y")
        st = self.sb.gh_state()
        st["prs"].append({"number": 4, "head": "feature-y", "base": "develop", "title": "feat: y",
                          "body": "", "labels": [], "state": "OPEN",
                          "url": "https://github.com/ParkviewLab/sim/pull/4"})
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("  feature-x\n", result.stdout)
        self.assertIn("  feature-y (#4)", result.stdout)
        self.assertEqual(self.origin("rev-parse", "feature-x"), r.promoted)

    def test_a_develop_worktree_with_local_changes_is_not_pulled(self):
        r = self.make("pyproject")
        (r.dev / "app.txt").write_text("a local edit\n")
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("has local changes; not pulled", result.stdout)

    def test_the_develop_worktree_is_fast_forwarded(self):
        r = self.make("pyproject")
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn(f"fast-forwarded {r.dev}\n", result.stdout)
        self.assertEqual(self.sb.git(r.dev, "rev-parse", "HEAD"), self.origin("rev-parse", "develop"))

    def test_in_the_handbook_layout_the_develop_worktree_is_fast_forwarded(self):
        # From a linked worktree, git lists the bare clone (core.bare unset, HEAD
        # develop) as a worktree on develop as well; it is not one, and is passed over.
        self.make("pyproject")
        develop_wt, _ = self.make_layout()
        result = self.back_merge(cwd=develop_wt)
        self.assertOk(result)
        self.assertIn(f"fast-forwarded {develop_wt}\n", result.stdout)
        self.assertNotIn("cannot change to", self.out(result))
        self.assertEqual(self.sb.git(develop_wt, "rev-parse", "HEAD"), self.origin("rev-parse", "develop"))

    def test_a_develop_worktree_whose_state_cannot_be_read_is_not_pulled(self):
        self.make("pyproject")
        develop_wt, main_wt = self.make_layout()
        before = self.sb.git(develop_wt, "rev-parse", "HEAD")
        (Path(self.sb.git(develop_wt, "rev-parse", "--git-dir")) / "index").write_bytes(b"not an index")
        result = self.back_merge(cwd=main_wt)
        self.assertOk(result)
        self.assertIn(f"cannot read the state of {develop_wt}; not pulled", result.stdout)
        self.assertEqual(self.sb.git(develop_wt, "rev-parse", "HEAD"), before)

    def test_a_required_check_whose_name_holds_a_comma(self):
        # a matrix job's check is named like "test (ubuntu-latest, 3.12)"
        self.make("pyproject")
        st = self.sb.gh_state()
        st["protection"]["contexts"] = ["no-version-change", "test (ubuntu-latest, 3.12)"]
        st["checks"]["result"] = {"no-version-change": "pass", "test (ubuntu-latest, 3.12)": "pass"}
        self.sb.set_gh_state(st)
        self.assertOk(self.back_merge())

    def test_dry_run_changes_nothing(self):
        r = self.make("pyproject")
        before = self.origin("for-each-ref", "--format=%(refname) %(objectname)")
        result = self.back_merge("--dry-run")
        self.assertOk(result)
        self.assertIn("(dry run)", result.stdout)
        self.assertIn("PASS", result.stdout)
        self.assertEqual(self.origin("for-each-ref", "--format=%(refname) %(objectname)"), before)
        self.assertEqual(self.sb.gh_state()["prs"], [])
        self.assertNoResidue()

    def test_a_dry_run_after_the_back_merge_has_landed_moves_nothing(self):
        # step 13 runs when the back-merge has landed; a dry run changes nothing on
        # this machine either, the develop worktree included
        r = self.make("pyproject")
        self.assertOk(self.back_merge())
        self.sb.git(r.dev, "reset", "-q", "--hard", "HEAD~1")
        before = self.sb.git(r.dev, "rev-parse", "HEAD")
        result = self.back_merge("--dry-run")
        self.assertOk(result)
        self.assertIn("already an ancestor of origin/develop", result.stdout)
        self.assertIn(f"(dry run) {r.dev} would be fast-forwarded\n", result.stdout)
        self.assertNotIn(f"fast-forwarded {r.dev}\n", result.stdout)
        self.assertEqual(self.sb.git(r.dev, "rev-parse", "HEAD"), before)


class TheRelease(BackMergeCase):

    def test_waits_for_the_release_run_to_start_and_finish(self):
        r = self.make("pyproject")
        st = self.sb.gh_state()
        st["runs"][0].update(appears_after=1, in_progress_polls=2)
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("has not started", result.stdout)
        self.assertIn("still running", result.stdout)
        self.assertGreaterEqual(self.sb.gh_state()["run_list_calls"], 4)

    def test_changelog_job_failed_and_repaired_by_hand_is_accepted(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["runs"][0].update(conclusion="failure", jobs=[{"name": "gate", "conclusion": "success"},
                                                         {"name": "changelog", "conclusion": "failure"}])
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("repaired by hand", result.stdout)

    def test_changelog_job_failed_without_a_release_is_refused(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["runs"][0].update(conclusion="failure", jobs=[{"name": "changelog", "conclusion": "failure"}])
        st["releases"] = []
        self.sb.set_gh_state(st)
        self.assertRefused(self.back_merge(), "has no GitHub Release")

    def test_another_failed_job_is_refused(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["runs"][0].update(conclusion="failure", jobs=[{"name": "gate", "conclusion": "failure"}])
        self.sb.set_gh_state(st)
        self.assertRefused(self.back_merge(), "concluded 'failure'")
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")

    def test_a_named_tag_that_is_not_mains_version_is_refused(self):
        self.make("pyproject")
        self.assertRefused(self.back_merge("v0.1.0"), "not v0.1.0's")

    def test_not_switched_quotes_the_handbook(self):
        self.make("pyproject")
        self.sb.update_gh_state(allow_merge_commit=False)
        result = self.back_merge()
        self.assertRefused(result, "does not allow merge commits")
        self.assertIn("After the release: the back-merge cascade", result.stderr)
        self.assertIn("git dev-release --open", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")

    def test_not_switched_quotes_the_transition_section_once_released(self):
        self.make("pyproject")
        (self.handbook / "docs" / "releases.md").write_text(RELEASES_MD_TRANSITION)
        self.sb.update_gh_state(allow_merge_commit=False)
        result = self.back_merge()
        self.assertRefused(result, "## Until a repository has switched")
        self.assertIn("git merge --no-ff main, then git dev-release --open", result.stderr)
        self.assertNotIn("After the release", result.stderr)
        self.assertNotIn("Run git back-merge", result.stderr)

    def test_not_switched_never_quotes_a_section_that_no_longer_gives_the_direct_back_merge(self):
        self.make("pyproject")
        (self.handbook / "docs" / "releases.md").write_text(RELEASES_MD_RENAMED_ONLY)
        self.sb.update_gh_state(allow_merge_commit=False)
        result = self.back_merge()
        self.assertRefused(result, 'the section "Until a repository has switched"')
        self.assertNotIn("Run git back-merge", result.stderr)

    def test_not_switched_never_quotes_the_pull_request_section(self):
        # only the heading handbook v0.27.0 released, matched exactly, is the
        # direct back-merge's
        self.make("pyproject")
        self.sb.update_gh_state(allow_merge_commit=False)
        for text in (RELEASES_MD_PR_SECTION, RELEASES_MD_LAST_STEP):
            (self.handbook / "docs" / "releases.md").write_text(text)
            result = self.back_merge()
            self.assertRefused(result, 'the section "Until a repository has switched"')
            self.assertNotIn("back-merge pull request", result.stderr)
            self.assertNotIn("merge --no-ff origin/main", result.stderr)

    def test_an_unreadable_merge_setting_is_not_taken_for_not_switched(self):
        # GitHub returns allow_merge_commit only to a caller with admin rights
        self.make("pyproject")
        self.sb.update_gh_state(admin=False)
        result = self.back_merge()
        self.assertRefused(result, "admin rights")
        self.assertNotIn("does not allow merge commits", result.stderr)


class Conflicts(BackMergeCase):

    def test_version_line_conflict_is_refused_before_merging(self):
        self.make("pyproject")
        r = self.repo
        r.g("fetch", "-q", "origin")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, "0.1.1.dev1")
        r.g("commit", "-q", "-am", "chore: dev build v0.1.1.dev1")
        r.g("push", "-q", "origin", "develop")
        result = self.back_merge()
        self.assertRefused(result, "the version-line repair")
        self.assertIn("0.1.1.dev1", result.stderr)
        self.assertIn("a version change reached develop outside the release flow", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_version_change_that_would_merge_cleanly_is_refused_all_the_same(self):
        # develop set during the release to main's own version: both sides move the
        # version lines alike, so the plain merge is clean, and step 7 refuses it all
        # the same, since the change is not the release flow's own; its message
        # claims no conflict
        self.make("pyproject")
        r = self.repo
        r.g("fetch", "-q", "origin")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, "0.1.1")
        r.g("commit", "-q", "-am", "chore: set develop's version to 0.1.1")
        r.g("push", "-q", "origin", "develop")
        clean = self.sb.run(["git", "merge-tree", "--write-tree", "--no-messages", "origin/develop", "origin/main"],
                            r.releaser, check=False)
        self.assertEqual(clean.returncode, 0, "the premise: the plain merge is clean")
        result = self.back_merge()
        self.assertRefused(result, "origin/develop's version is 0.1.1, but develop was promoted at 0.1.1.dev0:"
                                   " a version change reached develop outside the release flow, whether or not"
                                   " the merge would conflict. Repair it (the version-line repair; the handbook's"
                                   " releases.md, \"The release's last step: the back-merge pull request\"): one"
                                   " reviewed commit restoring develop's version lines (the version"
                                   " file and its lockfile) to 0.1.1.dev0, pushed to develop directly")
        self.assertNotIn("would conflict on", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_other_conflict_is_refused_and_cleaned_up(self):
        self.make("pyproject")
        self.push_to_develop("CHANGELOG.md", "# Changelog\n\nAn edit on develop during the release\n",
                             "docs: edit the changelog during the release (#4)")
        result = self.back_merge()
        self.assertRefused(result, "conflicts in: CHANGELOG.md")
        self.assertIn("the pull request that reconciles a conflict", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()


class Resumption(BackMergeCase):

    def failing_first_run(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["checks"]["result"]["test"] = "fail"
        self.sb.set_gh_state(st)
        first = self.back_merge()
        self.assertRefused(first, "required checks failed: 'test'")
        st = self.sb.gh_state()
        self.assertEqual(st["prs"][0]["state"], "OPEN")
        head = self.origin("rev-parse", "back-merge-v0.1.1")
        st["checks"]["result"]["test"] = "pass"
        self.sb.set_gh_state(st)
        self.assertNoResidue()
        return head

    def test_a_current_open_pull_request_is_resumed_not_rebuilt(self):
        head = self.failing_first_run()
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("current with origin/develop, and passes the check", result.stdout)
        st = self.sb.gh_state()
        self.assertEqual(len(st["prs"]), 1)
        self.assertEqual(st["prs"][0]["mergedHead"], head)

    def test_a_stale_open_pull_request_is_rebuilt_in_place(self):
        head = self.failing_first_run()
        self.push_to_develop("h.txt", "feature H\n", "feat: feature H (#5)")
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("is rebuilt from origin/develop", result.stdout)
        self.assertIn("force-pushed", result.stdout)
        st = self.sb.gh_state()
        self.assertEqual(len(st["prs"]), 1)
        self.assertNotEqual(st["prs"][0]["mergedHead"], head)
        self.assertTrue(self.is_ancestor(self.repo.tag_commit, "develop"))
        self.assertEqual(self.origin("show", "develop:h.txt"), "feature H")

    def test_a_head_updated_with_update_branch_is_rebuilt(self):
        # the settled point on step 6: the head contains develop, and only the check tells
        head = self.failing_first_run()
        self.push_to_develop("h.txt", "feature H\n", "feat: feature H (#5)")
        r = self.repo
        r.g("fetch", "-q", "origin")
        r.g("switch", "-q", "-C", "update-branch", "origin/back-merge-v0.1.1")
        r.g("merge", "-q", "--no-ff", "origin/develop", "-m", "Merge branch 'develop' into back-merge-v0.1.1")
        updated = r.g("rev-parse", "HEAD")
        r.g("push", "-q", "origin", "HEAD:refs/heads/back-merge-v0.1.1")
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("is rebuilt from origin/develop", result.stdout)
        self.assertIn("force-pushed", result.stdout)
        self.assertNotIn(self.sb.gh_state()["prs"][0]["mergedHead"], (head, updated))
        self.assertEqual(self.origin("show", "develop:h.txt"), "feature H")

    def test_a_head_with_an_extra_commit_is_rebuilt(self):
        self.failing_first_run()
        r = self.repo
        r.g("fetch", "-q", "origin")
        r.g("switch", "-q", "-C", "extra", "origin/back-merge-v0.1.1")
        ReleasedRepo.edit(r.releaser, "app.txt", "sneak\n")
        r.g("commit", "-q", "-am", "fix: sneak")
        extra = r.g("rev-parse", "HEAD")
        r.g("push", "-q", "origin", "HEAD:refs/heads/back-merge-v0.1.1")
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("is rebuilt from origin/develop", result.stdout)
        self.assertNotEqual(self.sb.gh_state()["prs"][0]["mergedHead"], extra)
        self.assertNotEqual(self.origin("show", "develop:app.txt"), "sneak")

    def test_merged_by_another_hand_while_the_checks_run(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["checks"]["merged_by_another_hand_on"] = 1
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("v0.1.1 has reached origin/develop while the checks ran", result.stdout)
        self.assertNotIn("rebuilding", result.stdout)
        st = self.sb.gh_state()
        self.assertEqual([c for c in st["calls"] if c[:2] == ["pr", "merge"]], [])
        self.assertEqual(st["prs"][0]["state"], "MERGED")
        self.assertTrue(self.is_ancestor(self.repo.tag_commit, "develop"))
        self.assertNoResidue()

    def test_a_merge_that_gh_reports_as_failed_after_it_landed(self):
        self.make("pyproject")
        self.sb.update_gh_state(merge_then_fail=True)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("gh reported a failure, but v0.1.1 has reached origin/develop", result.stdout)
        self.assertNotIn("rebuilding", result.stdout)
        self.assertEqual(self.sb.gh_state()["prs"][0]["state"], "MERGED")
        self.assertNoResidue()

    def test_a_forks_pull_request_of_the_same_name_is_left_alone(self):
        r = self.make("pyproject")
        st = self.sb.gh_state()
        st["prs"].append({"number": 5, "head": "back-merge-v0.1.1", "base": "develop", "title": "from a fork",
                          "body": "", "labels": [], "state": "OPEN", "fork": True, "forkHead": r.promoted,
                          "url": "https://github.com/ParkviewLab/sim/pull/5"})
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        prs = {p["number"]: p for p in self.sb.gh_state()["prs"]}
        self.assertEqual(prs[5]["state"], "OPEN")
        self.assertEqual(prs[7]["state"], "MERGED")

    def test_a_head_replaced_by_another_push_during_the_checks_is_rebuilt(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["checks"]["push_foreign_on"] = 1
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("changed outside git back-merge", result.stdout)
        self.assertIn("rebuilding (1 of 3)", result.stdout)
        self.assertEqual(self.origin("ls-tree", "--name-only", "develop", "foreign.txt"), "")
        self.assertNoResidue()

    def test_develop_moving_between_the_checks_and_the_merge_rebuilds(self):
        self.make("pyproject")
        self.sb.update_gh_state(move_develop_before_merge=1)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("develop has moved beyond #7's head; rebuilding (1 of 3)", result.stdout)
        self.assertEqual(self.origin("show", "develop:moved-at-merge.txt"), "moved-at-merge")

    def test_transient_gh_failures_while_polling_are_retried(self):
        self.make("pyproject")
        self.sb.update_gh_state(fail_once=["run list", "pr view"])
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("gh cannot list the workflow runs for v0.1.1; retrying", result.stdout)
        self.assertIn("gh cannot read #7; retrying", result.stdout)
        self.assertEqual(sorted(self.sb.gh_state()["failed_once"]), ["pr view", "run list"])

    def test_dry_run_with_an_open_pull_request_names_it_once(self):
        self.failing_first_run()
        result = self.back_merge("--dry-run")
        self.assertOk(result)
        self.assertIn("would push it, refresh #7, wait", result.stdout)

    def test_develop_moving_during_the_checks_rebuilds(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["checks"]["move_develop_on"] = [1]
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("rebuilding (1 of 3)", result.stdout)
        self.assertEqual(len(self.sb.gh_state()["prs"]), 1)
        self.assertEqual(self.origin("show", "develop:moved-1.txt"), "moved-1")
        self.assertNoResidue()

    def test_develop_moving_every_time_gives_up_after_three_rebuilds(self):
        self.make("pyproject")
        st = self.sb.gh_state()
        st["checks"]["move_develop_always"] = True
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertRefused(result, "rebuilt 3 times")
        self.assertEqual(self.sb.gh_state()["prs"][0]["state"], "OPEN")
        self.assertNoResidue()

    def test_a_refused_merge_leaves_the_pull_request_open(self):
        self.make("pyproject")
        self.sb.update_gh_state(refuse_merges=1)
        result = self.back_merge()
        self.assertRefused(result, "refused to merge")
        self.assertEqual(self.sb.gh_state()["prs"][0]["state"], "OPEN")

    def test_an_older_back_merge_pull_request_is_closed(self):
        r = self.make("pyproject")
        r.g("push", "-q", "origin", f"{r.promoted}:refs/heads/back-merge-v0.1.0")
        st = self.sb.gh_state()
        st["prs"].append({"number": 3, "head": "back-merge-v0.1.0", "base": "develop", "title": "old",
                          "body": "", "labels": ["release-bookkeeping"], "state": "OPEN",
                          "url": "https://github.com/ParkviewLab/sim/pull/3"})
        self.sb.set_gh_state(st)
        self.assertOk(self.back_merge())
        old = [p for p in self.sb.gh_state()["prs"] if p["number"] == 3][0]
        self.assertEqual(old["state"], "CLOSED")
        self.assertIn("Superseded by #7", old["closeComment"])


class PickedReleases(BackMergeCase):
    """A release picked onto main (a hotfix: the handbook's `git cherry-pick -m 1` of a
    pull request's merge on develop, then the bump and the tag, with no promotion)
    goes back into develop through the checked pull request like any other release:
    step 7 finds no promotion in the release's segment of main, and step 8 makes the
    merge from the tree that back-merge-check --merge-tree gives."""

    PICKED = "(a release picked onto main: the version lines taken from main)"

    def make_picked(self, kind="pyproject", fix=("fix.txt", "fix\n"), after_fix=None, **kw):
        r = self.make(kind, **kw)
        r.land_back_merge()
        r.hotfix(fix=fix, after_fix=after_fix)
        self.sb.set_gh_state(r.gh_state())
        return r

    def subject(self, rev):
        return self.origin("log", "-1", "--format=%s", rev)

    def blob(self, spec):
        """A blob's bytes, as git stores them (git's text output would lose a CR)."""
        return subprocess.run(["git", "cat-file", "blob", spec], cwd=self.repo.origin, env=self.sb.env,
                              capture_output=True, check=True).stdout

    def assertPicked(self, r, result, placeholder):
        """The back-merge landed; develop holds the merge M of develop and main, from the
        picked path, and, in a code repository, the open-cycle commit C on it."""
        self.assertOk(result)
        self.assertIn(f"{r.tag3} is a release picked onto main", result.stdout)
        self.assertIn(self.PICKED, result.stdout)
        self.assertNotIn("the version-line repair", self.out(result))
        self.assertNotIn("the pull request that reconciles a conflict", self.out(result))
        tip = self.origin("rev-parse", "develop")
        self.assertTrue(self.is_ancestor(r.tag3_commit, tip))
        head = self.origin("rev-parse", tip + "^2")
        m = self.origin("rev-parse", head + "^") if placeholder else head
        self.assertEqual(self.subject(m), f"Back-merge: main → develop after {r.tag3}")
        self.assertEqual(self.origin("log", "-1", "--format=%P", m).split(), [self.origin("rev-parse", tip + "^1"),
                                                                              r.main_tip])
        self.assertEqual(r.version_at(m, cwd=r.origin), r.v3)
        if placeholder:
            self.assertEqual(self.subject(head), f"chore: open {placeholder} dev cycle")
        self.assertEqual(r.version_at("develop", cwd=r.origin), placeholder or r.v3)
        pr = self.sb.gh_state()["prs"][0]
        self.assertEqual((pr["title"], pr["state"]),
                         (f"chore(release): back-merge main into develop after {r.tag3}", "MERGED"))
        self.assertNoResidue()
        return m, head

    def test_pyproject_with_uv_lock(self):
        # the lockfile's dependency twin stands at the project's version at the merge
        # base, and develop has upgraded it since; neither is the project's line
        r = self.make_picked("pyproject", lock_twin=True, after_fix=upgrade_twin)
        m, c = self.assertPicked(r, self.back_merge(), "0.1.3.dev0")
        self.assertEqual(sorted(self.origin("diff", "--name-only", m, c).split()), ["pyproject.toml", "uv.lock"])
        lock = self.origin("show", "develop:uv.lock")
        self.assertIn('name = "sim-app"\nversion = "0.1.3.dev0"\n', lock)
        self.assertIn('name = "twin"\nversion = "0.2.0"\n', lock)
        self.assertEqual(self.origin("show", "develop:fix.txt"), "fix")

    def test_package_json_with_package_lock_json(self):
        r = self.make_picked("package", lock_twin=True, after_fix=upgrade_twin)
        self.assertPicked(r, self.back_merge(), "3.5.3-dev0")
        lock = json.loads(self.origin("show", "develop:package-lock.json"))
        self.assertEqual((lock["version"], lock["packages"][""]["version"], lock["packages"]["node_modules/twin"]["version"]),
                         ("3.5.3-dev0", "3.5.3-dev0", "4.0.0"))

    def test_package_json_with_crlf_line_endings(self):
        r = self.make_picked("package", crlf=True)
        self.assertPicked(r, self.back_merge(), "3.5.3-dev0")
        for name in ("package.json", "package-lock.json"):
            raw = self.blob(f"develop:{name}")
            self.assertIn(b'"version": "3.5.3-dev0",\r\n', raw)
            self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), name)

    def test_version_txt(self):
        # only main has changed VERSION.txt since the merge base, so the automatic
        # merge is clean; step 7 no longer takes v0.23.1's promotion for this release's
        r = self.make_picked("version-txt")
        self.assertPicked(r, self.back_merge(), None)

    def assertTheException(self, result):
        """Refused, prescribing the exception, the direct back-merge (the handbook's
        releases.md, "The release's last step: the back-merge pull request"), with its
        procedure, for a hotfix's conflict: the pull request that reconciles a conflict
        would bring develop's newer work on those lines back to the hotfix's, and whether
        the conflict lies on a version line is not known."""
        self.assertRefused(result, exception(self.repo.v3))
        self.assertNotIn("Repair it (the pull request that reconciles a conflict", result.stderr)
        self.assertNotIn("the version-line repair", result.stderr)
        self.assertNotIn("lies elsewhere", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertEqual(self.sb.gh_state()["prs"], [])
        self.assertNoResidue()

    def test_another_tables_name_line_before_the_project_table(self):
        r = self.make_picked("pyproject", pyproject_head='[tool.x]\nname = "tooling"\n\n')
        self.assertPicked(r, self.back_merge(), "0.1.3.dev0")
        self.assertIn('name = "sim-app"\nversion = "0.1.3.dev0"\n', self.origin("show", "develop:uv.lock"))

    def test_a_conflict_is_refused_with_the_exception(self):
        # the pick changed a line that develop has changed again since
        self.make_picked("pyproject", fix=FIX_LINE_2, after_fix=rework_line_2)
        result = self.back_merge()
        self.assertIn("conflicts in: app.txt", result.stderr)
        self.assertTheException(result)

    def test_an_unreadable_version_on_develop_is_repaired_by_a_pull_request(self):
        # develop's version file cannot be parsed: the check gives no merge, and the
        # repair is develop's own, an ordinary pull request that fixes the file, then
        # git back-merge again; the exception is not prescribed
        def break_pyproject(repo):
            text = (repo.releaser / "pyproject.toml").read_text()
            (repo.releaser / "pyproject.toml").write_text(
                text.replace('requires-python = ">=3.11"', 'requires-python = ">=3.11'))
            repo.g("commit", "-q", "-am", "build: an unterminated string (#9)")
        self.make_picked("pyproject", after_fix=break_pyproject)
        result = self.back_merge()
        self.assertRefused(result, "Repair it: by an ordinary pull request into develop, make develop's version"
                           " readable again, set to the next-patch placeholder of the release at the merge base,"
                           " which the version guard passes as the repair of develop's version file; then run"
                           " git back-merge again.")
        self.assertIn("back-merge-check accepts no merge of origin/main into origin/develop for v0.1.2: for a release"
                      " picked onto main, develop's version cannot be read", result.stderr)
        self.assertNotIn(exception(self.repo.v3), result.stderr)
        self.assertNotIn("the version-line repair", result.stderr)

    def test_a_shallow_clone_is_refused_before_anything_is_compared(self):
        # at depth 4, step 7 read a shortened first-parent line of main and prescribed a
        # wrong version-line repair; the command now refuses a shallow repository at
        # step 1, as back-merge-check does
        r = self.make_picked("pyproject")
        shallow = self.sb.tmp / "shallow"
        self.sb.git(self.sb.tmp, "clone", "-q", "--depth", "4", "--no-single-branch", "--branch", "develop",
                    "file://" + str(r.origin), str(shallow))
        self.assertEqual(self.sb.git(shallow, "rev-parse", "--is-shallow-repository"), "true")
        result = self.back_merge("--dry-run", cwd=shallow)
        self.assertRefused(result, "shallow repository")
        self.assertIn("fetch the full history", result.stderr)
        self.assertNotIn("== 2.", result.stdout)
        self.assertNotIn("the version-line repair", result.stderr)
        self.assertNotIn("the pull request that reconciles a conflict", result.stderr)

    def test_an_error_of_the_check_is_reported_with_no_repair(self):
        # a git before 2.40 has no merge-tree --merge-base, so back-merge-check
        # --merge-tree exits 2: an error, which no repair of the history mends
        self.make_picked("pyproject")
        result = self.back_merge("--dry-run", env={"PATH": self.sb.path_with_git_2_39()})
        self.assertRefused(result, "back-merge-check --merge-tree could not run (exit 2)")
        self.assertIn("git 2.40 or later", result.stderr)
        self.assertNotIn("the direct back-merge", result.stderr)
        self.assertNotIn("the version-line repair", result.stderr)
        self.assertNotIn("the pull request that reconciles a conflict", result.stderr)
        self.assertNoResidue()

    def test_a_conflict_in_a_version_txt_repository_is_refused_with_the_exception(self):
        self.make_picked("version-txt", fix=FIX_LINE_2, after_fix=rework_line_2)
        result = self.back_merge()
        self.assertIn("conflicts in: app.txt", result.stderr)
        self.assertTheException(result)

    def test_more_than_one_merge_base_is_refused(self):
        # v0.1.2 promoted from a develop that did not yet hold v0.1.1's back-merge
        r = self.make("pyproject")
        r.g("fetch", "-q", "origin")
        feature_f = r.g("rev-parse", "origin/develop")
        r.land_back_merge()
        r.promote(feature_f, "0.1.2")
        r.hotfix(version="0.1.3")
        self.sb.set_gh_state(r.gh_state())
        result = self.back_merge()
        self.assertRefused(result, "2 merge bases")
        self.assertNotIn("the version-line repair", result.stderr)
        self.assertNotIn("the pull request that reconciles a conflict", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_dry_run_builds_and_checks_and_pushes_nothing(self):
        r = self.make_picked("pyproject")
        before = self.origin("for-each-ref", "--format=%(refname) %(objectname)")
        result = self.back_merge("--dry-run")
        self.assertOk(result)
        self.assertIn(self.PICKED, result.stdout)
        self.assertIn("PASS", result.stdout)
        self.assertEqual(self.origin("for-each-ref", "--format=%(refname) %(objectname)"), before)
        self.assertEqual(self.sb.gh_state()["prs"], [])
        self.assertNoResidue()

    def test_a_current_open_pull_request_is_resumed(self):
        r = self.make_picked("pyproject")
        st = self.sb.gh_state()
        st["checks"]["result"]["test"] = "fail"
        self.sb.set_gh_state(st)
        self.assertRefused(self.back_merge(), "required checks failed: 'test'")
        head = self.origin("rev-parse", "back-merge-v0.1.2")
        st = self.sb.gh_state()
        st["checks"]["result"]["test"] = "pass"
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("current with origin/develop, and passes the check", result.stdout)
        self.assertEqual(self.sb.gh_state()["prs"][0]["mergedHead"], head)
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.3.dev0")

    def test_develop_moving_during_the_checks_rebuilds(self):
        r = self.make_picked("pyproject")
        st = self.sb.gh_state()
        st["checks"]["move_develop_on"] = [1]
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("rebuilding (1 of 3)", result.stdout)
        self.assertEqual(result.stdout.count(self.PICKED), 2)
        self.assertEqual(self.origin("show", "develop:moved-1.txt"), "moved-1")
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.3.dev0")

    def test_a_promotion_not_yet_back_merged_is_seen_through_a_hotfix(self):
        # v0.1.1 is promoted and develop's version changes during it; before its
        # back-merge lands, v0.1.2 is picked onto main. Its back-merge brings v0.1.1's
        # promotion too, so step 7 refuses the version change, the version-line repair
        r = self.make("pyproject")
        r.g("fetch", "-q", "origin")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, "0.1.1.dev1")
        r.g("commit", "-q", "-am", "chore: dev build v0.1.1.dev1")
        r.g("push", "-q", "origin", "develop")
        r.hotfix()
        self.sb.set_gh_state(r.gh_state())
        result = self.back_merge()
        self.assertRefused(result, "origin/develop's version is 0.1.1.dev1, but develop was promoted at 0.1.1.dev0")
        self.assertIn("the version-line repair", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_first_release_whose_line_holds_pull_request_merges(self):
        # develop merged, by a real merge, a pull request cut before its dev cycle
        # opened, and main reached the first release by a fast-forward: that merge is on
        # main's first-parent line, but develop holds it, so it is no promotion to compare
        r = self.make("pyproject", first_release_by_fast_forward=True, early_merge=True)
        result = self.back_merge()
        self.assertOk(result)
        self.assertNotIn("the version-line repair", self.out(result))
        self.assertNotIn("the pull request that reconciles a conflict", self.out(result))
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.2.dev0")
        self.assertNoResidue()

    def repair_6a(self, version):
        """The version-line repair, carried out: one commit restoring develop's version
        lines (the version file and its lockfile) to version, pushed to develop directly."""
        r = self.repo
        r.g("fetch", "-q", "origin")
        r.g("switch", "-q", "develop")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, version)
        r.g("commit", "-q", "-am", f"chore: restore develop's version to {version} (the version-line repair)")
        r.g("push", "-q", "origin", "develop")

    def assertRepair6a(self, result, version):
        """Refused with the version-line repair, naming the version to restore, not the exception."""
        self.assertRefused(result, "Repair it (the version-line repair; the handbook's releases.md, \"The"
                                   " release's last step: the back-merge pull request\"): one reviewed commit"
                                   f" restoring develop's version lines (the version file and its lockfile) to {version},"
                                   " pushed to develop directly (with enforce_admins switched off and on again where"
                                   " administrators are bound); then run git back-merge again.")
        self.assertNotIn("the direct back-merge", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_first_release_reached_by_a_fast_forward_whose_version_changed(self):
        # develop re-pointed during a first release that main reached by a fast-forward:
        # the change is not the release flow's own. The merge base, where main was
        # fast-forwarded, is not at a release, so the version to restore is its own,
        # which makes the automatic merge clean
        r = self.make("pyproject", first_release_by_fast_forward=True)
        r.g("fetch", "-q", "origin")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, "0.2.0.dev0")
        r.g("commit", "-q", "-am", "chore: develop re-pointed to 0.2.0.dev0")
        r.g("push", "-q", "origin", "develop")
        result = self.back_merge()
        self.assertIn("the merge base's version must be a release X.Y.Z, and it is 0.1.1.dev0", result.stderr)
        self.assertRepair6a(result, "0.1.1.dev0")
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.2.0.dev0")
        self.repair_6a("0.1.1.dev0")
        again = self.back_merge()
        self.assertOk(again)
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.2.dev0")
        self.assertTrue(self.is_ancestor(r.tag_commit, "develop"))

    def test_develop_away_from_the_placeholder_its_back_merge_opened(self):
        # v0.1.1's back-merge opened 0.1.2.dev0, a dev build then committed 0.1.2.dev1,
        # and v0.1.2 was picked onto main: the version to restore is the placeholder
        r = self.make("pyproject")
        r.land_back_merge()
        r.g("fetch", "-q", "origin")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, "0.1.2.dev1")
        r.g("commit", "-q", "-am", "chore: dev build v0.1.2.dev1")
        r.g("push", "-q", "origin", "develop")
        r.hotfix()
        self.sb.set_gh_state(r.gh_state())
        result = self.back_merge()
        self.assertIn("develop's version must be 0.1.2.dev0, the next-patch placeholder of the merge base's 0.1.1,"
                      " and it is 0.1.2.dev1", result.stderr)
        self.assertRepair6a(result, "0.1.2.dev0")
        self.repair_6a("0.1.2.dev0")
        again = self.back_merge()
        self.assertOk(again)
        self.assertIn("(a release picked onto main: the version lines taken from main)", again.stdout)
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.3.dev0")
        self.assertTrue(self.is_ancestor(r.tag3_commit, "develop"))

    def test_a_first_release_reached_by_a_fast_forward(self):
        # no promotion commit, so it counts as picked; the automatic merge is clean,
        # and the back-merge is what it was
        r = self.make("pyproject", first_release_by_fast_forward=True)
        result = self.back_merge()
        self.assertOk(result)
        tip = self.origin("rev-parse", "develop")
        c = self.origin("rev-parse", tip + "^2")
        self.assertEqual(self.subject(c), "chore: open 0.1.2.dev0 dev cycle")
        self.assertEqual(self.subject(c + "^"), "Back-merge: main → develop after v0.1.1")
        self.assertEqual(self.origin("rev-parse", c + "^^2"), r.main_tip)
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.2.dev0")
        self.assertNoResidue()


class SeveralMergeBases(BackMergeCase):
    """Develop and main with more than one merge base: a release promoted from a develop
    commit that did not yet hold an earlier back-merge, or a hotfix branch merged onto
    main rather than picked. git back-merge refuses there only what back-merge-check
    refuses, naming the exception: a release picked onto main, and a release whose step
    7 comparison finds a version mismatch, where restoring develop's version would be
    the wrong repair. A release made by promotion whose versions agree is built with git
    merge --no-ff, as in v1.4.1, and the check passes it where its tree is the automatic
    merge."""

    EXCEPTION = exception("0.1.2")

    def subject(self, rev):
        return self.origin("log", "-1", "--format=%s", rev)

    def test_a_promotion_whose_versions_agree_lands(self):
        # develop holds v0.1.1's back-merge; then a feature D1 on develop, and a note
        # pushed to main, Y, which develop merges; v0.1.2 is promoted from D1, which does
        # not hold Y, so that Y and D1 are both merge bases; D1's version is develop's
        r = self.make("pyproject")
        r.land_back_merge()
        g = r.g
        g("fetch", "-q", "origin")
        g("merge", "-q", "--ff-only", "origin/develop")
        ReleasedRepo.edit(r.releaser, "d1.txt", "feature D1\n")
        g("add", "d1.txt")
        g("commit", "-q", "-m", "feat: feature D1 (#10)")
        d1 = g("rev-parse", "HEAD")
        g("push", "-q", "origin", "develop")
        g("switch", "-q", "main")
        g("merge", "-q", "--ff-only", "origin/main")
        ReleasedRepo.edit(r.releaser, "notes.txt", "a note\n")
        g("add", "notes.txt")
        g("commit", "-q", "-m", "docs: a note pushed to main")
        note = g("rev-parse", "HEAD")
        g("push", "-q", "origin", "main")
        g("switch", "-q", "develop")
        g("merge", "-q", "--no-ff", note, "-m", "Merge main's note into develop (#11)")
        g("push", "-q", "origin", "develop")
        r.promote(d1, "0.1.2")
        self.sb.set_gh_state(r.gh_state())
        self.assertEqual(len(self.origin("merge-base", "--all", "develop", "main").split()), 2)
        result = self.back_merge()
        self.assertOk(result)
        self.assertNotIn("merge bases", self.out(result))
        tip = self.origin("rev-parse", "develop")
        c = self.origin("rev-parse", tip + "^2")
        self.assertEqual(self.subject(c), "chore: open 0.1.3.dev0 dev cycle")
        self.assertEqual(self.subject(c + "^"), "Back-merge: main → develop after v0.1.2")
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.3.dev0")
        self.assertNoResidue()

    def test_a_picked_release_is_refused_with_the_exception(self):
        # a hotfix branch cut from develop's F, before v0.1.1's back-merge landed, merged
        # onto main rather than picked: v0.1.1's main commit and F are both merge bases,
        # and the merge's second parent is not develop's, so no promotion is found
        r = self.make("pyproject")
        g = r.g
        g("fetch", "-q", "origin")
        feature_f = g("rev-parse", "origin/develop")
        r.land_back_merge()
        g("switch", "-q", "-c", "hotfix-x", feature_f)
        ReleasedRepo.edit(r.releaser, "fix.txt", "fix\n")
        g("add", "fix.txt")
        g("commit", "-q", "-m", "fix: x")
        r.promote(g("rev-parse", "hotfix-x"), "0.1.2")
        self.sb.set_gh_state(r.gh_state())
        self.assertEqual(len(self.origin("merge-base", "--all", "develop", "main").split()), 2)
        result = self.back_merge()
        self.assertRefused(result, self.EXCEPTION)
        self.assertIn("v0.1.2 is a release picked onto main", result.stdout)
        self.assertIn("2 merge bases", result.stderr)
        self.assertNotIn("the version-line repair", result.stderr)
        self.assertNotIn("the pull request that reconciles a conflict", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_promotion_whose_version_changed_is_refused_with_the_exception(self):
        # v0.1.2 promoted from develop's F, before v0.1.1's back-merge moved develop to
        # 0.1.2.dev0: step 7 compares F's 0.1.1.dev0 with it, and restoring develop's
        # version, the version-line repair, would be wrong
        r = self.make("pyproject")
        r.g("fetch", "-q", "origin")
        feature_f = r.g("rev-parse", "origin/develop")
        r.land_back_merge()
        r.promote(feature_f, "0.1.2")
        self.sb.set_gh_state(r.gh_state())
        result = self.back_merge()
        self.assertRefused(result, self.EXCEPTION)
        self.assertIn("origin/develop's version is 0.1.2.dev0, but develop was promoted at 0.1.1.dev0", result.stderr)
        self.assertIn("2 merge bases", result.stderr)
        self.assertNotIn("the version-line repair", result.stderr)
        self.assertNotIn("the pull request that reconciles a conflict", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()


class ProjectVersion(BackMergeCase):
    """git back-merge reads a commit's version with _sot.sh's sot_read_at, which reads the
    project's own, as the version guard does: [project].version in pyproject.toml, the
    top-level "version" in package.json; a file that cannot be parsed is an error."""

    def test_another_tables_version_line_before_the_project_table(self):
        r = self.make("pyproject", pyproject_head='[tool.x]\nversion = "0.0.9"\n\n')
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("origin/develop carries v0.1.1; its version is 0.1.2.dev0", result.stdout)
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.2.dev0")
        self.assertIn('[tool.x]\nversion = "0.0.9"', self.origin("show", "develop:pyproject.toml"))

    def test_a_nested_version_before_the_top_level_one(self):
        # step 7 compares develop's version with the version it was promoted at
        r = self.make("package", package_nested_version=True)
        r.g("fetch", "-q", "origin")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, "3.5.1-dev1")
        r.g("commit", "-q", "-am", "chore: dev build v3.5.1-dev1")
        r.g("push", "-q", "origin", "develop")
        result = self.back_merge()
        self.assertRefused(result, "origin/develop's version is 3.5.1-dev1, but develop was promoted at 3.5.1-dev0")
        self.assertNoResidue()

    def test_an_unparseable_version_file_on_develop(self):
        self.make("pyproject")
        r = self.repo
        r.g("fetch", "-q", "origin")
        r.g("merge", "-q", "--ff-only", "origin/develop")
        text = (r.releaser / "pyproject.toml").read_text()
        (r.releaser / "pyproject.toml").write_text(text.replace('requires-python = ">=3.11"', 'requires-python = ">=3.11'))
        r.g("commit", "-q", "-am", "build: an unterminated string (#4)")
        r.g("push", "-q", "origin", "develop")
        result = self.back_merge()
        self.assertRefused(result, "pyproject.toml at origin/develop cannot be parsed")
        self.assertIn("cannot read the project's own version on origin/develop", result.stderr)
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_python3_without_tomllib_reads_through_uv(self):
        r = self.make("pyproject")
        shadow = self.sb.tmp / "no-tomllib"
        shadow.mkdir()
        (shadow / "tomllib.py").write_text("raise ImportError('no tomllib in this Python')\n")
        log = self.sb.tmp / "uv-run.log"
        self.assertOk(self.back_merge(env={"PYTHONPATH": str(shadow), "FAKE_UV_RUN_LOG": str(log)}))
        self.assertIn("run --no-project --quiet --python >=3.11\n", log.read_text())
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.2.dev0")


SHORT = {"GIT_BACK_MERGE_TIMEOUT": "4", "GIT_BACK_MERGE_POLL": "1"}


class OtherHands(BackMergeCase):
    """What a person, another run or a flaky GitHub can do while the command works."""

    def set_checks(self, **checks):
        st = self.sb.gh_state()
        st["checks"].update(checks)
        self.sb.set_gh_state(st)

    def test_a_pull_request_from_the_branch_into_main_is_never_adopted(self):
        r = self.make("pyproject")
        r.g("push", "-q", "origin", f"{r.promoted}:refs/heads/back-merge-v0.1.1")
        st = self.sb.gh_state()
        st["prs"].append({"number": 3, "head": "back-merge-v0.1.1", "base": "main", "title": "back-merge",
                          "body": "", "labels": [], "state": "OPEN",
                          "url": "https://github.com/ParkviewLab/sim/pull/3"})
        self.sb.set_gh_state(st)
        main_before = self.origin("rev-parse", "main")
        self.assertOk(self.back_merge())
        self.assertEqual(self.origin("rev-parse", "main"), main_before)
        self.assertTrue(self.is_ancestor(r.tag_commit, "develop"))
        prs = {p["number"]: p for p in self.sb.gh_state()["prs"]}
        self.assertEqual((prs[3]["state"], prs[7]["base"], prs[7]["state"]), ("OPEN", "develop", "MERGED"))

    def test_a_pull_request_closed_by_another_hand_stops_the_run(self):
        self.make("pyproject")
        self.set_checks(closed_by_another_hand_on=1)
        result = self.back_merge()
        self.assertRefused(result, "#7 reads 'CLOSED'")
        self.assertIn("opens a new pull request", result.stderr)
        self.assertNoResidue()
        # a second run opens a new one
        self.set_checks(closed_by_another_hand_on=None)
        self.assertOk(self.back_merge())
        prs = {p["number"]: p["state"] for p in self.sb.gh_state()["prs"]}
        self.assertEqual(prs, {7: "CLOSED", 8: "MERGED"})

    def test_a_closed_pull_request_is_not_rebuilt_when_develop_moves(self):
        self.make("pyproject")
        self.set_checks(closed_by_another_hand_on=1, move_develop_on=[1])
        result = self.back_merge()
        self.assertRefused(result, "no longer open")
        self.assertNotIn("force-pushed", result.stdout)
        self.assertEqual(self.origin("rev-parse", "back-merge-v0.1.1"), self.sb.gh_state()["prs"][0]["closedHead"])

    def test_a_branch_deleted_on_origin_stops_the_run(self):
        self.make("pyproject")
        self.set_checks(delete_branch_on=1, move_develop_on=[1])
        result = self.back_merge()
        self.assertRefused(result, "no longer open")
        self.assertEqual(self.origin("branch", "--list", "back-merge-*"), "")
        self.assertNoResidue()

    def test_a_push_between_the_checks_and_the_merge_rebuilds(self):
        self.make("pyproject")
        self.sb.update_gh_state(push_foreign_before_merge=1)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("changed outside git back-merge before the merge; rebuilding (1 of 3)", result.stdout)
        self.assertEqual(self.origin("ls-tree", "--name-only", "develop", "foreign-at-merge.txt"), "")

    def test_a_failed_state_read_after_the_merge_is_retried(self):
        self.make("pyproject")
        self.sb.update_gh_state(fail_state_view=1)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("merged #7", result.stdout)

    def test_merged_by_another_hand_while_a_check_fails(self):
        self.make("pyproject")
        self.sb.update_gh_state(protection=None)
        st = self.sb.gh_state()
        st["checks"].update(merged_by_another_hand_on=1, pending_polls=1)
        st["checks"]["result"]["lint"] = "fail"
        self.sb.set_gh_state(st)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("has reached origin/develop while the checks ran", result.stdout)

    def test_a_transient_failure_of_the_protection_read_is_retried(self):
        self.make("pyproject")
        self.sb.update_gh_state(fail_once=["api repos/ParkviewLab/sim/branches/develop/protection"],
                                move_develop_before_merge=1)
        result = self.back_merge()
        self.assertOk(result)
        self.assertIn("gh cannot read develop's protection (HTTP 502: Bad Gateway); retrying", result.stdout)
        self.assertNotIn("develop is unprotected", result.stdout)
        self.assertIn("rebuilding (1 of 3)", result.stdout)

    def test_a_persistent_gh_pr_checks_error_is_shown(self):
        self.make("pyproject")
        self.sb.update_gh_state(checks_error="HTTP 401: Bad credentials")
        result = self.back_merge(env=SHORT)
        self.assertRefused(result, "timed out waiting for #7's checks")
        self.assertIn("(gh pr checks: HTTP 401: Bad credentials)", result.stdout + result.stderr)

    def test_the_repository_is_named_from_origins_url(self):
        # gh repo view with no argument would name gh's base repository, which prefers upstream
        r = self.make("pyproject")
        self.assertOk(self.back_merge())
        views = [c for c in self.sb.gh_state()["calls"] if c[:2] == ["repo", "view"]]
        self.assertEqual(views[0][2], str(r.origin))

    def test_a_lagging_head_is_not_taken_for_a_foreign_push(self):
        self.make("pyproject")
        self.sb.update_gh_state(view_lag=2)
        self.set_checks(move_develop_on=[1])
        result = self.back_merge()
        self.assertOk(result)
        self.assertNotIn("outside git back-merge", result.stdout)
        self.assertTrue(self.sb.gh_state().get("lagged_reads"))

    def test_a_foreign_push_seen_through_a_lagging_head_rebuilds_once(self):
        self.make("pyproject")
        self.sb.update_gh_state(view_lag=2)
        self.set_checks(push_foreign_on=1)
        result = self.back_merge()
        self.assertOk(result)
        self.assertEqual(result.stdout.count("outside git back-merge"), 1)

    def test_a_dry_run_does_not_wait_on_a_failing_gh(self):
        self.make("pyproject")
        self.sb.update_gh_state(fail_once=["run list"])
        result = self.back_merge("--dry-run", env={"GIT_BACK_MERGE_POLL": "30"})
        self.assertOk(result)
        self.assertIn("(dry run) gh cannot list the workflow runs for v0.1.1; not waiting", result.stdout)


if __name__ == "__main__":
    unittest.main()
