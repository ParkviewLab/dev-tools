# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The unit tests of scripts/back-merge-check.

The cases of the simulation behind the design (the proposal "Real merges and the
back-merge pull request", its sim/run-sim.sh and sim/run-sim-kinds.sh) are tests
here, built in temporary repositories: 24 in the main scenario and 6 for
package.json and VERSION.txt, a VERSION.txt open-cycle commit being refused, as
condition 4 requires. Further cases cover what the simulation did not construct:
a lockfile line that belongs to a dependency, a repository without a lockfile,
real-sized lockfiles, names uv normalises, tag names, exit codes, condition 2 on
its own, and attempts to pass other changes through the open-cycle commit or a
tag that shadows main. The back-merge of a release picked onto main (a hotfix),
whose merge condition 3 takes with the project's version lines set to main's,
has its own cases, as has the --merge-tree mode that git back-merge builds it by.
"""

from __future__ import annotations

import json
import re
import unittest

from backmerge_support import (FIX_LINE_2, SCRIPTS, ReleasedRepo, Sandbox, rework_line_2, set_package_version,
                               set_pyproject_version, upgrade_twin)

PASS, FAIL, ERROR = 0, 1, 2
VERSION_FILES = {"pyproject": ("pyproject.toml", "uv.lock"), "package": ("package.json", "package-lock.json"),
                 "version-txt": ("VERSION.txt",)}


class CheckCase(unittest.TestCase):
    sb: Sandbox
    repo: ReleasedRepo

    def check(self, base, head, main="origin/main", tag=None, cwd=None, env=None):
        args = [base, head, main] + ([tag] if tag else [])
        return self.sb.script("back-merge-check", *args, cwd=cwd or self.repo.releaser, env=env)

    def merge_tree(self, develop, tag, main="origin/main", env=None):
        return self.sb.script("back-merge-check", "--merge-tree", develop, main, tag, cwd=self.repo.releaser, env=env)

    def assertTree(self, result, tree):
        """The --merge-tree mode printed tree on its last line."""
        self.assertEqual(result.returncode, PASS, f"\n{result.stdout}\n{result.stderr}")
        self.assertEqual(result.stdout.splitlines()[-1], tree)

    def assertOutcome(self, expected, result, fragment=None):
        msg = f"\n{result.stdout}\n{result.stderr}"
        self.assertEqual(result.returncode, expected, msg)
        if fragment:
            self.assertIn(fragment, result.stdout + result.stderr, msg)


class MainScenario(CheckCase):
    """The simulation's main scenario: a pyproject.toml repository with uv.lock."""

    @classmethod
    def setUpClass(cls):
        cls.sb = Sandbox()
        cls.repo = r = ReleasedRepo(cls.sb, "pyproject")
        g = r.g
        g("fetch", "-q", "origin")
        cls.BASE = g("rev-parse", "origin/develop")
        cls.P = r.promoted
        cls.MAINTIP = r.main_tip
        g("switch", "-q", "-c", "back-merge-v0.1.1", "origin/develop")
        g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop after v0.1.1")
        cls.M = g("rev-parse", "HEAD")
        r.set_version(r.releaser, "0.1.2.dev0")
        g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        cls.C = g("rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls):
        cls.sb.cleanup()

    def branch(self, name, start):
        self.repo.g("switch", "-q", "-C", name, start)
        return self.repo.releaser

    def commit_all(self, msg):
        self.repo.g("commit", "-q", "-am", msg)
        return self.repo.g("rev-parse", "HEAD")

    # accepted
    def test_01_clean_back_merge_head_is_the_merge(self):
        self.assertOutcome(PASS, self.check(self.BASE, self.M))

    def test_02_clean_back_merge_with_the_open_cycle_commit(self):
        self.assertOutcome(PASS, self.check(self.BASE, self.C), "0.1.1 -> 0.1.2.dev0")

    def test_03_clean_back_merge_with_the_open_cycle_commit_tag_mode(self):
        self.assertOutcome(PASS, self.check(self.BASE, self.C, tag="v0.1.1"))

    # rejected: an extra commit smuggled onto the branch
    def test_04_extra_commit_after_the_merge(self):
        wt = self.branch("x-after-m", self.M)
        ReleasedRepo.edit(wt, "app.txt", "sneak\n")
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_all("fix: sneak")))

    def test_05_extra_commit_after_the_open_cycle_commit(self):
        wt = self.branch("x-after-c", self.C)
        ReleasedRepo.edit(wt, "app.txt", "sneak\n")
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_all("fix: sneak")))

    def test_06_open_cycle_commit_that_also_edits_another_file(self):
        wt = self.branch("x-oc-plus", self.M)
        self.repo.set_version(wt, "0.1.2.dev0")
        ReleasedRepo.edit(wt, "app.txt", "sneak\n")
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_all("chore: open 0.1.2.dev0 dev cycle")),
                           "changes app.txt")

    def test_07_extra_commit_below_the_merge(self):
        # the simulation's "first parent not on develop"; condition 1 refuses it
        # first, and FirstParentAndSecondParent reaches condition 2 itself
        wt = self.branch("x-before-m", "origin/develop")
        ReleasedRepo.edit(wt, "app.txt", "sneak\n")
        self.commit_all("fix: sneak")
        self.repo.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "sits below the merge")

    # rejected: a merge whose tree was altered
    def test_08_evil_merge(self):
        wt = self.branch("x-evil", "origin/develop")
        self.repo.g("merge", "-q", "--no-ff", "--no-commit", "origin/main")
        ReleasedRepo.edit(wt, "app.txt", "folded into the merge\n")
        self.repo.g("add", "app.txt")
        self.repo.g("commit", "-q", "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "differs from the automatic merge")

    # rejected: a merge of a commit that is not on main
    def test_09_second_parent_not_on_main(self):
        # refused at condition 1 as well: the unreleased commit is a second one off main
        wt = self.branch("x-notmain-src", "origin/main")
        ReleasedRepo.edit(wt, "app.txt", "unreleased\n")
        notmain = self.commit_all("fix: never pushed to main")
        self.branch("x-notmain", "origin/develop")
        self.repo.g("merge", "-q", "--no-ff", notmain, "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "sits below the merge")

    # condition 2 on its own: the merge is the only commit off main
    def test_first_parent_on_main_not_on_develop(self):
        self.branch("x-p1-main", self.repo.tag_commit)
        self.repo.g("merge", "-q", "--no-ff", self.MAINTIP, "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "is not on develop")

    def test_second_parent_on_develop_not_on_main(self):
        self.branch("x-p2-develop", self.P)
        self.repo.g("merge", "-q", "--no-ff", self.BASE, "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "is not on main")

    def test_a_head_without_a_version_line(self):
        wt = self.branch("x-no-version", self.M)
        text = (wt / "pyproject.toml").read_text()
        (wt / "pyproject.toml").write_text("\n".join(l for l in text.split("\n") if not l.startswith("version")))
        result = self.check(self.BASE, self.commit_all("chore: a dynamic version"))
        self.assertOutcome(FAIL, result, "cannot read the project's own version of head")
        self.assertIn("holds no static version in its [project] table", result.stdout)

    def test_10_second_parent_is_a_working_branch(self):
        wt = self.branch("x-feature-src", self.P)
        ReleasedRepo.edit(wt, "work.txt", "work\n")
        self.repo.g("add", "work.txt")
        feature = self.commit_all("feat: work in progress")
        self.branch("x-feature-merge", "origin/develop")
        self.repo.g("merge", "-q", "--no-ff", feature, "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "a second commit not on main sits below the merge")

    # rejected: any other version
    def _other_version(self, name, version, lock=True):
        wt = self.branch(name, self.M)
        set_pyproject_version(wt, version, lock)
        return self.check(self.BASE, self.commit_all(f"chore: open {version} dev cycle"))

    def test_11_open_cycle_sets_the_next_dev_number(self):
        self.assertOutcome(FAIL, self._other_version("x-v1", "0.1.2.dev1"))

    def test_12_open_cycle_re_pointed_to_the_next_minor(self):
        self.assertOutcome(FAIL, self._other_version("x-v2", "0.2.0.dev0"))

    def test_13_open_cycle_sets_a_release_version(self):
        self.assertOutcome(FAIL, self._other_version("x-v3", "0.1.2"))

    def test_14_open_cycle_sets_a_version_below_the_release(self):
        self.assertOutcome(FAIL, self._other_version("x-v4", "0.1.1.dev0"))

    def test_15_placeholder_in_pyproject_but_lockfile_left_behind(self):
        self.assertOutcome(FAIL, self._other_version("x-lock-stale", "0.1.2.dev0", lock=False),
                           "uv.lock still records 0.1.1")

    def test_16_merge_of_an_older_main_commit(self):
        self.branch("x-older-main", "origin/develop")
        self.repo.g("merge", "-q", "--no-ff", self.MAINTIP + "~2", "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "is not main's")

    def test_17_fast_forward_head(self):
        self.assertOutcome(FAIL, self.check(self.P, self.MAINTIP), "found 0")

    # on main is not released: a direct push to main after the tag
    def _direct_push(self):
        wt = self.branch("main-plus-direct", self.MAINTIP)
        ReleasedRepo.edit(wt, "app.txt", "direct to main\n")
        direct = self.commit_all("docs: typo pushed straight to main")
        self.branch("x-direct", "origin/develop")
        self.repo.g("merge", "-q", "--no-ff", direct, "-m", "Back-merge: main → develop after v0.1.1")
        return direct

    def test_18_unreleased_direct_push_passes_in_plain_mode(self):
        direct = self._direct_push()
        self.assertOutcome(PASS, self.check(self.BASE, "HEAD", main=direct))

    def test_19_unreleased_direct_push_refused_in_tag_mode(self):
        direct = self._direct_push()
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD", main=direct, tag="v0.1.1"),
                           "is not its changelog commit")

    # refresh: a pull request merges into develop after the branch is made
    def _new_base(self):
        wt = self.branch("develop-later", "origin/develop")
        ReleasedRepo.edit(wt, "g.txt", "feature G\n")
        self.repo.g("add", "g.txt")
        return self.commit_all("feat: feature G (#3)")

    def test_20_old_head_against_the_new_base(self):
        self.assertOutcome(PASS, self.check(self._new_base(), self.C))

    def test_21_update_branch_merge_of_develop_refused(self):
        base2 = self._new_base()
        self.branch("x-update-branch", self.C)
        self.repo.g("merge", "-q", "--no-ff", base2, "-m", "Merge branch 'develop' into back-merge-v0.1.1")
        self.assertOutcome(FAIL, self.check(base2, "HEAD"), "found 2")

    def test_22_branch_rebuilt_from_the_new_develop(self):
        base2 = self._new_base()
        wt = self.branch("x-rebuilt", base2)
        self.repo.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop after v0.1.1")
        self.repo.set_version(wt, "0.1.2.dev0")
        self.assertOutcome(PASS, self.check(base2, self.commit_all("chore: open 0.1.2.dev0 dev cycle"), tag="v0.1.1"))

    # a dev build landed on develop during the release, resolved by hand
    def test_23_hand_resolved_back_merge_refused(self):
        wt = self.branch("c-develop", self.P)
        self.repo.set_version(wt, "0.1.1.dev1")
        cb = self.commit_all("chore: dev build v0.1.1.dev1")
        self.branch("c-back-merge", cb)
        r = self.sb.git(wt, "merge", "-q", "--no-ff", self.MAINTIP, "-m", "Back-merge: main → develop after v0.1.1",
                        check=False)
        self.repo.g("checkout", "-q", "--theirs", "pyproject.toml", "uv.lock")
        self.repo.g("add", "pyproject.toml", "uv.lock")
        self.repo.g("commit", "-q", "--no-edit", "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(cb, "HEAD"), "conflicts")

    def test_24_shallow_repository_refused(self):
        wt = self.branch("x-shallow-src", self.BASE)
        self.repo.g("push", "-q", "origin", f"{self.C}:refs/heads/back-merge-v0.1.1")
        ci = self.sb.tmp / "ci"
        self.sb.git(self.sb.tmp, "clone", "-q", "file://" + str(self.repo.origin), str(ci))
        self.sb.git(ci, "fetch", "-q", "--no-tags", "--depth=1", "origin", "develop")
        self.assertEqual(self.sb.git(ci, "rev-parse", "--is-shallow-repository"), "true")
        self.assertOutcome(ERROR, self.check(self.BASE, self.C, cwd=ci), "shallow repository")

    # further cases
    def test_open_cycle_changing_a_dependency_line_by_another_value(self):
        # refused as a line that changes more than the version value; LockfileOwner
        # has the cases a dependency at main's own version brings
        wt = self.branch("x-lock-dep", self.M)
        set_pyproject_version(wt, "0.1.2.dev0", lock=False)
        lock = (wt / "uv.lock").read_text().replace('version = "3.10"', 'version = "3.11"')
        (wt / "uv.lock").write_text(lock)
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_all("chore: open 0.1.2.dev0 dev cycle")),
                           "changes more than the version value")

    # attempts on the open-cycle rule and on the main ref (the adversarial review)
    def open_cycle_on_m(self, name):
        wt = self.branch(name, self.M)
        self.repo.set_version(wt, "0.1.2.dev0")
        return wt

    def commit_everything(self, msg="chore: open 0.1.2.dev0 dev cycle"):
        self.repo.g("add", "-A")
        self.repo.g("commit", "-q", "-m", msg)
        return self.repo.g("rev-parse", "HEAD")

    def test_open_cycle_adding_a_file_whose_name_holds_a_space(self):
        wt = self.open_cycle_on_m("x-space")
        (wt / "pyproject.toml pyproject.toml").write_text("injected\n")
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_everything(), tag="v0.1.1"),
                           "changes pyproject.toml\\ pyproject.toml")

    def test_open_cycle_adding_a_file_whose_name_is_a_glob(self):
        wt = self.open_cycle_on_m("x-glob")
        (wt / "pyproject.to[m]l").write_text("injected\n")
        (wt / "[u]v.lock").write_text("injected\n")
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_everything(), tag="v0.1.1"),
                           "the open-cycle commit changes")

    def test_open_cycle_adding_a_line_that_begins_with_plus_signs(self):
        # in a -U0 diff it reads "+++...", the form of a file header. As a TOML
        # statement it does not parse, so reading the version refuses it first;
        # inside a multi-line string it parses, and the line count refuses it
        wt = self.open_cycle_on_m("x-plusplus")
        with open(wt / "pyproject.toml", "a") as fh:
            fh.write("++injected\n")
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_everything(), tag="v0.1.1"),
                           "cannot be parsed")
        wt = self.open_cycle_on_m("x-plusplus-in-a-string")
        with open(wt / "pyproject.toml", "a") as fh:
            fh.write('notes = """\n++injected\n"""\n')
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_everything(), tag="v0.1.1"),
                           "adds or removes lines")

    def test_open_cycle_changing_the_version_files_mode(self):
        wt = self.open_cycle_on_m("x-mode")
        (wt / "pyproject.toml").chmod(0o755)
        head = self.commit_everything()
        self.assertEqual(self.repo.g("ls-tree", head, "pyproject.toml").split()[0], "100755")
        self.assertOutcome(FAIL, self.check(self.BASE, head, tag="v0.1.1"), "mode")

    def test_open_cycle_changing_the_last_line_ending(self):
        wt = self.open_cycle_on_m("x-eol")
        (wt / "pyproject.toml").write_text((wt / "pyproject.toml").read_text().rstrip("\n"))
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_everything(), tag="v0.1.1"),
                           "last line ending")

    def test_a_tag_named_like_main_does_not_stand_in_for_it(self):
        g = self.repo.g
        wt = self.branch("x-fake-main", self.MAINTIP)
        ReleasedRepo.edit(wt, "CHANGELOG.md", "# Changelog\n\nfabricated\n")
        fake = self.commit_all("docs(changelog): v0.1.1 [skip ci]")
        g("tag", "origin/main", fake)
        self.addCleanup(g, "tag", "-d", "origin/main")
        g("switch", "-q", "-C", "x-fake-merge", self.BASE)
        g("merge", "-q", "--no-ff", fake, "-m", "Back-merge: main → develop after v0.1.1")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD", tag="v0.1.1"), "not on main")

    def test_a_main_ref_that_only_a_tag_carries_is_refused(self):
        g = self.repo.g
        g("tag", "only-a-tag", self.MAINTIP)
        self.addCleanup(g, "tag", "-d", "only-a-tag")
        self.assertOutcome(ERROR, self.check(self.BASE, self.C, main="only-a-tag"), "names a tag")

    def test_two_merges_refused(self):
        wt = self.branch("x-side", self.BASE)
        ReleasedRepo.edit(wt, "side.txt", "side\n")
        self.repo.g("add", "side.txt")
        side = self.commit_all("feat: a side change")
        self.branch("x-two-merges", self.M)
        self.repo.g("merge", "-q", "--no-ff", side, "-m", "a second merge")
        self.assertOutcome(FAIL, self.check(self.BASE, "HEAD"), "found 2")

    def test_tag_mode_with_a_tag_that_is_not_the_release(self):
        self.assertOutcome(FAIL, self.check(self.BASE, self.C, tag="v0.1.0"), "after v0.1.0")

    def test_tag_mode_with_a_name_that_is_not_a_release_tag(self):
        self.assertOutcome(FAIL, self.check(self.BASE, self.C, tag="vfoo"), "not a release tag")

    def test_tag_mode_with_a_tag_that_does_not_exist(self):
        self.assertOutcome(FAIL, self.check(self.BASE, self.C, tag="v9.9.9"), "does not exist")

    def test_usage_error(self):
        self.assertOutcome(ERROR, self.sb.script("back-merge-check", "only-one-argument", cwd=self.repo.releaser))

    def test_unknown_commit_is_an_error(self):
        self.assertOutcome(ERROR, self.check(self.BASE, "0" * 40))


class NoLockfile(CheckCase):
    """A pyproject.toml repository without uv.lock: the open-cycle commit changes pyproject.toml alone."""

    @classmethod
    def setUpClass(cls):
        cls.sb = Sandbox()
        cls.repo = r = ReleasedRepo(cls.sb, "pyproject", lockfile=False)
        r.g("fetch", "-q", "origin")
        cls.BASE = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge-v0.1.1", "origin/develop")
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop after v0.1.1")
        r.set_version(r.releaser, "0.1.2.dev0")
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        cls.C = r.g("rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls):
        cls.sb.cleanup()

    def test_open_cycle_without_a_lockfile(self):
        self.assertOutcome(PASS, self.check(self.BASE, self.C, tag="v0.1.1"))


class OtherKinds(CheckCase):
    """The simulation's run-sim-kinds.sh: package.json with package-lock.json, and VERSION.txt."""

    def build(self, kind):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, kind, changelog=False)
        r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge", "origin/develop")
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop")
        m = r.g("rev-parse", "HEAD")
        return r, base, m

    def test_package_json(self):
        r, base, m = self.build("package")
        self.assertOutcome(PASS, self.check(base, m))
        r.set_version(r.releaser, "3.5.2-dev0")
        r.g("commit", "-q", "-am", "chore: open 3.5.2-dev0 dev cycle")
        c = r.g("rev-parse", "HEAD")
        self.assertOutcome(PASS, self.check(base, c, tag="v3.5.1"), "package-lock.json package.json")
        r.g("switch", "-q", "-c", "wrong", m)
        r.set_version(r.releaser, "3.6.0-dev0")
        r.g("commit", "-q", "-am", "chore: open 3.6.0-dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "is not main's next-patch placeholder 3.5.2-dev0")
        # a dependency line changed by another value (LockfileOwner has one at main's version)
        r.g("switch", "-q", "-c", "dep", m)
        set_package_version(r.releaser, "3.5.2-dev0", lock=False)
        lock = (r.releaser / "package-lock.json").read_text().replace('"version": "1.3.0"', '"version": "1.3.1"')
        (r.releaser / "package-lock.json").write_text(lock)
        r.g("commit", "-q", "-am", "chore: open 3.5.2-dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "changes more than the version value")

    def test_version_txt(self):
        r, base, m = self.build("version-txt")
        self.assertOutcome(PASS, self.check(base, m, tag="v0.23.1"))
        # the open cycle, which a VERSION.txt repository skips: refused (condition 4, narrowed)
        r.set_version(r.releaser, "0.23.2-dev")
        r.g("commit", "-q", "-am", "chore: open 0.23.2-dev dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "skips the open cycle")
        r.g("switch", "-q", "-c", "wrong", m)
        r.set_version(r.releaser, "0.24.0-dev")
        r.g("commit", "-q", "-am", "chore: open 0.24.0-dev dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"))


class LockfileOwner(CheckCase):
    """A lockfile line may change only where it is the project's own.

    A dependency named twin stands at the release's version, so that changing
    its line from main's version to the placeholder passes every rule but this
    one. In uv.lock the project's block carries no version, so that the rule on
    a lockfile left behind does not refuse first.
    """

    def build(self, kind, **kw):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, kind, changelog=False, lock_twin=True, **kw)
        r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge", "origin/develop")
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop")
        return r, base, r.g("rev-parse", "HEAD")

    def test_package_lock_json(self):
        r, base, m = self.build("package")
        r.set_version(r.releaser, "3.5.2-dev0")
        r.g("commit", "-q", "-am", "chore: open 3.5.2-dev0 dev cycle")
        self.assertOutcome(PASS, self.check(base, "HEAD", tag="v3.5.1"))
        # the top-level version and the twin's, with packages[""] left behind: two pairs
        r.g("switch", "-q", "-c", "twin", m)
        set_package_version(r.releaser, "3.5.2-dev0", lock=False)
        lock = json.loads((r.releaser / "package-lock.json").read_text())
        lock["version"] = "3.5.2-dev0"
        lock["packages"]["node_modules/twin"]["version"] = "3.5.2-dev0"
        (r.releaser / "package-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
        r.g("commit", "-q", "-am", "chore: open 3.5.2-dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "is not the root package's version")

    def test_package_lock_json_root_entry_left_behind(self):
        r, base, m = self.build("package")
        set_package_version(r.releaser, "3.5.2-dev0", lock=False)
        lock = json.loads((r.releaser / "package-lock.json").read_text())
        lock["version"] = "3.5.2-dev0"   # packages[""] left at 3.5.1
        (r.releaser / "package-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
        r.g("commit", "-q", "-am", "chore: open 3.5.2-dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "package-lock.json still records 3.5.1 for the project")

    def test_uv_lock(self):
        r, base, m = self.build("pyproject", lock_project_version=False)
        set_pyproject_version(r.releaser, "0.1.2.dev0")
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(PASS, self.check(base, "HEAD", tag="v0.1.1"))
        r.g("switch", "-q", "-c", "twin", m)
        set_pyproject_version(r.releaser, "0.1.2.dev0")
        lock = (r.releaser / "uv.lock").read_text()
        self.assertEqual(lock.count('version = "0.1.1"'), 1)
        (r.releaser / "uv.lock").write_text(lock.replace('version = "0.1.1"', 'version = "0.1.2.dev0"'))
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "is not in the sim-app package block")


class NormalisedName(CheckCase):
    """A project name that uv records normalised: Sim_App in pyproject.toml, sim-app in uv.lock."""

    def test_open_cycle(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, "pyproject", changelog=False, project_name="Sim_App")
        self.assertIn('name = "sim-app"', (r.releaser / "uv.lock").read_text())
        r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge", "origin/develop")
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop")
        m = r.g("rev-parse", "HEAD")
        r.set_version(r.releaser, "0.1.2.dev0")
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(PASS, self.check(base, "HEAD", tag="v0.1.1"))
        r.g("switch", "-q", "-c", "stale", m)
        set_pyproject_version(r.releaser, "0.1.2.dev0", lock=False)
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "uv.lock still records 0.1.1")


class RealSizedLockfiles(CheckCase):
    """Lockfiles with a real one's bulk after the project's version line.

    The check reads a lockfile through a pipeline; a reader that stops early
    leaves the writer to die of SIGPIPE, and under pipefail that failed a clean
    back-merge with status 141. A few thousand entries put far more than a pipe
    buffer after the line.
    """

    def build(self, kind, placeholder):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, kind, lock_bulk=3000)
        r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge", "origin/develop")
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop")
        r.set_version(r.releaser, placeholder)
        r.g("commit", "-q", "-am", f"chore: open {placeholder} dev cycle")
        return r, base

    def test_uv_lock(self):
        r, base = self.build("pyproject", "0.1.2.dev0")
        self.assertGreater((r.releaser / "uv.lock").stat().st_size, 300_000)
        self.assertOutcome(PASS, self.check(base, "HEAD", tag="v0.1.1"), "0.1.1 -> 0.1.2.dev0")

    def test_package_lock_json(self):
        r, base = self.build("package", "3.5.2-dev0")
        self.assertGreater((r.releaser / "package-lock.json").stat().st_size, 300_000)
        self.assertOutcome(PASS, self.check(base, "HEAD", tag="v3.5.1"), "3.5.1 -> 3.5.2-dev0")


class SecondReview(CheckCase):
    """The cases of the second adversarial review of the check."""

    def build(self, kind="pyproject", on_develop=None, **kw):
        """A released repository, the merge M of main into develop on a branch, and
        base; on_develop(worktree) may first add a commit to develop."""
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, kind, changelog=False, **kw)
        r.g("fetch", "-q", "origin")
        if on_develop:
            r.g("switch", "-q", "develop")
            r.g("merge", "-q", "--ff-only", "origin/develop")
            on_develop(r.releaser)
            r.g("push", "-q", "origin", "develop")
            r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge", "origin/develop")
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop")
        return r, base

    def test_a_submodule_set_to_ignore_all_is_still_seen(self):
        def add_submodule(wt):
            (wt / ".gitmodules").write_text('[submodule "vendor/lib"]\n\tpath = vendor/lib\n'
                                            '\turl = ../lib.git\n\tignore = all\n')
            self.repo.g("add", ".gitmodules")
            self.repo.g("update-index", "--add", "--cacheinfo", f"160000,{self.repo.promoted},vendor/lib")
            self.repo.g("commit", "-q", "-m", "chore: vendor lib (#4)")
        r, base = self.build(on_develop=lambda wt: add_submodule(wt))
        r.set_version(r.releaser, "0.1.2.dev0")
        r.g("add", "pyproject.toml", "uv.lock")
        r.g("update-index", "--cacheinfo", f"160000,{r.tag_commit},vendor/lib")
        r.g("commit", "-q", "-m", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"), "changes vendor/lib")

    def test_a_nul_byte_in_the_version_file(self):
        # TOML admits no NUL byte, so in pyproject.toml reading the version refuses
        # it first; the lockfile, which that reading does not parse, meets the NUL rule
        r, base = self.build()
        m = r.g("rev-parse", "HEAD")
        r.set_version(r.releaser, "0.1.2.dev0")
        text = (r.releaser / "pyproject.toml").read_bytes()
        (r.releaser / "pyproject.toml").write_bytes(text.replace(b'"0.1.2.dev0"', b'"0.1.2.dev0"\x00'))
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"), "cannot be parsed")
        r.g("switch", "-q", "-c", "nul-in-the-lockfile", m)
        r.set_version(r.releaser, "0.1.2.dev0")
        text = (r.releaser / "uv.lock").read_bytes()
        (r.releaser / "uv.lock").write_bytes(text.replace(b'"0.1.2.dev0"', b'"0.1.2.dev0"\x00'))
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"), "uv.lock: a NUL byte in the file")

    def test_a_numeric_line_changed_to_an_equal_number(self):
        r, base = self.build(pyproject_head="[tool.x]\nlevels = [\n  1,\n  3\n]\n\n")
        r.set_version(r.releaser, "0.1.2.dev0")
        text = (r.releaser / "pyproject.toml").read_text()
        (r.releaser / "pyproject.toml").write_text(text.replace("\n  3\n", "\n  3.0\n"))
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"))

    def test_crlf_package_files(self):
        r, base = self.build("package", crlf=True)
        self.assertIn(b"\r\n", (r.releaser / "package-lock.json").read_bytes())
        m = r.g("rev-parse", "HEAD")
        r.set_version(r.releaser, "3.5.2-dev0")
        r.g("commit", "-q", "-am", "chore: open 3.5.2-dev0 dev cycle")
        self.assertOutcome(PASS, self.check(base, "HEAD", tag="v3.5.1"))
        # the top-level version left behind in the lockfile
        r.g("switch", "-q", "-c", "stale", m)
        set_package_version(r.releaser, "3.5.2-dev0", lock=False)
        raw = (r.releaser / "package-lock.json").read_bytes().decode()
        lock = json.loads(raw)
        lock["packages"][""]["version"] = "3.5.2-dev0"
        (r.releaser / "package-lock.json").write_bytes(
            (json.dumps(lock, indent=2) + "\n").replace("\n", "\r\n").encode())
        r.g("commit", "-q", "-am", "chore: open 3.5.2-dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD"), "package-lock.json still records 3.5.1 for the project at line 3")

    def test_collation_does_not_hide_a_change(self):
        # macOS awk compares strings with strcoll under a UTF-8 locale, where a
        # zero-width space compares equal to nothing
        r, base = self.build()
        r.set_version(r.releaser, "0.1.2.dev0")
        text = (r.releaser / "pyproject.toml").read_text()
        (r.releaser / "pyproject.toml").write_text(text.replace('["idna"]', '["idna\u200b"]'))
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1", env={"LC_ALL": "en_US.UTF-8"}))

    def test_a_version_line_outside_the_project_table(self):
        # a [tool] table's version before [project], standing at the release's
        # version: a change to it is not the open cycle, whether with the project's
        # own (the owner rule) or instead of it (the project's version unchanged)
        r, base = self.build(pyproject_head='[tool.x]\nversion = "0.1.1"\n\n')
        m = r.g("rev-parse", "HEAD")

        def set_tool_x(version):
            text = (r.releaser / "pyproject.toml").read_text()
            (r.releaser / "pyproject.toml").write_text(text.replace('[tool.x]\nversion = "0.1.1"',
                                                                    f'[tool.x]\nversion = "{version}"'))
        r.set_version(r.releaser, "0.1.2.dev0")
        set_tool_x("0.1.2.dev0")
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"), "is not the [project] table's version ([tool.x])")
        r.g("switch", "-q", "-c", "tool-x-only", m)
        set_tool_x("0.1.2.dev0")
        r.g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"),
                           "open-cycle version 0.1.1 is not main's next-patch placeholder 0.1.2.dev0")

    def test_a_changelog_commit_that_changes_the_files_mode(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, "pyproject")
        r.g("fetch", "-q", "origin")
        r.g("switch", "-q", "-c", "bot", "origin/main")
        (r.releaser / "CHANGELOG.md").chmod(0o755)
        r.g("commit", "-q", "-am", "docs(changelog): v0.1.1 [skip ci]")
        r.g("push", "-q", "origin", "HEAD:main")
        r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge", "origin/develop")
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"), "is not its changelog commit")


class PickedRelease(CheckCase):
    """The back-merge of a release picked onto main: a hotfix, made as the handbook
    gives it, `git cherry-pick -m 1` of a pull request's merge on develop, then the
    bump and the tag, with no promotion.

    In a code repository the automatic merge of main into develop conflicts on the
    project's version lines by construction: since their merge base, main has moved
    them to the hotfix's version and develop to its placeholder. In tag mode,
    condition 3 then takes the merge in which those lines of develop and of the
    merge base are first set to main's version. M is made here independently of the
    check: git's own merge, its conflicting version files resolved to develop's with
    the project's version set by the fixtures' setters.
    """

    def build(self, kind="pyproject", fix=("fix.txt", "fix\n"), after_fix=None, **kw):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, kind, **kw)
        r.land_back_merge()
        r.hotfix(fix=fix, after_fix=after_fix)
        r.g("fetch", "-q", "origin")
        return r, r.g("rev-parse", "origin/develop")

    def merge(self, take="main", edit=None, name="back-merge"):
        """M: git's merge of main into develop. Where it conflicts, each conflicting
        version file is taken from develop, with the project's version set to main's
        where take is "main", edit(worktree) is applied, and the result committed,
        whatever remains conflicted included."""
        r, g = self.repo, self.repo.g
        message = f"Back-merge: main → develop after {r.tag3}"
        g("switch", "-q", "-C", name, "origin/develop")
        merged = self.sb.run(["git", "merge", "-q", "--no-ff", "origin/main", "-m", message], r.releaser, check=False)
        if merged.returncode != 0:
            conflicted = g("diff", "--name-only", "--diff-filter=U").split()
            ours = [f for f in VERSION_FILES[r.kind] if f in conflicted]
            if ours:
                g("checkout", "-q", "--ours", "--", *ours)
            if take == "main":
                r.set_version(r.releaser, r.v3)
            if edit:
                edit(r.releaser)
            g("add", "-A")
            g("commit", "-q", "-m", message)
        return g("rev-parse", "HEAD")

    def open_cycle(self):
        r = self.repo
        r.set_version(r.releaser, r.placeholder3)
        r.g("commit", "-q", "-am", f"chore: open {r.placeholder3} dev cycle")
        return r.g("rev-parse", "HEAD")

    def tree(self, commit):
        return self.repo.g("rev-parse", f"{commit}^{{tree}}")

    PICKED_OK = ("tree of the merge equals the automatic merge with the project's version lines of develop and the"
                 " merge base set to main's {} (a release picked onto main)")

    # accepted
    def test_pyproject_with_uv_lock(self):
        # the lockfile's dependency twin stands at the project's version at the merge
        # base (0.1.1), and develop has upgraded it since: a line rewritten for its
        # value, or outside the project's block, would conflict or undo the upgrade
        r, base = self.build("pyproject", lock_twin=True, after_fix=upgrade_twin)
        m = self.merge()
        self.assertIn('name = "twin"\nversion = "0.2.0"\n', r.g("show", f"{m}:uv.lock"))
        self.assertOutcome(PASS, self.check(base, m, tag="v0.1.2"), self.PICKED_OK.format("0.1.2"))
        c = self.open_cycle()
        self.assertOutcome(PASS, self.check(base, c, tag="v0.1.2"), "0.1.2 -> 0.1.3.dev0 (pyproject.toml uv.lock)")
        self.assertTree(self.merge_tree(base, "v0.1.2"), self.tree(m))
        # outside tag mode it is refused, as any merge that is not the automatic one
        self.assertOutcome(FAIL, self.check(base, c), "conflicts")

    def test_pyproject_without_a_lockfile(self):
        r, base = self.build("pyproject", lockfile=False)
        m = self.merge()
        self.assertOutcome(PASS, self.check(base, m, tag="v0.1.2"), self.PICKED_OK.format("0.1.2"))
        self.assertOutcome(PASS, self.check(base, self.open_cycle(), tag="v0.1.2"), "(pyproject.toml)")

    def test_a_lockfile_without_the_projects_version_is_left_as_it_is(self):
        r, base = self.build("pyproject", lock_project_version=False)
        m = self.merge()
        self.assertOutcome(PASS, self.check(base, m, tag="v0.1.2"), self.PICKED_OK.format("0.1.2"))

    def test_package_json_with_package_lock_json(self):
        r, base = self.build("package", lock_twin=True, after_fix=upgrade_twin)
        m = self.merge()
        self.assertIn('"version": "4.0.0"', r.g("show", f"{m}:package-lock.json"))
        self.assertOutcome(PASS, self.check(base, m, tag="v3.5.2"), self.PICKED_OK.format("3.5.2"))
        c = self.open_cycle()
        self.assertOutcome(PASS, self.check(base, c, tag="v3.5.2"),
                           "3.5.2 -> 3.5.3-dev0 (package-lock.json package.json)")
        self.assertTree(self.merge_tree(base, "v3.5.2"), self.tree(m))

    def test_package_json_with_crlf_line_endings(self):
        r, base = self.build("package", crlf=True)
        m = self.merge()
        self.assertIn(b'"version": "3.5.2",\r\n', (r.releaser / "package-lock.json").read_bytes())
        self.assertOutcome(PASS, self.check(base, m, tag="v3.5.2"), self.PICKED_OK.format("3.5.2"))
        self.assertOutcome(PASS, self.check(base, self.open_cycle(), tag="v3.5.2"), "3.5.2 -> 3.5.3-dev0")
        self.assertTree(self.merge_tree(base, "v3.5.2"), self.tree(m))

    def test_version_txt(self):
        # only main has changed VERSION.txt since the merge base: the automatic merge is clean
        r, base = self.build("version-txt")
        m = self.merge()
        self.assertEqual(r.g("log", "-1", "--format=%P", m).split()[1], r.main_tip)
        self.assertOutcome(PASS, self.check(base, m, tag="v0.23.2"), "tree of the merge equals the automatic merge (")
        self.assertTree(self.merge_tree(base, "v0.23.2"), self.tree(m))
        r.set_version(r.releaser, "0.23.3-dev")
        r.g("commit", "-q", "-am", "chore: open 0.23.3-dev dev cycle")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.23.2"), "skips the open cycle")

    # refused
    def test_a_hand_edit_in_the_merge_is_refused(self):
        r, base = self.build("pyproject")
        m = self.merge(edit=lambda wt: ReleasedRepo.edit(wt, "app.txt", "folded into the merge\n"))
        self.assertOutcome(FAIL, self.check(base, m, tag="v0.1.2"),
                           "differs from the automatic merge with the project's version lines of develop")

        def requires(wt):
            text = (wt / "pyproject.toml").read_text()
            (wt / "pyproject.toml").write_text(text.replace('requires-python = ">=3.11"', 'requires-python = ">=3.9"'))
        m = self.merge(edit=requires, name="back-merge-2")
        self.assertOutcome(FAIL, self.check(base, m, tag="v0.1.2"),
                           "differs from the automatic merge with the project's version lines of develop")

    def test_a_merge_that_takes_develops_version_is_refused(self):
        r, base = self.build("pyproject")
        m = self.merge(take="develop")
        self.assertEqual(r.version_at(m), "0.1.2.dev0")
        self.assertOutcome(FAIL, self.check(base, m, tag="v0.1.2"),
                           "differs from the automatic merge with the project's version lines of develop")

    def test_a_conflict_outside_the_version_lines_is_refused(self):
        # the pick changed a line that develop has changed again since
        r, base = self.build("pyproject", fix=FIX_LINE_2, after_fix=rework_line_2)
        m = self.merge()
        self.assertOutcome(FAIL, self.check(base, m, tag="v0.1.2"), "conflicts in: app.txt")
        result = self.merge_tree(base, "v0.1.2")
        self.assertEqual(result.returncode, FAIL, result.stdout + result.stderr)
        self.assertTrue(result.stdout.splitlines()[-1].endswith(" conflicts in: app.txt"), result.stdout)

    def test_a_version_line_outside_the_project_table_is_left_as_it_is(self):
        # a [tool] table's version before [project], which develop has changed since
        # the merge base: set to main's with the project's, as a rewrite of the first
        # version line would set it, it would take main's value and undo develop's
        def tool_x(repo):
            text = (repo.releaser / "pyproject.toml").read_text()
            (repo.releaser / "pyproject.toml").write_text(text.replace('version = "0.0.9"', 'version = "0.0.10"'))
            repo.g("commit", "-q", "-am", "chore: tool.x 0.0.10 (#9)")
        r, base = self.build("pyproject", pyproject_head='[tool.x]\nversion = "0.0.9"\n\n', after_fix=tool_x)
        m = self.merge()
        self.assertIn('[tool.x]\nversion = "0.0.10"', r.g("show", f"{m}:pyproject.toml"))
        self.assertOutcome(PASS, self.check(base, m, tag="v0.1.2"), self.PICKED_OK.format("0.1.2"))

    def test_more_than_one_merge_base_is_refused(self):
        # v0.1.2 promoted from a develop that did not yet hold v0.1.1's back-merge,
        # which then landed: each trunk holds a commit of the other that the other's
        # side of it lacks, so the back-merge of the hotfix v0.1.3 has two merge bases
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, "pyproject")
        g = r.g
        g("fetch", "-q", "origin")
        feature_f = g("rev-parse", "origin/develop")
        r.land_back_merge()
        r.promote(feature_f, "0.1.2")
        r.hotfix(version="0.1.3")
        g("fetch", "-q", "origin")
        base = g("rev-parse", "origin/develop")
        self.assertEqual(len(g("merge-base", "--all", base, "origin/main").split()), 2)
        m = self.merge()
        self.assertOutcome(FAIL, self.check(base, m, tag="v0.1.3"), "2 merge bases")
        result = self.merge_tree(base, "v0.1.3")
        self.assertEqual(result.returncode, FAIL, result.stdout + result.stderr)
        self.assertIn("2 merge bases", result.stdout.splitlines()[-1])
        self.assertNotIn(" conflicts in: ", result.stdout.splitlines()[-1])

    # how the merge is built
    def test_the_check_needs_no_identity_and_signs_nothing(self):
        # a CI runner may have no user configured, and a person's configuration may
        # sign every commit; the merge base and develop rewritten are commits all the same
        r, base = self.build("pyproject")
        m = self.merge()
        env = {"GIT_AUTHOR_NAME": "", "GIT_AUTHOR_EMAIL": "", "GIT_COMMITTER_NAME": "", "GIT_COMMITTER_EMAIL": "",
               "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "user.useConfigOnly", "GIT_CONFIG_VALUE_0": "true",
               "GIT_CONFIG_KEY_1": "commit.gpgSign", "GIT_CONFIG_VALUE_1": "true"}
        self.assertOutcome(PASS, self.check(base, m, tag="v0.1.2", env=env), self.PICKED_OK.format("0.1.2"))

    def test_no_ref_index_or_working_tree_is_touched(self):
        r, base = self.build("pyproject")
        m = self.merge()
        g = r.g
        before = (g("for-each-ref"), g("status", "--porcelain", "--untracked-files=all"), g("rev-parse", "HEAD"))
        self.assertOutcome(PASS, self.check(base, m, tag="v0.1.2"))
        self.assertTree(self.merge_tree(base, "v0.1.2"), self.tree(m))
        self.assertEqual((g("for-each-ref"), g("status", "--porcelain", "--untracked-files=all"),
                          g("rev-parse", "HEAD")), before)

    def test_merge_tree_usage(self):
        r, base = self.build("version-txt")
        self.assertOutcome(ERROR, self.sb.script("back-merge-check", "--merge-tree", base, "origin/main",
                                                 cwd=r.releaser), "back-merge-check --merge-tree <develop>")
        self.assertOutcome(FAIL, self.merge_tree(base, "vfoo"), "'vfoo' is not a release tag")
        self.assertOutcome(ERROR, self.merge_tree("0" * 40, "v0.23.2"), f"develop {'0' * 40} is not a commit")


class PromotionRelease(CheckCase):
    """A release made by promotion keeps the automatic merge alone (decision 6 (a)):
    a version change that reached develop during the release is refused in tag mode
    too, however the merge resolves it, and --merge-tree gives no tree for it."""

    def test_a_version_change_during_the_release_is_refused_in_tag_mode(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, "pyproject")
        g = r.g
        g("fetch", "-q", "origin")
        g("switch", "-q", "develop")
        g("merge", "-q", "--ff-only", "origin/develop")
        r.set_version(r.releaser, "0.1.1.dev1")
        g("commit", "-q", "-am", "chore: dev build v0.1.1.dev1")
        g("push", "-q", "origin", "develop")
        base = g("rev-parse", "HEAD")
        # resolved as the merge of a release picked onto main would set the lines
        g("switch", "-q", "-c", "back-merge", base)
        self.sb.run(["git", "merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop after v0.1.1"],
                    r.releaser, check=False)
        g("checkout", "-q", "--ours", "--", "pyproject.toml", "uv.lock")
        r.set_version(r.releaser, "0.1.1")
        g("add", "pyproject.toml", "uv.lock")
        g("commit", "-q", "-m", "Back-merge: main → develop after v0.1.1")
        m = g("rev-parse", "HEAD")
        r.set_version(r.releaser, "0.1.2.dev0")
        g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(FAIL, self.check(base, m, tag="v0.1.1"), "conflicts")
        self.assertOutcome(FAIL, self.check(base, "HEAD", tag="v0.1.1"), "conflicts")
        result = self.merge_tree(base, "v0.1.1")
        self.assertEqual(result.returncode, FAIL, result.stdout + result.stderr)
        self.assertTrue(result.stdout.splitlines()[-1].endswith(" conflicts in: pyproject.toml uv.lock"),
                        result.stdout)

    def test_merge_tree_gives_the_automatic_merge(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, "pyproject")
        r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        auto = r.g("merge-tree", "--write-tree", base, "origin/main")
        self.assertTree(self.merge_tree(base, "v0.1.1"), auto)


class FastForwardFirstRelease(CheckCase):
    """A first release that main reached by a fast-forward has no promotion commit, so
    it counts as picked onto main; the automatic merge, tried first, passes it as before."""

    def test_the_automatic_merge_passes(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, "pyproject", first_release_by_fast_forward=True)
        g = r.g
        g("fetch", "-q", "origin")
        self.assertEqual(g("tag", "--list"), "v0.1.1")
        self.assertEqual(g("rev-list", "--merges", "origin/main"), "")
        base = g("rev-parse", "origin/develop")
        g("switch", "-q", "-c", "back-merge", base)
        g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop after v0.1.1")
        m = g("rev-parse", "HEAD")
        r.set_version(r.releaser, "0.1.2.dev0")
        g("commit", "-q", "-am", "chore: open 0.1.2.dev0 dev cycle")
        self.assertOutcome(PASS, self.check(base, "HEAD", tag="v0.1.1"), "tree of the merge equals the automatic merge (")
        self.assertTree(self.merge_tree(base, "v0.1.1"), g("rev-parse", f"{m}^{{tree}}"))


class ProjectVersion(CheckCase):
    """The versions the check compares are the project's own, read as the version guard
    reads them: [project].version in pyproject.toml, the top-level "version" in
    package.json; a file that cannot be parsed, or holds no such version, fails."""

    def build(self, kind="pyproject", **kw):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.repo = r = ReleasedRepo(self.sb, kind, changelog=False, **kw)
        r.g("fetch", "-q", "origin")
        base = r.g("rev-parse", "origin/develop")
        r.g("switch", "-q", "-c", "back-merge", base)
        r.g("merge", "-q", "--no-ff", "origin/main", "-m", "Back-merge: main → develop")
        return r, base, r.g("rev-parse", "HEAD")

    def open_cycle(self, placeholder, spoil=None):
        r = self.repo
        r.set_version(r.releaser, placeholder)
        if spoil:
            spoil(r.releaser)
        r.g("commit", "-q", "-am", f"chore: open {placeholder} dev cycle")
        return r.g("rev-parse", "HEAD")

    def test_another_tables_version_line_before_the_project_table(self):
        r, base, m = self.build(pyproject_head='[tool.x]\nversion = "0.0.9"\n\n')
        c = self.open_cycle("0.1.2.dev0")
        self.assertIn('[tool.x]\nversion = "0.0.9"', r.g("show", f"{c}:pyproject.toml"))
        self.assertOutcome(PASS, self.check(base, c, tag="v0.1.1"), "0.1.1 -> 0.1.2.dev0 (pyproject.toml uv.lock)")

    def test_a_nested_version_before_the_top_level_one(self):
        r, base, m = self.build("package", package_nested_version=True)
        text = r.g("show", f"{m}:package.json")
        self.assertLess(text.index('"version": "9.9.9"'), text.index('"version": "3.5.1"'))
        self.assertOutcome(PASS, self.check(base, m, tag="v3.5.1"), "head version 3.5.1 equals main's")
        # condition 4's owner rule is unchanged: it takes the last line ending in "{"
        # before a changed version line for its owner, here the nested object's
        self.assertOutcome(FAIL, self.check(base, self.open_cycle("3.5.2-dev0"), tag="v3.5.1"),
                           "package.json: line 6 is not the top-level version")

    def test_an_unparseable_pyproject_toml(self):
        r, base, m = self.build()

        def unterminated(wt):
            text = (wt / "pyproject.toml").read_text()
            (wt / "pyproject.toml").write_text(text.replace('version = "0.1.2.dev0"', 'version = "0.1.2.dev0'))
        result = self.check(base, self.open_cycle("0.1.2.dev0", unterminated), tag="v0.1.1")
        self.assertOutcome(FAIL, result, "cannot read the project's own version of head")
        self.assertIn("cannot be parsed", result.stdout)

    def test_an_unparseable_package_json(self):
        r, base, m = self.build("package")

        def trailing_comma(wt):
            text = (wt / "package.json").read_text()
            (wt / "package.json").write_text(text.replace('"private": true,', '"private": true,,'))
        result = self.check(base, self.open_cycle("3.5.2-dev0", trailing_comma), tag="v3.5.1")
        self.assertOutcome(FAIL, result, "cannot read the project's own version of head")
        self.assertIn("cannot be parsed", result.stdout)

    def test_a_python3_without_tomllib_reads_through_uv(self):
        # a Mac's /usr/bin/python3 is 3.9, without tomllib; a pyproject.toml
        # repository requires uv, which provides a Python 3.11 or later
        r, base, m = self.build()
        shadow = self.sb.tmp / "no-tomllib"
        shadow.mkdir()
        (shadow / "tomllib.py").write_text("raise ImportError('no tomllib in this Python')\n")
        log = self.sb.tmp / "uv-run.log"
        env = {"PYTHONPATH": str(shadow), "FAKE_UV_RUN_LOG": str(log)}
        self.assertOutcome(PASS, self.check(base, self.open_cycle("0.1.2.dev0"), tag="v0.1.1", env=env))
        self.assertIn("run --no-project --quiet --python >=3.11\n", log.read_text())


class CopiesAgree(unittest.TestCase):
    """back-merge-check copies _sot.sh's reading at a commit rather than sourcing it
    (a pin's floor rises only with the pinned script's own file); the copies must agree.
    Likewise git-back-merge carries the check's rule for a release picked onto main."""

    @staticmethod
    def reading_lines(name):
        text = (SCRIPTS / name).read_text()
        return [l.strip() for l in text.splitlines()
                if re.match(r"\s+(pyproject|package|version-txt)\)\s+git show", l)
                or re.match(r"\s+if\s+git cat-file -e|\s+elif git cat-file -e", l)]

    @staticmethod
    def function(name, fn):
        text = (SCRIPTS / name).read_text()
        start = text.index(f"\n{fn}() {{")
        return text[start:text.index("\n}\n", start) + 3]

    def test_version_reading(self):
        ours, theirs = self.reading_lines("back-merge-check"), self.reading_lines("_sot.sh")
        self.assertEqual(len(ours), 6)
        self.assertEqual(ours, theirs)
        reader = self.function("back-merge-check", "sot_version_reader")
        self.assertIn("import tomllib", reader)
        self.assertEqual(reader, self.function("_sot.sh", "sot_version_reader"))

    def test_the_rule_for_a_release_picked_onto_main(self):
        ours = self.function("back-merge-check", "release_promotion")
        self.assertIn("git rev-list --first-parent --merges", ours)
        self.assertEqual(ours, self.function("git-back-merge", "release_promotion"))


if __name__ == "__main__":
    unittest.main()
