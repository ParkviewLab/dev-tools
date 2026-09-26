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
tag that shadows main.
"""

from __future__ import annotations

import json
import re
import unittest

from backmerge_support import ReleasedRepo, Sandbox, set_package_version, set_pyproject_version

PASS, FAIL, ERROR = 0, 1, 2


class CheckCase(unittest.TestCase):
    sb: Sandbox
    repo: ReleasedRepo

    def check(self, base, head, main="origin/main", tag=None, cwd=None):
        args = [base, head, main] + ([tag] if tag else [])
        return self.sb.script("back-merge-check", *args, cwd=cwd or self.repo.releaser)

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
        self.assertOutcome(FAIL, self.check(self.BASE, self.commit_all("chore: a dynamic version")),
                           "no version line in head's pyproject.toml")

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
        # in a -U0 diff it reads "+++...", the form of a file header
        wt = self.open_cycle_on_m("x-plusplus")
        with open(wt / "pyproject.toml", "a") as fh:
            fh.write("++injected\n")
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


class CopiesAgree(unittest.TestCase):
    """back-merge-check copies _sot.sh's reading at a commit rather than sourcing it
    (a pin's floor rises only with the pinned script's own file); the copies must agree."""

    @staticmethod
    def reading_lines(name):
        from backmerge_support import SCRIPTS
        text = (SCRIPTS / name).read_text()
        return [l.strip() for l in text.splitlines()
                if re.match(r"\s+(pyproject|package|version-txt)\)\s+git show", l)
                or re.match(r"\s+if\s+git cat-file -e|\s+elif git cat-file -e", l)]

    def test_version_reading(self):
        ours, theirs = self.reading_lines("back-merge-check"), self.reading_lines("_sot.sh")
        self.assertEqual(len(ours), 6)
        self.assertEqual(ours, theirs)


if __name__ == "__main__":
    unittest.main()
