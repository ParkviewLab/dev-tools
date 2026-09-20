# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The unit tests of scripts/assemble-workflows.

Each case builds a small handbook of parts and a repository in a temporary
directory, so the tests read no real repository and need no network. The parts
are shaped like the handbook's own: each begins with a blank line, and the
final job's part carries the comment block that introduces it, since the job a
difference is attributed to depends on those leading lines.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import contextlib
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "assemble-workflows"
spec = importlib.util.spec_from_loader("assemble_workflows", importlib.machinery.SourceFileLoader("assemble_workflows", str(SCRIPT)))
aw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aw)

CHANGELOG_COMMENT = (
    "  # Generate the Highlights paragraph and the categorized list, commit the\n"
    "  # new CHANGELOG.md section back to main, and create the GitHub Release.\n"
)

PARTS = {
    "release/head.yml": "name: Release\n\non:\n  push:\n    tags: ['v*']\n\njobs:\n",
    "release/gate.yml": "\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: gate\n",
    "release/docker.yml": "\n  docker:\n    needs: gate\n    steps:\n      - run: docker\n",
    "release/pypi.yml": "\n  pypi:\n    needs: gate\n    steps:\n      - run: pypi\n",
    "release/npm.yml": "\n  npm:\n    needs: gate\n    steps:\n      - run: npm\n",
    "release/installers.yml": "\n  installers:\n    needs: gate\n    steps:\n      - run: installers\n",
    "release/changelog.yml": (
        "\n" + CHANGELOG_COMMENT +
        "  changelog:\n    needs: [gate, TARGET_JOBS]\n    steps:\n"
        "      - run: checkout\n"
        "      # Installers target only: omit this step where the release builds none.\n"
        "      - name: Download all built installers\n"
        "        uses: actions/download-artifact@v7\n"
        "      - name: Install uv\n        run: uv\n"
    ),
    "release/documents.yml": (
        "\n  # Create the GitHub Release for the tag, with GitHub's generated notes.\n"
        "  release:\n    needs: gate\n    steps:\n      - run: release\n"
    ),
    "dev-release/head.yml": "name: Dev release\n\non:\n  workflow_dispatch:\n\njobs:\n",
    "dev-release/gate.yml": "\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: dev gate\n",
    "dev-release/docker.yml": "\n  docker:\n    needs: gate\n    steps:\n      - run: dev docker\n",
    "dev-release/testpypi.yml": "\n  testpypi:\n    needs: gate\n    steps:\n      - run: testpypi\n",
    "dev-release/installers.yml": "\n  installers:\n    needs: gate\n    steps:\n      - run: dev installers\n",
}


def handbook(root: Path) -> Path:
    for name, text in PARTS.items():
        path = root / "templates/.github/workflows" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def repository(root: Path, declaration: str) -> Path:
    workflows = root / ".github/workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / ".assembly.toml").write_text(declaration)
    return root


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = aw.main(list(argv))
    return status, out.getvalue()


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.hb = handbook(root / "handbook")
        self.repo = root / "repo"
        self.addCleanup(self.dir.cleanup)

    def assemble(self, declaration: str, *extra: str) -> tuple[int, str]:
        repository(self.repo, declaration)
        return run("--handbook", str(self.hb), "--repo", str(self.repo), *extra)

    def check(self) -> tuple[int, str]:
        return run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")

    def path(self, name: str = "release.yml") -> Path:
        return self.repo / ".github/workflows" / name

    def release(self) -> str:
        return self.path().read_text()

    def declare(self, declaration: str) -> None:
        (self.repo / ".github/workflows/.assembly.toml").write_text(declaration)

    def tamper(self, name: str, old: str, new: str) -> None:
        path = self.path(name)
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def jobs(self, text: str) -> list[str]:
        return [name for _, name in aw.job_regions(text)]


class AssembleTests(Base):
    def test_image_and_pypi(self) -> None:
        status, _ = self.assemble('targets = ["pypi", "docker"]\ndev = true\n')
        self.assertEqual(status, 0)
        self.assertEqual(self.jobs(self.release()), ["gate", "docker", "pypi", "changelog"])
        self.assertIn("needs: [gate, docker, pypi]", self.release())
        self.assertEqual(self.jobs(self.path("dev-release.yml").read_text()), ["gate", "docker", "testpypi"])

    def test_every_target_in_the_recipe_order(self) -> None:
        self.assemble('targets = ["installers", "npm", "pypi", "docker"]\ndev = true\n')
        self.assertEqual(self.jobs(self.release()), ["gate", "docker", "pypi", "npm", "installers", "changelog"])
        self.assertIn("needs: [gate, docker, pypi, npm, installers]", self.release())
        self.assertEqual(self.jobs(self.path("dev-release.yml").read_text()),
                         ["gate", "docker", "testpypi", "installers"])

    def test_installers_keep_the_download_step(self) -> None:
        self.assemble('targets = ["installers"]\ndev = true\n')
        self.assertIn("download-artifact", self.release())
        self.assertEqual(self.jobs(self.release()), ["gate", "installers", "changelog"])
        self.assertIn("run: dev installers", self.path("dev-release.yml").read_text())

    def test_other_targets_drop_the_download_step(self) -> None:
        self.assemble('targets = ["npm", "docker"]\ndev = false\n')
        self.assertNotIn("download-artifact", self.release())
        self.assertNotIn("Installers target only", self.release())
        self.assertIn("      - run: checkout\n      - name: Install uv\n", self.release())
        self.assertEqual(self.jobs(self.release()), ["gate", "docker", "npm", "changelog"])

    def test_documents_target_has_its_own_final_job(self) -> None:
        self.assemble('targets = ["documents"]\ndev = false\n')
        self.assertEqual(self.jobs(self.release()), ["gate", "release"])
        self.assertFalse(self.path("dev-release.yml").exists())

    def test_no_dev_workflow_without_dev_builds(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        self.assertFalse(self.path("dev-release.yml").exists())

    # The fixture header is a licence line, as a repository's own header is, so the
    # literals below are not this file's licence. REUSE is told to skip them.
    # REUSE-IgnoreStart
    def test_the_header_is_placed_above_both_heads(self) -> None:
        self.assemble('targets = ["docker"]\ndev = true\nheader = "# SPDX-License-Identifier: MIT\\n\\n"\n')
        self.assertTrue(self.release().startswith("# SPDX-License-Identifier: MIT\n\nname: Release"))
        self.assertTrue(self.path("dev-release.yml").read_text().startswith(
            "# SPDX-License-Identifier: MIT\n\nname: Dev release"))
    # REUSE-IgnoreEnd

    def test_a_stale_dev_workflow_is_removed(self) -> None:
        self.assemble('targets = ["docker"]\ndev = true\n')
        self.declare('targets = ["docker"]\ndev = false\n')
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo))
        self.assertEqual(status, 0)
        self.assertIn("removed", output)
        self.assertFalse(self.path("dev-release.yml").exists())
        self.assertEqual(self.check()[0], 0)

    def test_the_write_path_names_the_declared_slots(self) -> None:
        _, output = self.assemble('targets = ["docker"]\ndev = false\n[[slots]]\njob = "docker"\nreason = "three images"\n')
        self.assertIn("restore them by hand: docker", output)


class CheckTests(Base):
    def test_check_passes_on_the_assembly(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("matches the assembly", output)

    def test_check_names_the_job_of_an_undeclared_difference(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        self.tamper("release.yml", "      - run: docker\n", "      - run: docker --three-images\n")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn("docker: differs from its part, not declared", output)

    def test_check_passes_a_declared_slot(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n[[slots]]\njob = "docker"\nreason = "three images, one matrix"\n')
        self.tamper("release.yml", "      - run: docker\n", "      - run: docker --three-images\n")
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("declared as a slot", output)

    def test_a_comment_belongs_to_the_job_it_introduces(self) -> None:
        """The lines above a job's key are part of that job, not of the one before it."""
        self.assemble('targets = ["docker"]\ndev = false\n')
        self.tamper("release.yml", "  # Generate the Highlights", "  # TAMPERED: Generate the Highlights")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn("changelog: differs from its part, not declared", output)
        self.assertNotIn("docker: differs", output)

    def test_a_slot_does_not_excuse_the_next_jobs_comment(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n[[slots]]\njob = "docker"\nreason = "three images"\n')
        self.tamper("release.yml", "  # Generate the Highlights", "  # TAMPERED: Generate the Highlights")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn("changelog: differs from its part, not declared", output)

    def test_a_slot_can_be_declared_for_the_head(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n[[slots]]\njob = "the head"\nreason = "why this repository differs"\n')
        self.tamper("release.yml", "name: Release\n", "name: Release\n\n# Why this repository differs.\n")
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("the head: differs from its part, declared as a slot", output)

    def test_a_release_slot_does_not_excuse_the_dev_workflow(self) -> None:
        self.assemble('targets = ["docker"]\ndev = true\n[[slots]]\njob = "docker"\nreason = "three images"\n')
        self.tamper("dev-release.yml", "      - run: dev docker\n", "      - run: dev docker --three-images\n")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn("dev-release.yml: docker: differs from its part, not declared", output)

    def test_a_slot_scoped_to_both_excuses_the_dev_workflow(self) -> None:
        self.assemble('targets = ["docker"]\ndev = true\n[[slots]]\njob = "docker"\nreason = "three images"\nworkflow = "both"\n')
        self.tamper("dev-release.yml", "      - run: dev docker\n", "      - run: dev docker --three-images\n")
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("dev-release.yml: docker: differs from its part, declared as a slot", output)

    def test_check_reports_a_missing_workflow(self) -> None:
        repository(self.repo, 'targets = ["docker"]\ndev = false\n')
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn("missing", output)

    def test_check_reports_a_dev_workflow_that_is_not_declared(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        self.path("dev-release.yml").write_text("name: Dev release\n")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn("the declaration has no dev builds", output)

    def test_a_file_without_jobs_has_only_a_head(self) -> None:
        self.assertEqual(aw.job_of("name: X\n\non:\n  push:\n    tags: ['v*']\n", 4), aw.HEAD)
        self.assertEqual(aw.job_regions("name: X\n\non:\n  push:\n"), [])


class DeclarationErrorTests(Base):
    def assert_declaration_error(self, declaration: str, message: str) -> None:
        status, output = self.assemble(declaration)
        self.assertEqual(status, 2, output)
        self.assertIn(message, output)

    def test_an_unknown_target(self) -> None:
        self.assert_declaration_error('targets = ["cargo"]\ndev = false\n', "unknown target")

    def test_documents_stands_alone(self) -> None:
        self.assert_declaration_error('targets = ["documents", "docker"]\ndev = false\n', "stands alone")

    def test_targets_must_be_a_non_empty_list(self) -> None:
        self.assert_declaration_error('dev = false\n', "non-empty list")

    def test_targets_must_be_names(self) -> None:
        self.assert_declaration_error('targets = [1]\n', "non-empty list")

    def test_malformed_toml(self) -> None:
        self.assert_declaration_error('targets = ["docker"\n', "Unclosed array")

    def test_dev_must_be_a_boolean(self) -> None:
        self.assert_declaration_error('targets = ["docker"]\ndev = "yes"\n', "`dev` must be true or false")

    def test_the_header_must_be_a_string(self) -> None:
        self.assert_declaration_error('targets = ["docker"]\nheader = 3\n', "`header` must be a string")

    def test_dev_needs_a_target_with_a_dev_part(self) -> None:
        self.assert_declaration_error('targets = ["npm"]\ndev = true\n', "has a dev part")

    def test_a_slot_must_be_a_table_array(self) -> None:
        self.assert_declaration_error('targets = ["docker"]\n[slots]\njob = "docker"\n', "`[[slots]]` table")

    def test_a_slot_needs_a_job(self) -> None:
        self.assert_declaration_error('targets = ["docker"]\n[[slots]]\nreason = "x"\n', "each slot needs a `job`")

    def test_a_slot_workflow_is_one_of_three(self) -> None:
        self.assert_declaration_error('targets = ["docker"]\n[[slots]]\njob = "docker"\nworkflow = "both-of-them"\n',
                                      "`workflow` is one of")

    def test_neither_a_declaration_nor_a_workflow(self) -> None:
        (self.repo / ".github/workflows").mkdir(parents=True)
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo))
        self.assertEqual(status, 2)
        self.assertIn("no .assembly.toml to declare the targets", output)

    def test_a_missing_part(self) -> None:
        (self.hb / "templates/.github/workflows/release/pypi.yml").unlink()
        self.assert_declaration_error('targets = ["pypi"]\ndev = false\n', "is missing")


class InferenceTests(Base):
    """A repository without a declaration has its targets read from its workflow."""

    def build(self, declaration: str) -> None:
        repository(self.repo, declaration)
        run("--handbook", str(self.hb), "--repo", str(self.repo))
        (self.repo / ".github/workflows/.assembly.toml").unlink()

    def test_targets_are_read_from_the_jobs(self) -> None:
        self.build('targets = ["docker", "pypi"]\ndev = true\n')
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("the targets are read from the workflow (docker, pypi)", output)
        self.assertIn("release.yml: matches the assembly", output)
        self.assertIn("dev-release.yml: matches the assembly", output)

    def test_the_documents_target_is_recognised(self) -> None:
        self.build('targets = ["documents"]\ndev = false\n')
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("(documents)", output)

    # REUSE-IgnoreStart
    def test_the_header_is_read_from_the_workflow(self) -> None:
        self.build('targets = ["docker"]\ndev = false\nheader = "# SPDX-License-Identifier: MIT\\n\\n"\n')
        status, output = self.check()
        self.assertEqual(status, 0)
        self.assertIn("release.yml: matches the assembly", output)
    # REUSE-IgnoreEnd

    def test_drift_in_the_dev_workflow_is_reported(self) -> None:
        self.build('targets = ["docker"]\ndev = true\n')
        self.tamper("dev-release.yml", "      - run: dev docker\n", "      - run: dev docker --changed\n")
        status, output = self.check()
        self.assertEqual(status, 1)
        self.assertIn("dev-release.yml: docker: differs from its part, not declared", output)

    def test_a_repository_with_no_workflow_is_an_error(self) -> None:
        (self.repo / ".github/workflows").mkdir(parents=True)
        status, output = self.check()
        self.assertEqual(status, 2)
        self.assertIn("no .assembly.toml", output)


if __name__ == "__main__":
    unittest.main()
