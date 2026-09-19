# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the profiles mode of tests/acceptance/acceptance.py.

Run from the repository root:

    python3 -m unittest discover -s tests -v

Standard library only, and offline: only the comparison logic that does not
reach the network is exercised (published_comparison, given the two texts
directly) and tests/acceptance/representatives.json, which is read from disk.
acceptance.py is loaded by path, as tests/test_generate_changelog.py loads the
script; the module it defines lives under "acceptance", not "generate_changelog".
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "tests" / "acceptance" / "acceptance.py"
REPRESENTATIVES = ROOT / "tests" / "acceptance" / "representatives.json"


def load_acceptance():
    loader = importlib.machinery.SourceFileLoader("acceptance", str(ACCEPTANCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


acc = load_acceptance()

SECTION = (
    "## [v1.0.0] - 2026-01-01\n\n"
    "### Highlights\n\n"
    "_Highlights were not generated for this release._\n\n"
    "### Features\n\n"
    "- Add the thing (#1)\n"
)
DIFFERENT_SECTION = SECTION.replace("Add the thing", "Add another thing")


class PublishedComparisonTests(unittest.TestCase):
    """published_comparison is the profiles mode's comparison, once a tag's
    Release was made by the shared generator: pure given the dry run's list and
    the published Release body, so it needs no network to test."""

    def test_a_dry_run_matching_the_published_release_passes(self):
        _, listing = acc.split_section(SECTION)
        r = acc.published_comparison("example", "v1.0.0", listing, SECTION)
        self.assertTrue(r.passed)
        self.assertEqual(r.basis, "published")
        self.assertEqual(r.listing, listing)
        self.assertEqual(r.detail, "")

    def test_a_dry_run_differing_from_the_published_release_fails_with_a_diff(self):
        _, listing = acc.split_section(SECTION)
        r = acc.published_comparison("example", "v1.0.0", listing, DIFFERENT_SECTION)
        self.assertFalse(r.passed)
        self.assertIn("Add the thing", r.detail)
        self.assertIn("Add another thing", r.detail)

    def test_no_github_release_fails_without_a_diff(self):
        _, listing = acc.split_section(SECTION)
        r = acc.published_comparison("example", "v1.0.0", listing, None)
        self.assertFalse(r.passed)
        self.assertIn("no GitHub Release", r.detail)


class RepresentativesTests(unittest.TestCase):
    """The real-history check's set (tests/acceptance/representatives.json):
    one active representative per profile with a repository, each with a reason,
    and the pending profiles carrying no repository."""

    def test_every_active_representative_has_a_repo_and_a_reason(self):
        for rep in acc.representatives():
            self.assertTrue(rep["repo"])
            self.assertTrue(rep["reason"])

    def test_the_active_profiles_match_the_2026_09_18_ruling(self):
        by_profile = {rep["profile"]: rep["repo"] for rep in acc.representatives()}
        self.assertEqual(
            by_profile,
            {
                "pyproject.toml, GHCR": "paper-boxing",
                "pyproject.toml, PyPI": "cogrind-workshop",
                "pyproject.toml, PyPI and GHCR": "smalt-mcp",
                "package.json, npm and GHCR": "jonobones",
                "package.json, installers": "pensa-grex",
            },
        )

    def test_pending_profiles_carry_no_repository(self):
        data = json.loads(REPRESENTATIVES.read_text(encoding="utf-8"))
        pending = [p for p in data["profiles"] if p["status"] == "pending"]
        self.assertEqual({p["profile"] for p in pending}, {"npm only", "Cargo.toml, installers"})
        self.assertTrue(all(p["repo"] is None for p in pending))


if __name__ == "__main__":
    unittest.main()
