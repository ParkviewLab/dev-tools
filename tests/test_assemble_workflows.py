# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The unit tests of scripts/assemble-workflows.

Each case builds a small handbook of parts and a repository in a temporary
directory, so the tests read no real repository and need no network.
"""

from __future__ import annotations

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

PARTS = {
    "release/head.yml": "name: Release\n\non:\n  push:\n    tags: ['v*']\n\njobs:\n",
    "release/gate.yml": "  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: gate\n",
    "release/docker.yml": "  docker:\n    needs: gate\n    steps:\n      - run: docker\n",
    "release/pypi.yml": "  pypi:\n    needs: gate\n    steps:\n      - run: pypi\n",
    "release/npm.yml": "  npm:\n    needs: gate\n    steps:\n      - run: npm\n",
    "release/installers.yml": "  installers:\n    needs: gate\n    steps:\n      - run: installers\n",
    "release/changelog.yml": (
        "  changelog:\n    needs: [gate, TARGET_JOBS]\n    steps:\n"
        "      - run: checkout\n"
        "      # Installers target only: omit this step where the release builds none.\n"
        "      - name: Download all built installers\n"
        "        uses: actions/download-artifact@v7\n"
        "      - name: Install uv\n        run: uv\n"
    ),
    "release/documents.yml": "  release:\n    needs: gate\n    steps:\n      - run: release\n",
    "dev-release/head.yml": "name: Dev release\n\non:\n  workflow_dispatch:\n\njobs:\n",
    "dev-release/gate.yml": "  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: dev gate\n",
    "dev-release/docker.yml": "  docker:\n    needs: gate\n    steps:\n      - run: dev docker\n",
    "dev-release/testpypi.yml": "  testpypi:\n    needs: gate\n    steps:\n      - run: testpypi\n",
    "dev-release/installers.yml": "  installers:\n    needs: gate\n    steps:\n      - run: dev installers\n",
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


class AssembleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.hb = handbook(root / "handbook")
        self.repo = root / "repo"
        self.addCleanup(self.dir.cleanup)

    def assemble(self, declaration: str, *extra: str) -> tuple[int, str]:
        repository(self.repo, declaration)
        return run("--handbook", str(self.hb), "--repo", str(self.repo), *extra)

    def release(self) -> str:
        return (self.repo / ".github/workflows/release.yml").read_text()

    def jobs(self, text: str) -> list[str]:
        start = text.index("\njobs:\n")
        return aw.JOB_RE.findall(text, start + 1)

    def test_image_and_pypi(self) -> None:
        status, _ = self.assemble('targets = ["pypi", "docker"]\ndev = true\n')
        self.assertEqual(status, 0)
        self.assertEqual(self.jobs(self.release()), ["gate", "docker", "pypi", "changelog"])
        self.assertIn("needs: [gate, docker, pypi]", self.release())
        dev = (self.repo / ".github/workflows/dev-release.yml").read_text()
        self.assertEqual(self.jobs(dev), ["gate", "docker", "testpypi"])

    def test_installers_keep_the_download_step(self) -> None:
        self.assemble('targets = ["installers"]\ndev = false\n')
        self.assertIn("download-artifact", self.release())
        self.assertEqual(self.jobs(self.release()), ["gate", "installers", "changelog"])

    def test_other_targets_drop_the_download_step(self) -> None:
        self.assemble('targets = ["npm", "docker"]\ndev = false\n')
        self.assertNotIn("download-artifact", self.release())
        self.assertEqual(self.jobs(self.release()), ["gate", "docker", "npm", "changelog"])

    def test_documents_target_has_its_own_final_job(self) -> None:
        self.assemble('targets = ["documents"]\ndev = false\n')
        self.assertEqual(self.jobs(self.release()), ["gate", "release"])
        self.assertFalse((self.repo / ".github/workflows/dev-release.yml").exists())

    def test_no_dev_workflow_without_dev_builds(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        self.assertFalse((self.repo / ".github/workflows/dev-release.yml").exists())

    def test_the_header_is_placed_above_the_head(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\nheader = "# SPDX-License-Identifier: MIT\\n\\n"\n')
        self.assertTrue(self.release().startswith("# SPDX-License-Identifier: MIT\n\nname: Release"))

    def test_check_passes_on_the_assembly(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 0)
        self.assertIn("matches the assembly", output)

    def test_check_names_the_job_of_an_undeclared_difference(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        path = self.repo / ".github/workflows/release.yml"
        path.write_text(path.read_text().replace("      - run: docker\n", "      - run: docker --three-images\n"))
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 1)
        self.assertIn("docker: differs from its part, not declared", output)

    def test_check_passes_a_declared_slot(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n[[slots]]\njob = "docker"\nreason = "three images, one matrix"\n')
        path = self.repo / ".github/workflows/release.yml"
        path.write_text(path.read_text().replace("      - run: docker\n", "      - run: docker --three-images\n"))
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 0)
        self.assertIn("declared as a slot", output)

    def test_check_reports_a_missing_workflow(self) -> None:
        repository(self.repo, 'targets = ["docker"]\ndev = false\n')
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 1)
        self.assertIn("missing", output)

    def test_check_reports_a_dev_workflow_that_is_not_declared(self) -> None:
        self.assemble('targets = ["docker"]\ndev = false\n')
        (self.repo / ".github/workflows/dev-release.yml").write_text("name: Dev release\n")
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 1)
        self.assertIn("the declaration says the repository has no dev builds", output)

    def test_an_unknown_target_is_a_declaration_error(self) -> None:
        status, output = self.assemble('targets = ["cargo"]\ndev = false\n')
        self.assertEqual(status, 2)
        self.assertIn("unknown target", output)

    def test_documents_stands_alone(self) -> None:
        status, output = self.assemble('targets = ["documents", "docker"]\ndev = false\n')
        self.assertEqual(status, 2)
        self.assertIn("stands alone", output)

    def test_neither_a_declaration_nor_a_workflow_is_an_error(self) -> None:
        (self.repo / ".github/workflows").mkdir(parents=True)
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo))
        self.assertEqual(status, 2)
        self.assertIn("no .assembly.toml to declare the targets", output)

    def test_a_missing_part_is_an_error(self) -> None:
        (self.hb / "templates/.github/workflows/release/pypi.yml").unlink()
        status, output = self.assemble('targets = ["pypi"]\ndev = false\n')
        self.assertEqual(status, 2)
        self.assertIn("is missing", output)


if __name__ == "__main__":
    unittest.main()


class InferenceTests(unittest.TestCase):
    """A repository without a declaration has its targets read from its workflow."""

    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.hb = handbook(root / "handbook")
        self.repo = root / "repo"
        self.addCleanup(self.dir.cleanup)

    def build(self, declaration: str) -> None:
        repository(self.repo, declaration)
        run("--handbook", str(self.hb), "--repo", str(self.repo))
        (self.repo / ".github/workflows/.assembly.toml").unlink()

    def test_targets_are_read_from_the_jobs(self) -> None:
        self.build('targets = ["docker", "pypi"]\ndev = true\n')
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 0)
        self.assertIn("the targets are read from the workflow (docker, pypi)", output)
        self.assertIn("release.yml: matches the assembly", output)
        self.assertIn("dev-release.yml: matches the assembly", output)

    def test_the_documents_target_is_recognised(self) -> None:
        self.build('targets = ["documents"]\ndev = false\n')
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 0)
        self.assertIn("(documents)", output)

    def test_a_repository_with_no_workflow_is_an_error(self) -> None:
        (self.repo / ".github/workflows").mkdir(parents=True)
        status, output = run("--handbook", str(self.hb), "--repo", str(self.repo), "--check")
        self.assertEqual(status, 2)
        self.assertIn("no .assembly.toml", output)
