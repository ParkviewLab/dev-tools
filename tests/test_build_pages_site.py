# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for scripts/build-pages-site.

Run from the repository root:

    python3 -m unittest discover -s tests -v

Standard library only. The script has no .py suffix, so it is loaded by path.
Every build runs against a temporary repository; the tests that need git
(the tag resolution, the origin remote) skip when git is not installed.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-pages-site"
GIT = shutil.which("git")


def load_script():
    loader = importlib.machinery.SourceFileLoader("build_pages_site", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


bps = load_script()

HTML_DOC = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>{title}</title>\n{meta}'
    "</head>\n<body>\n{body}\n</body>\n</html>\n"
)


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        [GIT, "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class Fixture(unittest.TestCase):
    """A temporary repository (docs/, optionally site/) and a fresh --out beside it."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bps-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        if GIT:  # a repository with no origin, so the name comes from the environment
            git(self.repo, "init", "-q")
        self.out = self.tmp / "out"
        patcher = mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "ParkviewLab/example"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, rel: str, text: str) -> Path:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def md(self, rel: str, title: str = "A title", body: str = "") -> Path:
        return self.write(rel, f"# {title}\n\n{body}\n")

    def html(self, rel: str, title: str = "A title", description: str | None = None, body: str = "") -> Path:
        meta = f'<meta name="description" content="{description}">\n' if description else ""
        return self.write(rel, HTML_DOC.format(title=title, meta=meta, body=body))

    def run_build(self, *extra: str, tag: str | None = "v1.2.3", out: Path | None = None) -> tuple[int, str, str]:
        argv = ["--out", str(out or self.out), "--repo", str(self.repo)]
        if tag is not None:
            argv += ["--tag", tag]
        argv += list(extra)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bps.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def build(self, *extra: str, **kw) -> str:
        """Build, assert success, return the log."""
        code, log, err = self.run_build(*extra, **kw)
        self.assertEqual(code, 0, err)
        return log

    def build_fails(self, *extra: str, **kw) -> str:
        """Build, assert failure, return the error text."""
        code, log, err = self.run_build(*extra, **kw)
        self.assertEqual(code, 1, log)
        self.assertIn("build-pages-site: error:", err)
        return err

    def page(self, rel: str = "index.html") -> str:
        return (self.out / rel).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Grouping, twin pairing, titles
# --------------------------------------------------------------------------- #


class GroupingTests(unittest.TestCase):
    def doc(self, name: str, kind: str) -> object:
        return bps.Document(PurePosixPath(name), kind, "t")

    def test_five_groups(self) -> None:
        self.assertEqual(bps.group_of(self.doc("northstar.html", "html")), "northstar")
        self.assertEqual(bps.group_of(self.doc("northstar.md", "md")), "northstar")
        self.assertEqual(bps.group_of(self.doc("study.html", "html")), "html")
        self.assertEqual(bps.group_of(self.doc("notes.md", "md")), "specs")
        self.assertEqual(bps.group_of(self.doc("in-flight_ideas.md", "md")), "ideas")
        self.assertEqual(bps.group_of(self.doc("theme_ideas.md", "md")), "ideas")
        self.assertEqual(bps.group_of(self.doc("CONTRIBUTING.md", "md")), "contributing")
        self.assertEqual(bps.group_of(self.doc("contributing.md", "md")), "contributing")

    def test_an_html_ideas_document_is_an_html_document(self) -> None:
        self.assertEqual(bps.group_of(self.doc("model_ideas.html", "html")), "html")

    def test_group_order(self) -> None:
        self.assertEqual([k for k, _ in bps.GROUPS], ["northstar", "html", "specs", "ideas", "contributing"])


class ScanTests(Fixture):
    def scan(self) -> tuple[object, list[str]]:
        untitled: list[str] = []
        return bps.scan_folder(self.repo / "docs", PurePosixPath("."), untitled), untitled

    def test_twin_listed_once_under_the_html(self) -> None:
        self.html("docs/plan.html", "Plan")
        self.md("docs/plan.md", "Plan (source)")
        self.md("docs/other.md", "Other")
        folder, untitled = self.scan()
        self.assertEqual(untitled, [])
        listed = {str(d.rel): d for d in folder.documents}
        self.assertEqual(set(listed), {"plan.html", "other.md"})
        self.assertEqual(str(listed["plan.html"].twin.rel), "plan.md")
        self.assertIsNone(listed["other.md"].twin)

    def test_untitled_documents_are_collected(self) -> None:
        self.write("docs/blank.md", "no heading here\n")
        self.write("docs/blank.html", "<html><head></head><body></body></html>")
        _, untitled = self.scan()
        self.assertEqual(sorted(untitled), ["blank.html", "blank.md"])

    def test_subfolders_without_documents_are_dropped(self) -> None:
        self.md("docs/guide/one.md")
        self.write("docs/assets/logo.svg", "<svg/>")
        self.md("docs/deep/deeper/two.md")
        folder, _ = self.scan()
        self.assertEqual([str(f.rel) for f in folder.subfolders], ["deep", "guide"])
        deep = folder.subfolders[0]
        self.assertEqual(deep.documents, [])
        self.assertTrue(deep.holds_documents)

    def test_own_index_is_noticed(self) -> None:
        self.html("docs/guide/index.html", "Guide")
        folder, _ = self.scan()
        self.assertTrue(folder.subfolders[0].has_own_index)
        self.assertFalse(folder.has_own_index)

    def test_non_documents_are_ignored(self) -> None:
        self.write("docs/data.json", "{}")
        self.write("docs/.DS_Store", "")
        folder, _ = self.scan()
        self.assertEqual(folder.documents, [])


class TitleTests(Fixture):
    def test_markdown_first_h1(self) -> None:
        path = self.write("docs/a.md", "Intro line\n\n## Not it\n\n#   The   title  ##\n\n# Second\n")
        self.assertEqual(bps.markdown_title(path), "The title")

    def test_markdown_skips_fenced_code(self) -> None:
        path = self.write("docs/a.md", "```\n# not a heading\n```\n\n~~~sh\n# nor this\n~~~\n# Real\n")
        self.assertEqual(bps.markdown_title(path), "Real")

    def test_markdown_hash_without_space_is_not_a_heading(self) -> None:
        path = self.write("docs/a.md", "#hashtag\n")
        self.assertEqual(bps.markdown_title(path), "")

    def test_html_title_and_description(self) -> None:
        path = self.html("docs/a.html", "A &amp; B\n  &mdash; C", "What  it\nis")
        self.assertEqual(bps.html_head(path), ("A & B — C", "What it is"))

    def test_html_without_description(self) -> None:
        path = self.html("docs/a.html", "Only")
        self.assertEqual(bps.html_head(path), ("Only", None))

    def test_untitled_document_fails_the_build(self) -> None:
        self.md("docs/ok.md", "Fine")
        self.write("docs/bad.md", "no heading\n")
        err = self.build_fails()
        self.assertIn("documents without a title", err)
        self.assertIn("bad.md", err)


# --------------------------------------------------------------------------- #
# The tag and the repository
# --------------------------------------------------------------------------- #


class TagTests(Fixture):
    def test_explicit_tag(self) -> None:
        self.assertEqual(bps.release_tag("v1.2.3", self.repo), "v1.2.3")
        self.assertEqual(bps.release_tag("v1.2.3-rc.1", self.repo), "v1.2.3-rc.1")

    def test_explicit_tag_must_look_like_a_release(self) -> None:
        for bad in ("1.2.3", "v1.2", "latest", "v1.2.3 "):
            with self.assertRaises(bps.BuildError):
                bps.release_tag(bad, self.repo)

    @unittest.skipUnless(GIT, "git is not installed")
    def test_newest_reachable_tag_even_when_head_has_moved_on(self) -> None:
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "one")
        git(self.repo, "tag", "v1.0.0")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "changelog")
        # The late-tag leniency: a commit after the tag still builds, pinned to that tag.
        self.assertEqual(bps.release_tag(None, self.repo), "v1.0.0")
        git(self.repo, "tag", "v1.1.0")
        self.assertEqual(bps.release_tag(None, self.repo), "v1.1.0")

    @unittest.skipUnless(GIT, "git is not installed")
    def test_no_v_tag_refuses(self) -> None:
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "one")
        with self.assertRaisesRegex(bps.BuildError, "no v\\* tag reachable"):
            bps.release_tag(None, self.repo)
        git(self.repo, "tag", "1.0.0")  # not a v* tag
        with self.assertRaises(bps.BuildError):
            bps.release_tag(None, self.repo)


class RepositoryTests(Fixture):
    @unittest.skipUnless(GIT, "git is not installed")
    def test_origin_remote_wins(self) -> None:
        git(self.repo, "remote", "add", "origin", "git@github.com:ParkviewLab/from-remote.git")
        repo = bps.repository(str(self.repo))
        self.assertEqual((repo.owner, repo.name), ("ParkviewLab", "from-remote"))
        self.assertEqual(repo.github_url, "https://github.com/ParkviewLab/from-remote")

    def test_remote_url_shapes(self) -> None:
        for url in (
            "git@github.com:ParkviewLab/x.git",
            "https://github.com/ParkviewLab/x.git",
            "https://github.com/ParkviewLab/x",
            "ssh://git@github.com/ParkviewLab/x.git",
            "https://github.com/ParkviewLab/x/",
        ):
            m = bps.REMOTE_RE.search(url)
            self.assertIsNotNone(m, url)
            self.assertEqual((m["owner"], m["name"]), ("ParkviewLab", "x"), url)
        self.assertIsNone(bps.REMOTE_RE.search("git@gitlab.com:ParkviewLab/x.git"))

    def test_environment_fallback(self) -> None:
        repo = bps.repository(str(self.repo))
        self.assertEqual((repo.owner, repo.name), ("ParkviewLab", "example"))

    def test_no_repository_to_link_to(self) -> None:
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": ""}):
            with self.assertRaisesRegex(bps.BuildError, "cannot tell which GitHub repository"):
                bps.repository(str(self.repo))

    def test_repo_must_be_a_directory(self) -> None:
        with self.assertRaises(bps.BuildError):
            bps.repository(str(self.repo / "missing"))


# --------------------------------------------------------------------------- #
# The shell
# --------------------------------------------------------------------------- #

ALL_VALUES = {name: name.upper() for name in bps.PLACEHOLDERS}


class ShellTests(Fixture):
    def test_placeholder_set(self) -> None:
        self.assertEqual(bps.PLACEHOLDERS, ("title", "intro", "groups", "root", "tag", "repo", "footer"))

    def test_substitution_inline(self) -> None:
        shell = bps.Shell("<title>{{title}}</title><b>{{tag}}/{{repo}}</b>\n", None)
        self.assertEqual(bps.fill(shell, ALL_VALUES), "<title>TITLE</title><b>TAG/REPO</b>\n")

    def test_multi_line_value_indented_to_its_placeholder(self) -> None:
        shell = bps.Shell("<x>\n    {{groups}}\n</x>\n", None)
        values = dict(ALL_VALUES, groups="<div>\n  <p>a</p>\n</div>")
        self.assertEqual(bps.fill(shell, values), "<x>\n    <div>\n      <p>a</p>\n    </div>\n</x>\n")

    def test_single_line_and_empty_values_at_line_start(self) -> None:
        shell = bps.Shell("  {{tag}}\n  {{intro}}\n{{root}}x\n", None)
        values = dict(ALL_VALUES, intro="", root="../../")
        self.assertEqual(bps.fill(shell, values), "  TAG\n\n../../x\n")

    def test_unknown_placeholder_fails(self) -> None:
        self.md("docs/a.md")
        shell = self.write("shell.html", "<html>{{groups}}{{titel}}</html>\n")
        err = self.build_fails("--shell", str(shell))
        self.assertIn("unknown placeholder {{titel}}", err)

    def test_shell_without_groups_fails(self) -> None:
        self.md("docs/a.md")
        shell = self.write("shell.html", "<html>{{title}}</html>\n")
        err = self.build_fails("--shell", str(shell))
        self.assertIn("no {{groups}} placeholder", err)

    def test_missing_shell_file_fails(self) -> None:
        self.md("docs/a.md")
        err = self.build_fails("--shell", str(self.repo / "nope.html"))
        self.assertIn("no such file", err)

    def test_custom_shell_is_used_and_not_published_from_site(self) -> None:
        self.md("docs/a.md", "Alpha")
        self.write("site/intro.html", "<p>Hello</p>\n")
        shell = self.write(
            "site/shell.html",
            "<!DOCTYPE html>\n<html><head><title>{{repo}} {{tag}}</title></head>\n<body>\n"
            "<a href=\"{{root}}\">home</a>\n  {{intro}}\n  {{groups}}\n<footer>\n  {{footer}}\n</footer>\n</body></html>\n",
        )
        self.build("--shell", str(shell))
        self.assertFalse((self.out / "shell.html").exists())
        self.assertFalse((self.out / "intro.html").exists())
        page = self.page()
        self.assertIn("<title>example v1.2.3</title>", page)
        self.assertIn("  <p>Hello</p>\n", page)
        self.assertIn('href="https://github.com/ParkviewLab/example/blob/v1.2.3/docs/a.md">Alpha</a>', page)
        self.assertIn('  <span>Published from <a href="https://github.com/ParkviewLab/example/tree/v1.2.3">v1.2.3</a></span>\n', page)

    def test_default_shell_discipline(self) -> None:
        shell = bps.DEFAULT_SHELL
        urls = set(re.findall(r"https?://[^\s\"'<>)]*", shell))
        self.assertEqual(urls, {"http://www.w3.org/2000/svg"})  # an identifier, not a request
        self.assertNotIn("fonts.googleapis", shell)
        self.assertNotIn("@font-face", shell)
        self.assertNotIn("@import", shell)
        self.assertNotIn("url(", shell)
        self.assertNotIn("<script", shell)
        self.assertNotIn("<link", shell)
        self.assertRegex(shell, r"@media\s*\(max-width:\s*\d+px\)")
        self.assertIn("--teal:#00C2C7", shell)
        self.assertIn("--paper:#f3eee2", shell)

    def test_default_shell_uses_only_known_placeholders(self) -> None:
        names = {m.group(2) for m in bps.PLACEHOLDER_RE.finditer(bps.DEFAULT_SHELL)}
        self.assertEqual(names, set(bps.PLACEHOLDERS))

    def test_default_shell_output_fetches_nothing(self) -> None:
        self.md("docs/a.md", "Alpha")
        self.build()
        page = self.page()
        for url in re.findall(r"https?://[^\s\"'<>)]*", page):
            self.assertTrue(
                url == "http://www.w3.org/2000/svg" or url.startswith("https://github.com/ParkviewLab/example"), url
            )


# --------------------------------------------------------------------------- #
# The build
# --------------------------------------------------------------------------- #


class IndexTests(Fixture):
    def test_docs_alone_when_there_is_no_site(self) -> None:
        self.md("docs/northstar.md", "North")
        self.md("docs/CONTRIBUTING.md", "Contributing")
        self.write("README.md", "# not published\n")
        self.write("dev-tools/scripts/build-pages-site", "# a checkout of dev-tools at the repository root\n")
        log = self.build()
        self.assertIn("no site/ directory; publishing docs/ alone", log)
        self.assertIn("no introduction", log)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["docs", "index.html"])
        self.assertEqual(sorted(p.name for p in (self.out / "docs").iterdir()), ["CONTRIBUTING.md", "northstar.md"])
        page = self.page()
        self.assertIn("<title>ParkviewLab · example</title>", page)
        self.assertIn("<h1>example</h1>", page)
        self.assertIn('<div class="group northstar">', page)
        self.assertIn('href="https://github.com/ParkviewLab/example/blob/v1.2.3/docs/northstar.md">North</a>', page)
        self.assertIn("Markdown · rendered on GitHub", page)

    def test_site_without_intro(self) -> None:
        self.md("docs/a.md")
        self.write("site/assets/logo.svg", "<svg/>")
        log = self.build()
        self.assertIn("copied site/\n", log)
        self.assertIn("no introduction", log)
        self.assertTrue((self.out / "assets" / "logo.svg").is_file())

    def test_intro_is_inserted_without_its_leading_comments(self) -> None:
        self.md("docs/a.md")
        # REUSE-IgnoreStart: the tags below are fixture text, not this file's licensing
        self.write(
            "site/intro.html",
            "<!--\nSPDX-FileCopyrightText: 2026 someone\nSPDX-License-Identifier: CC-BY-4.0\n-->\n"
            "<!-- an explanatory comment -->\n<p>First.</p>\n<p>Second.</p>\n\n",
        )
        # REUSE-IgnoreEnd
        self.build()
        page = self.page()
        self.assertIn("      <p>First.</p>\n      <p>Second.</p>\n", page)
        self.assertNotIn("SPDX", page)
        self.assertNotIn("explanatory", page)
        self.assertFalse((self.out / "intro.html").exists())

    def test_empty_intro_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/intro.html", "<!-- only a comment -->\n")
        self.assertIn("holds no introduction", self.build_fails())

    def test_groups_in_order_with_titles_sorted_and_escaped(self) -> None:
        self.md("docs/northstar.md", "North")
        self.html("docs/z.html", "Zed study")
        self.md("docs/b.md", "beta & co")
        self.md("docs/a.md", "Alpha")
        self.md("docs/in-flight_ideas.md", "Ideas")
        self.md("docs/CONTRIBUTING.md", "Contributing")
        self.build()
        page = self.page()
        order = re.findall(r'<div class="group (\w+)">', page)
        self.assertEqual(order, ["northstar", "html", "specs", "ideas", "contributing"])
        self.assertLess(page.index(">Alpha<"), page.index(">beta &amp; co<"))
        self.assertIn('<a class="doc-title" href="docs/z.html">Zed study</a>', page)

    def test_twin_listed_once_with_a_markdown_source_link(self) -> None:
        self.html("docs/plan.html", "The plan", "Designed twin")
        self.md("docs/plan.md", "The plan, in Markdown")
        self.build()
        page = self.page()
        self.assertEqual(page.count('<li class="doc">'), 1)
        self.assertIn('<a class="doc-title" href="docs/plan.html">The plan</a>', page)
        self.assertIn('<p class="doc-desc">Designed twin</p>', page)
        self.assertIn(
            '<a href="https://github.com/ParkviewLab/example/blob/v1.2.3/docs/plan.md">Markdown source</a>', page
        )
        self.assertNotIn("in Markdown", page)

    def test_footer_and_tag_are_pinned(self) -> None:
        self.md("docs/a.md")
        self.build(tag="v2.0.0")
        page = self.page()
        self.assertIn('<a href="https://github.com/ParkviewLab/example/tree/v2.0.0">v2.0.0</a>', page)
        self.assertIn('<a href="https://github.com/ParkviewLab/example">ParkviewLab/example on GitHub</a>', page)
        self.assertNotIn("v1.2.3", page)

    def test_docs_are_copied_byte_identical(self) -> None:
        html = self.html("docs/a.html", "A", body="<p>é &amp; \r\n</p>")
        self.write("docs/.DS_Store", "junk")
        self.build()
        self.assertEqual((self.out / "docs" / "a.html").read_bytes(), html.read_bytes())
        self.assertFalse((self.out / "docs" / ".DS_Store").exists())


class FolderIndexTests(Fixture):
    def test_folder_index_generated_with_root_prefix(self) -> None:
        self.md("docs/top.md", "Top")
        self.md("docs/guide/one.md", "One")
        self.html("docs/guide/two.html", "Two")
        log = self.build()
        self.assertIn("wrote docs/guide/index.html: 2 documents", log)
        root = self.page()
        self.assertIn('<div class="group folders">', root)
        self.assertIn('<a class="doc-title" href="docs/guide/">guide/</a>', root)
        page = self.page("docs/guide/index.html")
        self.assertIn("<title>ParkviewLab · example · docs/guide</title>", page)
        self.assertIn("<h1>example · docs/guide</h1>", page)
        self.assertIn('<a href="../../">', page)
        self.assertIn('<a class="doc-title" href="two.html">Two</a>', page)
        self.assertIn('href="https://github.com/ParkviewLab/example/blob/v1.2.3/docs/guide/one.md">One</a>', page)
        self.assertNotIn(">Top<", page)

    def test_nested_folders(self) -> None:
        self.md("docs/a/b/deep.md", "Deep")
        self.build()
        self.assertTrue((self.out / "docs" / "a" / "index.html").is_file())
        a = self.page("docs/a/index.html")
        self.assertIn('<a class="doc-title" href="b/">b/</a>', a)
        self.assertNotIn('<div class="group specs">', a)
        b = self.page("docs/a/b/index.html")
        self.assertIn('<a href="../../../">', b)
        self.assertIn("<h1>example · docs/a/b</h1>", b)

    def test_shipped_index_is_kept(self) -> None:
        own = self.html("docs/guide/index.html", "Own index", body="<p>mine</p>")
        self.md("docs/guide/one.md", "One")
        log = self.build()
        self.assertIn("docs/guide/index.html ships in the repository; not generated", log)
        self.assertEqual((self.out / "docs" / "guide" / "index.html").read_bytes(), own.read_bytes())

    def test_folder_without_documents_gets_no_index(self) -> None:
        self.md("docs/a.md")
        self.write("docs/assets/logo.svg", "<svg/>")
        self.build()
        self.assertFalse((self.out / "docs" / "assets" / "index.html").exists())
        self.assertNotIn("Folders", self.page())


class StampTests(Fixture):
    def test_every_html_under_site_is_stamped(self) -> None:
        self.md("docs/a.md")
        self.write("site/downloads/index.html", "<html><body>Version __LATEST_TAG__ and again __LATEST_TAG__</body></html>\n")
        self.write("site/about/index.html", "<html><body>Since __LATEST_TAG__</body></html>\n")
        self.write("site/notes.txt", "__LATEST_TAG__ stays in a text file\n")
        log = self.build()
        self.assertIn("stamped v1.2.3 into 2 hand-built pages: about/index.html, downloads/index.html", log)
        self.assertEqual(self.page("downloads/index.html"), "<html><body>Version v1.2.3 and again v1.2.3</body></html>\n")
        self.assertEqual(self.page("about/index.html"), "<html><body>Since v1.2.3</body></html>\n")
        self.assertIn("__LATEST_TAG__", self.page("notes.txt"))

    def test_a_partial_token_is_not_a_placeholder(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", "<html><script>if(e.textContent.indexOf('__LATEST')===0){}</script>__proto__</html>\n")
        self.build()
        self.assertIn("indexOf('__LATEST')", self.page("dl/index.html"))

    def test_surviving_placeholder_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", "<html>\n<body>__LATEST_TAG__\nand __NEXT_TAG__</body></html>\n")
        err = self.build_fails()
        self.assertIn("survived the stamp", err)
        self.assertIn("dl/index.html:3: __NEXT_TAG__", err)

    def test_stamp_keeps_line_endings(self) -> None:
        self.md("docs/a.md")
        page = self.repo / "site" / "dl" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_bytes(b"<html>\r\n__LATEST_TAG__\r\n</html>\r\n")
        self.build()
        self.assertEqual((self.out / "dl" / "index.html").read_bytes(), b"<html>\r\nv1.2.3\r\n</html>\r\n")


class LinkCheckTests(Fixture):
    def test_generated_pages_resolve(self) -> None:
        self.md("docs/a.md")
        self.html("docs/b.html", "B")
        self.write("site/assets/icon.svg", "<svg/>")
        self.write(
            "site/dl/index.html",
            '<html><head><style>body{background:url("../assets/icon.svg")}</style></head>'
            '<body><a href="../">home</a><img src="../assets/icon.svg"><a href="../docs/b.html">b</a>'
            '<a href="#top">top</a><a href="https://example.org/">out</a><a href="//cdn/x">pr</a></body></html>\n',
        )
        log = self.build()
        self.assertIn("link check: 5 local references in 2 generated or stamped pages, all resolve", log)

    def test_unresolved_reference_in_a_stamped_page_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", '<html><body>\n<img src="../assets/missing.png">\n</body></html>\n')
        err = self.build_fails()
        self.assertIn("unresolved references", err)
        self.assertIn("dl/index.html:2: '../assets/missing.png': no such file", err)

    def test_css_url_in_a_stamped_page_is_checked(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", "<html><head><style>\n\nh1{background:url(bg.png)}\n</style></head></html>\n")
        err = self.build_fails()
        self.assertIn("dl/index.html:3: 'bg.png': no such file", err)

    def test_root_relative_reference_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", '<html><body><a href="/docs/a.md">a</a></body></html>\n')
        err = self.build_fails()
        self.assertIn("root-relative; the site lives under /example/", err)

    def test_reference_outside_the_site_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", '<html><body><a href="../../repo/docs/a.md">a</a></body></html>\n')
        self.assertIn("resolves outside the site", self.build_fails())

    def test_folder_link_needs_an_index(self) -> None:
        self.md("docs/a.md")
        self.write("site/assets/x.txt", "x")
        self.write("site/dl/index.html", '<html><body><a href="../assets/">assets</a></body></html>\n')
        self.assertIn("no index.html in that folder", self.build_fails())

    def test_copied_html_document_is_only_reported(self) -> None:
        self.html("docs/a.html", "A", body='<a href="missing.html">gone</a><img src="../nope.png">')
        self.md("docs/b.md", "B")
        log = self.build()
        self.assertIn("warning: docs/a.html:8: 'missing.html': no such file", log)
        self.assertIn("warning: docs/a.html:8: '../nope.png': no such file", log)
        self.assertIn("docs/ link check: 1 copied HTML document, 2 unresolved, published as they are", log)
        self.assertTrue((self.out / "docs" / "a.html").is_file())

    def test_copied_markdown_is_not_checked(self) -> None:
        self.md("docs/a.md", "A", "[gone](missing.md) ![img](nope.png)")
        log = self.build()
        self.assertNotIn("warning", log)
        self.assertNotIn("docs/ link check", log)


class OutRefusalTests(Fixture):
    def setUp(self) -> None:
        super().setUp()
        self.md("docs/a.md")
        (self.repo / "site").mkdir()

    def test_non_empty_out(self) -> None:
        self.out.mkdir()
        (self.out / "stale.html").write_text("old", encoding="utf-8")
        self.assertIn("is not empty", self.build_fails())
        self.assertEqual((self.out / "stale.html").read_text(encoding="utf-8"), "old")

    def test_out_inside_docs(self) -> None:
        self.assertIn("must not be inside docs/", self.build_fails(out=self.repo / "docs" / "_site"))
        self.assertFalse((self.repo / "docs" / "_site").exists())

    def test_out_is_site(self) -> None:
        self.assertIn("must not be inside site/", self.build_fails(out=self.repo / "site"))

    def test_out_inside_site(self) -> None:
        self.assertIn("must not be inside site/", self.build_fails(out=self.repo / "site" / "build"))

    def test_out_is_a_file(self) -> None:
        self.out.write_text("a file", encoding="utf-8")
        self.assertIn("is not a directory", self.build_fails())

    def test_empty_out_is_fine(self) -> None:
        self.out.mkdir()
        self.build()

    def test_out_elsewhere_in_the_repository_is_fine(self) -> None:
        self.build(out=self.repo / "_site")
        self.assertTrue((self.repo / "_site" / "index.html").is_file())


class SiteLayoutGuardTests(Fixture):
    def test_missing_docs_fails(self) -> None:
        self.assertIn("no docs/ directory", self.build_fails())

    def test_site_index_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/index.html", "<html></html>")
        self.assertIn("site/index.html would be overwritten", self.build_fails())

    def test_site_docs_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/docs/x.html", "<html></html>")
        self.assertIn("site/docs/ would collide", self.build_fails())


class CliTests(Fixture):
    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=cwd or self.tmp, capture_output=True, text=True, check=False
        )

    def test_out_is_required(self) -> None:
        result = self.run_cli("--tag", "v1.2.3")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--out", result.stderr)

    def test_repo_defaults_to_the_current_directory(self) -> None:
        self.md("docs/a.md", "Alpha")
        result = self.run_cli("--out", str(self.out), "--tag", "v1.2.3", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("build-pages-site: ParkviewLab/example, release tag v1.2.3", result.stdout)
        self.assertIn(">Alpha<", self.page())

    def test_build_error_exits_1(self) -> None:
        result = self.run_cli("--out", str(self.out), "--tag", "v1.2.3", "--repo", str(self.repo))
        self.assertEqual(result.returncode, 1)
        self.assertIn("build-pages-site: error: no docs/ directory", result.stderr)

    def test_script_is_executable_with_a_python3_shebang(self) -> None:
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        with SCRIPT.open("rb") as f:
            self.assertEqual(f.readline(), b"#!/usr/bin/env python3\n")


# --------------------------------------------------------------------------- #
# The correctness review
# --------------------------------------------------------------------------- #


class SymlinkGuardTests(Fixture):
    """docs/ or site/ as a symlink still guards --out (else copytree recurses into itself)."""

    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "real-docs").mkdir()
        (self.tmp / "real-site").mkdir()
        os.symlink(self.tmp / "real-docs", self.repo / "docs")
        os.symlink(self.tmp / "real-site", self.repo / "site")
        self.md("docs/a.md", "Alpha")

    def test_out_inside_symlinked_docs_is_refused(self) -> None:
        self.assertIn("must not be inside docs/", self.build_fails(out=self.repo / "docs" / "_site"))
        self.assertEqual(sorted(p.name for p in (self.tmp / "real-docs").iterdir()), ["a.md"])

    def test_out_inside_symlinked_site_is_refused(self) -> None:
        self.assertIn("must not be inside site/", self.build_fails(out=self.repo / "site" / "_site"))
        self.assertEqual(list((self.tmp / "real-site").iterdir()), [])

    def test_symlinked_docs_and_site_still_build_elsewhere(self) -> None:
        self.build()
        self.assertTrue((self.out / "docs" / "a.md").is_file())


class ExactPlaceholderTests(Fixture):
    """A placeholder is written exactly; other braces fail rather than being published."""

    def test_loose_shapes_are_rejected(self) -> None:
        self.md("docs/a.md")
        for token in ("{{ title }}", "{{Title}}", "{{TITLE}}", "{{title-x}}", "{{ groups}}"):
            shell = self.write("shell.html", f"<html>{{{{groups}}}}{token}</html>\n")
            err = self.build_fails("--shell", str(shell))
            self.assertIn(f"unknown placeholder {token}", err, token)
            self.assertIn("written exactly so", err)

    def test_a_loose_groups_does_not_count_as_groups(self) -> None:
        self.md("docs/a.md")
        shell = self.write("shell.html", "<html>{{ groups }}</html>\n")
        self.assertIn("unknown placeholder {{ groups }}", self.build_fails("--shell", str(shell)))


class TagTokenTests(Fixture):
    """__LATEST_TAG__ in a shell or in the intro is stamped, and a misspelling of it fails."""

    def test_token_in_shell_and_intro_is_stamped(self) -> None:
        self.md("docs/a.md")
        self.write("site/intro.html", "<p>Current release: __LATEST_TAG__.</p>\n")
        shell = self.write("shell.html", "<html><title>__LATEST_TAG__</title>\n{{intro}}\n{{groups}}</html>\n")
        self.build("--shell", str(shell))
        page = self.page()
        self.assertIn("<title>v1.2.3</title>", page)
        self.assertIn("<p>Current release: v1.2.3.</p>", page)
        self.assertNotIn("__LATEST_TAG__", page)

    def test_misspelt_token_in_intro_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/intro.html", "<p>Release __LATEST_TAG_ here.</p>\n")
        err = self.build_fails()
        self.assertIn("survived the stamp", err)
        self.assertRegex(err, r"index\.html:\d+: __LATEST_TAG_")

    def test_misspelt_token_in_shell_fails(self) -> None:
        self.md("docs/guide/a.md")
        shell = self.write("shell.html", "<html>\n<p>__NEXT_TAG__</p>\n{{groups}}</html>\n")
        self.assertIn("index.html:2: __NEXT_TAG__", self.build_fails("--shell", str(shell)))


class SurvivorShapeTests(Fixture):
    """The survivor rule catches misspellings of the tag token and nothing else."""

    def test_shapes(self) -> None:
        caught = ("__LATEST_TAG_", "_LATEST_TAG__", "__NEXT_TAG__", "__LATSET_TAG__", "__LATEST__", "__TAG__", "__LATEST_TGA__")
        passed = ("__FILE__", "__VERSION__", "__STAGE__", "__DEV__", "__proto__", "'__LATEST'", "MY_LATEST_TAG_VALUE", "__latest_tag__")
        for token in caught:
            self.assertIsNotNone(bps.SURVIVOR_RE.search(f"x {token} y"), token)
        for token in passed:
            self.assertIsNone(bps.SURVIVOR_RE.search(f"x {token} y"), token)

    def test_quoted_dunders_build(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", "<html><body><code>__FILE__</code> __VERSION__ __STAGE__ __LATEST_TAG__</body></html>\n")
        self.build()
        self.assertIn("<code>__FILE__</code> __VERSION__ __STAGE__ v1.2.3", self.page("dl/index.html"))

    def test_misspelt_tag_token_in_a_hand_built_page_fails(self) -> None:
        self.md("docs/a.md")
        self.write("site/dl/index.html", "<html><body>__LATEST_TAG_</body></html>\n")
        self.assertIn("dl/index.html:1: __LATEST_TAG_", self.build_fails())


class BomTests(Fixture):
    """A UTF-8 byte-order mark hides neither a title nor a leading comment."""

    def test_markdown_title_behind_a_bom(self) -> None:
        path = self.repo / "docs" / "a.md"
        path.parent.mkdir()
        path.write_bytes("\ufeff# Bom title\n".encode("utf-8"))
        self.assertEqual(bps.markdown_title(path), "Bom title")

    def test_html_title_behind_a_bom(self) -> None:
        path = self.repo / "docs" / "a.html"
        path.parent.mkdir()
        path.write_bytes(("\ufeff" + HTML_DOC.format(title="Bom html", meta="", body="")).encode("utf-8"))
        self.assertEqual(bps.html_head(path), ("Bom html", None))

    def test_intro_comment_behind_a_bom_is_stripped(self) -> None:
        self.md("docs/a.md")
        intro = self.repo / "site" / "intro.html"
        intro.parent.mkdir()
        # REUSE-IgnoreStart: the tag below is fixture text, not this file's licensing
        intro.write_bytes("\ufeff<!-- SPDX-License-Identifier: CC-BY-4.0 -->\n<p>Hi</p>\n".encode("utf-8"))
        # REUSE-IgnoreEnd
        self.build()
        page = self.page()
        self.assertIn("<p>Hi</p>", page)
        self.assertNotIn("SPDX", page)
        self.assertNotIn("\ufeff", page)


class OddNameTests(Fixture):
    """A document or folder name with # or a space is percent-encoded in its link."""

    def test_hash_and_space_in_names(self) -> None:
        self.html("docs/q#1.html", "Hash")
        self.html("docs/a b.html", "Space")
        self.html("docs/guide x/c.html", "Folder space")
        self.build()
        page = self.page()
        self.assertIn('href="docs/q%231.html">Hash</a>', page)
        self.assertIn('href="docs/a%20b.html">Space</a>', page)
        self.assertIn('href="docs/guide%20x/">guide x/</a>', page)
        self.assertIn('href="c.html">Folder space</a>', self.page("docs/guide x/index.html"))


class UnreadableInputTests(Fixture):
    """A bad document or a bad copy is a build error line, not a traceback."""

    def test_non_utf8_document_fails(self) -> None:
        self.md("docs/ok.md")
        (self.repo / "docs" / "bad.md").write_bytes(b"# T\xff\xfe\n")
        self.assertIn("docs/bad.md is not UTF-8", self.build_fails())

    def test_dangling_symlink_in_docs_fails(self) -> None:
        self.md("docs/ok.md")
        os.symlink(self.repo / "docs" / "missing.md", self.repo / "docs" / "dangling.md")
        err = self.build_fails()
        self.assertIn("cannot copy docs/", err)
        self.assertIn("dangling.md", err)


class ShellLocationTests(Fixture):
    """A shell under docs/ would be published as a document, so it is refused."""

    def test_shell_under_docs_is_refused(self) -> None:
        self.md("docs/a.md")
        shell = self.write("docs/shell.html", "<html>{{groups}}</html>\n")
        self.assertIn("lives under docs/", self.build_fails("--shell", str(shell)))
        self.assertFalse(self.out.exists())


class CaseMismatchedIndexTests(Fixture):
    """docs/g/Index.html is no index to Pages and must not be overwritten by the generated one."""

    def test_case_mismatched_index_fails(self) -> None:
        self.html("docs/g/Index.html", "Own")
        self.md("docs/g/one.md", "One")
        err = self.build_fails()
        self.assertIn("docs/g/Index.html", err)
        self.assertIn("index.html exactly", err)

    def test_exact_index_is_kept(self) -> None:
        own = self.html("docs/g/index.html", "Own")
        self.md("docs/g/one.md", "One")
        self.build()
        self.assertEqual((self.out / "docs" / "g" / "index.html").read_bytes(), own.read_bytes())


class HeadScannerTests(Fixture):
    """The title is the first <title>; an inline svg's is not appended to it."""

    def test_svg_title_in_a_body_without_head_end(self) -> None:
        path = self.write("docs/a.html", "<html><head><title>Doc</title>\n<body><svg><title>Icon</title></svg></body></html>\n")
        self.assertEqual(bps.html_head(path), ("Doc", None))

    def test_svg_title_inside_the_head(self) -> None:
        path = self.write("docs/a.html", '<html><head><title>Doc</title><svg><title>Icon</title></svg><meta name="description" content="D"></head></html>\n')
        self.assertEqual(bps.html_head(path), ("Doc", "D"))

    def test_body_ends_the_scan(self) -> None:
        path = self.write("docs/a.html", '<html><head><title>Doc</title>\n<body><meta name="description" content="late"></body></html>\n')
        self.assertEqual(bps.html_head(path), ("Doc", None))


class TagShapeTests(Fixture):
    """Only vX.Y.Z tags are releases, from git and from --tag alike."""

    @unittest.skipUnless(GIT, "git is not installed")
    def test_vnext_is_skipped_for_the_release_tag(self) -> None:
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "one")
        git(self.repo, "tag", "v1.2.3")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "two")
        git(self.repo, "tag", "vnext")
        self.assertEqual(bps.release_tag(None, self.repo), "v1.2.3")

    @unittest.skipUnless(GIT, "git is not installed")
    def test_only_vnext_is_no_release(self) -> None:
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "one")
        git(self.repo, "tag", "vnext")
        with self.assertRaisesRegex(bps.BuildError, "no v\\* tag reachable"):
            bps.release_tag(None, self.repo)

    @unittest.skipUnless(GIT, "git is not installed")
    def test_v2_is_not_a_release_tag(self) -> None:
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "one")
        git(self.repo, "tag", "v2")
        with self.assertRaisesRegex(bps.BuildError, "not a vX.Y.Z release tag"):
            bps.release_tag(None, self.repo)

    def test_explicit_vnext_is_refused(self) -> None:
        with self.assertRaises(bps.BuildError):
            bps.release_tag("vnext", self.repo)


class RepoRootTests(Fixture):
    """--repo must be the root of its checkout, so a subdirectory never borrows its origin."""

    @unittest.skipUnless(GIT, "git is not installed")
    def test_subdirectory_of_a_checkout_is_refused(self) -> None:
        git(self.repo, "remote", "add", "origin", "git@github.com:ParkviewLab/outer.git")
        sub = self.repo / "sub"
        (sub / "docs").mkdir(parents=True)
        (sub / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
        with self.assertRaisesRegex(bps.BuildError, "is not its root"):
            bps.repository(str(sub))
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bps.main(["--out", str(self.out), "--tag", "v1.2.3", "--repo", str(sub)])
        self.assertEqual(code, 1)
        self.assertIn("is not its root", stderr.getvalue())
        self.assertFalse(self.out.exists())


class EmptyDocsTests(Fixture):
    """An empty docs/ builds, and the log says so."""

    def test_empty_docs_warns(self) -> None:
        (self.repo / "docs").mkdir()
        log = self.build()
        self.assertIn("wrote index.html: 0 documents", log)
        self.assertIn("warning: docs/ holds no documents; the index lists nothing", log)


if __name__ == "__main__":
    unittest.main()
