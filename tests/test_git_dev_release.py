# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The unit tests of scripts/git-dev-release.

Both of its behaviours, as the design of real merges sets them out: in a
repository that does not allow merge commits and whose dev-release.yml declares
no `kind` input, it commits, pushes and dispatches as before, --open included;
where the workflow declares the input, it dispatches with it and commits nothing.
Once merge commits are allowed, develop takes no direct push, so --open and a dev
build without the input are refused, except that --open --direct opens the cycle by
a direct push after the exception's direct back-merge, carrying its merge commit in
the same push, and only on a develop at the version of main's newest release and
holding its commit, which that merge leaves. A VERSION.txt repository has no dev build.
"""

from __future__ import annotations

import unittest

from backmerge_support import ReleasedRepo, Sandbox

WF_NO_INPUT = (
    "name: Dev release\n\non:\n  workflow_dispatch:\n\npermissions:\n  contents: read\n\n"
    "jobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo gate\n"
)
WF_KIND = (
    "name: Dev release\n\non:\n  workflow_dispatch:\n    inputs:\n      kind:\n"
    "        description: The release this build heads toward\n        type: choice\n"
    "        options: [patch, minor, major]\n        default: patch\n\n"
    "jobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo gate\n"
)
WF_KIND_SECOND_INPUT = WF_KIND.replace("    inputs:\n", "    inputs:\n      verbose:\n        type: boolean\n")
WF_KIND_QUOTED_ON = WF_KIND.replace("\non:\n", '\n"on":\n')
WF_KIND_SINGLE_QUOTED = WF_KIND.replace("\non:\n", "\n'on':\n").replace("      kind:\n", "      'kind':\n")
WF_KIND_IN_A_JOB = WF_NO_INPUT.replace("    runs-on: ubuntu-latest\n",
                                       "    runs-on: ubuntu-latest\n    env:\n      kind: patch\n")
WF_KIND_NESTED = WF_NO_INPUT.replace("  workflow_dispatch:\n",
                                     "  workflow_dispatch:\n    inputs:\n      target:\n        kind: patch\n")
# GitHub's answer to a direct push to develop where its protection binds administrators
GH006_HOOK = """#!/bin/sh
while read old new ref; do
  if [ "$ref" = refs/heads/develop ]; then
    echo "error: GH006: Protected branch update failed for refs/heads/develop." >&2
    echo "error: Changes must be made through a pull request." >&2
    exit 1
  fi
done
exit 0
"""


class DevReleaseCase(unittest.TestCase):

    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)

    def make(self, kind="pyproject", workflow=WF_NO_INPUT, allow_merge_commit=False):
        self.repo = r = ReleasedRepo(self.sb, kind)
        if workflow is not None:
            r.g("fetch", "-q", "origin")
            r.g("switch", "-q", "develop")
            r.g("merge", "-q", "--ff-only", "origin/develop")
            (r.releaser / ".github" / "workflows" / "dev-release.yml").write_text(workflow)
            r.g("add", ".github/workflows/dev-release.yml")
            r.g("commit", "-q", "-m", "ci: the dev-release workflow (#3)")
            r.g("push", "-q", "origin", "develop")
            self.sb.git(r.dev, "pull", "-q", "--ff-only")
        self.sb.set_gh_state(r.gh_state(allow_merge_commit=allow_merge_commit))
        self.develop_before = self.sb.git(r.origin, "rev-parse", "develop")
        return r

    def dev_release(self, *args):
        return self.sb.script("git-dev-release", *args, cwd=self.repo.dev)

    def out(self, r):
        return r.stdout + r.stderr

    def dispatches(self):
        return self.sb.gh_state().get("dispatches", [])

    def assertDevelopUnchanged(self):
        self.assertEqual(self.sb.git(self.repo.origin, "rev-parse", "develop"), self.develop_before)


class BeforeTheSwitch(DevReleaseCase):

    def test_dev_build_commits_pushes_and_dispatches_as_before(self):
        r = self.make()
        res = self.dev_release("patch")
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.1.dev1")
        self.assertEqual(self.sb.git(r.origin, "log", "-1", "--format=%s", "develop"), "chore: dev build v0.1.1.dev1")
        self.assertEqual(self.dispatches(), [{"workflow": "dev-release.yml", "ref": "develop", "fields": []}])

    def test_open_commits_and_pushes_as_before(self):
        r = self.make()
        res = self.dev_release("--open")
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertEqual(self.sb.git(r.origin, "log", "-1", "--format=%s", "develop"), "chore: open 0.1.1.dev1 dev cycle")
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.1.dev1")
        self.assertEqual(self.dispatches(), [])

    def test_open_with_direct_is_open_before_the_switch(self):
        # in a repository that has not switched, --direct changes nothing
        r = self.make()
        res = self.dev_release("--open", "--direct")
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertEqual(self.sb.git(r.origin, "log", "-1", "--format=%s", "develop"), "chore: open 0.1.1.dev1 dev cycle")
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.1.dev1")
        self.assertEqual(self.dispatches(), [])

    def test_a_local_tag_that_differs_from_origins_does_not_stop_it(self):
        r = self.make()
        self.sb.git(r.dev, "tag", "-f", "-a", "v0.1.0", "-m", "a local tag, not origin's", "develop")
        res = self.dev_release("patch")
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.1.dev1")

    def test_dry_run_changes_nothing(self):
        self.make()
        res = self.dev_release("--dry-run", "patch")
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertIn("(dry run)", res.stdout)
        self.assertDevelopUnchanged()
        self.assertEqual(self.dispatches(), [])


class TheKindInput(DevReleaseCase):

    def assertDispatchedWith(self, kind, res):
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertEqual(self.dispatches(), [{"workflow": "dev-release.yml", "ref": "develop", "fields": [f"kind={kind}"]}])
        self.assertDevelopUnchanged()

    def test_dispatches_with_the_input_and_commits_nothing(self):
        self.make(workflow=WF_KIND)
        res = self.dev_release("minor")
        self.assertDispatchedWith("minor", res)
        self.assertIn("0.2.0.devN", res.stdout)

    def test_the_same_after_the_switch(self):
        self.make(workflow=WF_KIND, allow_merge_commit=True)
        self.assertDispatchedWith("patch", self.dev_release("patch"))

    def test_package_json_names_the_semver_form(self):
        self.make("package", workflow=WF_KIND)
        res = self.dev_release("patch")
        self.assertDispatchedWith("patch", res)
        self.assertIn("3.5.2-devN", res.stdout)

    def test_kind_among_other_inputs(self):
        self.make(workflow=WF_KIND_SECOND_INPUT)
        self.assertDispatchedWith("patch", self.dev_release("patch"))

    def test_quoted_on_key(self):
        self.make(workflow=WF_KIND_QUOTED_ON)
        self.assertDispatchedWith("patch", self.dev_release("patch"))

    def test_single_quoted_keys(self):
        self.make(workflow=WF_KIND_SINGLE_QUOTED)
        self.assertDispatchedWith("patch", self.dev_release("patch"))

    def test_dry_run_dispatches_nothing(self):
        self.make(workflow=WF_KIND)
        res = self.dev_release("--dry-run", "patch")
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertIn("would dispatch dev-release.yml on develop with kind=patch", res.stdout)
        self.assertEqual(self.dispatches(), [])

    def test_a_kind_argument_is_still_required(self):
        self.make(workflow=WF_KIND)
        self.assertEqual(self.dev_release().returncode, 2)


class AfterTheSwitch(DevReleaseCase):

    def assertRefused(self, res, fragment):
        self.assertEqual(res.returncode, 1, self.out(res))
        self.assertIn(fragment, res.stderr)
        self.assertDevelopUnchanged()
        self.assertEqual(self.dispatches(), [])

    def test_open_is_refused_and_names_git_back_merge(self):
        self.make(allow_merge_commit=True)
        self.assertRefused(self.dev_release("--open"), "git back-merge")

    def test_open_without_direct_is_refused_and_names_direct_for_the_exception(self):
        self.make(allow_merge_commit=True)
        self.assertRefused(self.dev_release("--open"), "git dev-release --open --direct")

    def test_direct_is_allowed_only_with_open(self):
        self.make(allow_merge_commit=True)
        self.assertRefused(self.dev_release("--direct", "patch"), "--direct is allowed only with --open")

    def test_open_is_refused_even_where_the_workflow_takes_the_input(self):
        self.make(workflow=WF_KIND, allow_merge_commit=True)
        self.assertRefused(self.dev_release("--open"), "back-merge pull request")

    def test_a_dev_build_without_the_input_is_refused(self):
        self.make(allow_merge_commit=True)
        self.assertRefused(self.dev_release("patch"), "declares no kind input")

    def test_kind_as_a_job_variable_is_not_the_input(self):
        self.make(workflow=WF_KIND_IN_A_JOB, allow_merge_commit=True)
        self.assertRefused(self.dev_release("patch"), "declares no kind input")

    def test_kind_nested_below_another_input_is_not_the_input(self):
        self.make(workflow=WF_KIND_NESTED, allow_merge_commit=True)
        self.assertRefused(self.dev_release("patch"), "declares no kind input")

    def test_an_unreadable_merge_setting_stops_it(self):
        # GitHub returns allow_merge_commit only to a caller with admin rights;
        # read as "not switched", the command would push to develop
        self.make(allow_merge_commit=True)
        self.sb.update_gh_state(admin=False)
        for args in (("patch",), ("--open",)):
            self.assertRefused(self.dev_release(*args), "admin rights")

    def test_no_dev_release_workflow_at_all(self):
        self.make(workflow=None, allow_merge_commit=True)
        self.assertRefused(self.dev_release("patch"), "declares no kind input")


class TheException(DevReleaseCase):
    """--open --direct after the exception, the direct back-merge (the handbook's
    releases.md, "The release's last step: the back-merge pull request"), with
    administrators unbound for its one push: in a repository that allows merge commits
    it opens the cycle by a direct push, as --open does before the switch, and that one
    push carries the hand-made merge commit as well. It refuses a develop that does not
    carry the version of main's newest release or does not hold its commit, both of
    which that merge leaves."""

    def hand_made_back_merge(self):
        """A hotfix released; in the develop worktree, the exception's merge of main, its
        conflicting version lines resolved by hand to main's, committed and not pushed."""
        r = self.make(allow_merge_commit=True)
        r.land_back_merge()
        r.hotfix()
        self.sb.set_gh_state(r.gh_state(allow_merge_commit=True))
        dev = r.dev
        self.sb.git(dev, "pull", "-q", "--ff-only")
        self.sb.run(["git", "merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop after v0.1.2"],
                    dev, check=False)
        self.sb.git(dev, "checkout", "-q", "--theirs", "--", "pyproject.toml", "uv.lock")
        self.sb.git(dev, "add", "pyproject.toml", "uv.lock")
        self.sb.git(dev, "commit", "-q", "--no-edit")
        self.develop_before = self.sb.git(r.origin, "rev-parse", "develop")
        return r, self.sb.git(dev, "rev-parse", "HEAD")

    def test_one_push_carries_the_merge_and_the_open_cycle(self):
        r, merge = self.hand_made_back_merge()
        res = self.dev_release("--open", "--direct")
        self.assertEqual(res.returncode, 0, self.out(res))
        tip = self.sb.git(r.origin, "rev-parse", "develop")
        self.assertEqual(self.sb.git(r.origin, "log", "-1", "--format=%s", tip), "chore: open 0.1.3.dev0 dev cycle")
        self.assertEqual(self.sb.git(r.origin, "rev-parse", tip + "^"), merge)
        self.assertEqual(self.sb.git(r.origin, "log", "-1", "--format=%s", merge), "Back-merge: main → develop after v0.1.2")
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.3.dev0")
        self.assertEqual(self.sb.run(["git", "merge-base", "--is-ancestor", r.tag3_commit, tip], r.origin,
                                     check=False).returncode, 0)
        self.assertEqual(self.dispatches(), [])

    def test_the_push_refused_where_administrators_are_bound(self):
        r, merge = self.hand_made_back_merge()
        hook = r.origin / "hooks" / "pre-receive"
        hook.write_text(GH006_HOOK)
        hook.chmod(0o755)
        res = self.dev_release("--open", "--direct")
        self.assertEqual(res.returncode, 1, self.out(res))
        self.assertIn("switch enforce_admins off for the one push", res.stderr)
        self.assertDevelopUnchanged()

    # --direct is for the exception alone: the develop it pushes must carry the version
    # of main's newest release, which the exception's merge leaves once its version
    # lines are resolved to main's, and hold that release's commit, which it brings

    def develop_at_its_placeholder(self, kind):
        """A hotfix released and no back-merge made: the develop worktree, pulled, is at
        the placeholder the last back-merge opened."""
        r = self.make(kind, allow_merge_commit=True)
        r.land_back_merge()
        r.hotfix()
        self.sb.set_gh_state(r.gh_state(allow_merge_commit=True))
        self.sb.git(r.dev, "pull", "-q", "--ff-only")
        self.develop_before = self.sb.git(r.origin, "rev-parse", "develop")
        return r

    def assertRefusedBeforeTheExceptionsMerge(self, found, expected):
        head = self.sb.git(self.repo.dev, "rev-parse", "HEAD")
        for args in (("--open", "--direct"), ("--dry-run", "--open", "--direct")):
            res = self.dev_release(*args)
            self.assertEqual(res.returncode, 1, self.out(res))
            self.assertIn(f"git dev-release: the local develop's version is {found}, not {expected}, the version"
                          f" of main's newest release (v{expected}): --direct opens the cycle only after the direct"
                          " back-merge of the exception (the handbook's releases.md, \"The release's last step:"
                          " the back-merge pull request\"), whose merge leaves develop at that"
                          " version once its version lines are resolved to main's. Nothing is committed or pushed.",
                          res.stderr)
            self.assertNotIn("new:", res.stdout)
        self.assertEqual(self.sb.git(self.repo.dev, "rev-parse", "HEAD"), head)
        self.assertEqual(self.sb.git(self.repo.dev, "status", "--porcelain"), "")
        self.assertDevelopUnchanged()
        self.assertEqual(self.dispatches(), [])

    def test_refused_on_a_develop_at_its_placeholder(self):
        self.develop_at_its_placeholder("pyproject")
        self.assertRefusedBeforeTheExceptionsMerge("0.1.2.dev0", "0.1.2")

    def test_refused_on_a_package_develop_at_its_placeholder(self):
        self.develop_at_its_placeholder("package")
        self.assertRefusedBeforeTheExceptionsMerge("3.5.2-dev0", "3.5.2")

    def test_refused_where_the_version_was_set_by_hand_without_the_merge(self):
        # develop's version lines set to the release's by hand, main not merged: the
        # version agrees, and develop does not hold the release's commit
        r = self.develop_at_its_placeholder("pyproject")
        r.set_version(r.dev, "0.1.2")
        self.sb.git(r.dev, "commit", "-q", "-am", "chore: set develop's version to 0.1.2")
        head = self.sb.git(r.dev, "rev-parse", "HEAD")
        short = self.sb.git(r.dev, "rev-parse", "--short", r.tag3_commit)
        for args in (("--open", "--direct"), ("--dry-run", "--open", "--direct")):
            res = self.dev_release(*args)
            self.assertEqual(res.returncode, 1, self.out(res))
            self.assertIn("git dev-release: the local develop's version is 0.1.2, the version of main's newest release"
                          f" (v0.1.2), but it does not hold that release's commit ({short}): the exception's merge is"
                          " missing. --direct opens the cycle only after the direct back-merge of the exception (the"
                          " handbook's releases.md, \"The release's last step: the back-merge pull request\"),"
                          " whose merge of main brings that commit into develop. Nothing is committed"
                          " or pushed.", res.stderr)
            self.assertNotIn("new:", res.stdout)
        self.assertEqual(self.sb.git(r.dev, "rev-parse", "HEAD"), head)
        self.assertEqual(self.sb.git(r.dev, "status", "--porcelain"), "")
        self.assertDevelopUnchanged()
        self.assertEqual(self.dispatches(), [])

    def test_the_newest_release_is_read_from_origin(self):
        # a develop worktree that has not fetched the hotfix's tag still finds it
        r, merge = self.hand_made_back_merge()
        self.sb.git(r.dev, "tag", "-d", "v0.1.2")
        res = self.dev_release("--open", "--direct")
        self.assertEqual(res.returncode, 0, self.out(res))
        self.assertEqual(r.version_at("develop", cwd=r.origin), "0.1.3.dev0")

    def test_refused_where_the_tags_cannot_be_fetched(self):
        # a local tag that differs from origin's stops the tag fetch: the local tags
        # are then no measure of main's newest release
        r, merge = self.hand_made_back_merge()
        self.sb.git(r.dev, "tag", "-f", "v0.1.2", "HEAD")
        res = self.dev_release("--open", "--direct")
        self.assertEqual(res.returncode, 1, self.out(res))
        self.assertIn("git dev-release: cannot fetch main and the release tags from origin; --direct needs them to"
                      " compare the local develop's version with main's newest release. Nothing is committed or"
                      " pushed.", res.stderr)
        self.assertIn("would clobber existing tag", res.stderr)
        self.assertEqual(self.sb.git(r.dev, "rev-parse", "HEAD"), merge)
        self.assertDevelopUnchanged()

    def test_refused_where_main_holds_no_release(self):
        r, merge = self.hand_made_back_merge()
        for where in (r.origin, r.dev):
            for tag in self.sb.git(where, "tag", "-l").split():
                self.sb.git(where, "tag", "-d", tag)
        res = self.dev_release("--open", "--direct")
        self.assertEqual(res.returncode, 1, self.out(res))
        self.assertIn("git dev-release: origin/main holds no release tag vX.Y.Z, so the local develop cannot carry"
                      " the version of main's newest release: --direct opens the cycle only after the direct"
                      " back-merge of the exception (the handbook's releases.md, \"The release's last step: the"
                      " back-merge pull request\"). Nothing is committed or pushed.", res.stderr)
        self.assertEqual(self.sb.git(r.dev, "rev-parse", "HEAD"), merge)
        self.assertDevelopUnchanged()


class VersionTxt(DevReleaseCase):

    def test_refused(self):
        self.make("version-txt", workflow=None)
        for args in (("patch",), ("--open",), ("--open", "--direct")):
            res = self.dev_release(*args)
            self.assertEqual(res.returncode, 1, self.out(res))
            self.assertIn("VERSION.txt", res.stderr)
        self.assertDevelopUnchanged()


if __name__ == "__main__":
    unittest.main()
