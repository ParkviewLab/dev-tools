# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The unit tests of scripts/git-dev-release.

Both of its behaviours, as the design of real merges sets them out: in a
repository that does not allow merge commits and whose dev-release.yml declares
no `kind` input, it commits, pushes and dispatches as before, --open included;
where the workflow declares the input, it dispatches with it and commits nothing.
Once merge commits are allowed, develop takes no direct push, so --open and a dev
build without the input are refused. A VERSION.txt repository has no dev build.
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
WF_KIND_IN_A_JOB = WF_NO_INPUT.replace("    runs-on: ubuntu-latest\n",
                                       "    runs-on: ubuntu-latest\n    env:\n      kind: patch\n")
WF_KIND_NESTED = WF_NO_INPUT.replace("  workflow_dispatch:\n",
                                     "  workflow_dispatch:\n    inputs:\n      target:\n        kind: patch\n")


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
        self.assertRegex(self.sb.git(r.origin, "log", "-1", "--format=%s", "develop"), r"^chore: open .* dev cycle$")
        self.assertEqual(self.dispatches(), [])

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

    def test_no_dev_release_workflow_at_all(self):
        self.make(workflow=None, allow_merge_commit=True)
        self.assertRefused(self.dev_release("patch"), "declares no kind input")


class VersionTxt(DevReleaseCase):

    def test_refused(self):
        self.make("version-txt", workflow=None)
        for args in (("patch",), ("--open",)):
            res = self.dev_release(*args)
            self.assertEqual(res.returncode, 1, self.out(res))
            self.assertIn("VERSION.txt", res.stderr)
        self.assertDevelopUnchanged()


if __name__ == "__main__":
    unittest.main()
