# ParkviewLab dev-tools

Shared developer tooling for repos under [`ParkviewLab/`](https://github.com/ParkviewLab) — small scripts that don't justify their own repo but want to live in one canonical place.

## Install

Clone once, run `install.sh`. The installer symlinks every **executable** script in `scripts/` into `~/.local/bin/`, so each is on `$PATH` under its file name: `git-<verb>` for the version helpers, `build-pages-site` for the site builder, `generate-changelog` for the changelog generator (a dry run or a repair runs it from a dev-tools worktree at the pinned release instead; see its section).

```bash
git clone git@github.com:ParkviewLab/dev-tools.git ~/dev-tools
cd ~/dev-tools
./install.sh
```

Updates: `git pull`. Because the installer **symlinks** (not copies), a changed script is picked up on the next `git pull` with no re-run; a **brand-new** command needs one more `install.sh` run to add its symlink.

### Requirements

- `~/.local/bin` on `$PATH` (default on most modern macOS / Linux setups).
- Bash 3.2 or later for the version helpers (`#!/usr/bin/env bash`).
- `python3` (3.13) for `build-pages-site`, which uses the standard library only.
- `uv` for `generate-changelog`, which runs under `uv run --script`: uv provides Python 3.13, downloading it where the machine has none, and installs the `anthropic` SDK at the exact version the script declares, with that SDK's dependencies as PyPI held them at the script's `exclude-newer` date, for its Highlights call. The script also needs git 2.38 or later, for `git merge-tree --write-tree`.
- Per the repo's version source of truth: `uv` for `pyproject.toml`, `node`/`npm` for `package.json`, nothing extra for `VERSION.txt`.
- `gh` (GitHub CLI) for `git dev-release`, and for `generate-changelog`, which reads the repository's merged pull requests through it.

## The version helpers

`git release`, `git bump`, and `git dev-release` are **source-of-truth aware** — each auto-detects and operates on whichever the repo uses:

| Source of truth | read / written via |
|---|---|
| `pyproject.toml` `[project].version` | `uv` |
| `package.json` `version` | `npm` |
| top-level `VERSION.txt` | the file directly |

Shared detection + version math lives in `scripts/_sot.sh` (sourced by each; not executable, so it isn't symlinked as a command).

### `git release` — tag a release

Reads the version from the source of truth and makes an annotated tag `v<version>` on `HEAD`. Refuses on a dirty tree or an existing tag. Does **not** push.

```bash
git release
# tagged v0.1.6 (HEAD: abc1234)
# push with: git push --follow-tags
```

### `git bump` — bump the version + commit

Bumps the version in the source of truth, `git add`s it (+ lockfile if touched), commits `release v<new>`. Does **not** tag — that's `git release`.

```bash
git bump patch     # 0.1.5 -> 0.1.6
git bump minor     # 0.1.6 -> 0.2.0
git bump major     # 0.2.0 -> 1.0.0
git bump release   # finalize a dev cycle (drop the .devN) — see below
git bump 0.1.7     # explicit version
```

**Finalizing a dev cycle.** When `develop` carries a dev version (the open-cycle placeholder — e.g. `0.1.6.dev0`, opened after `v0.1.5`; see `git dev-release`), `git bump` drops the `.devN` and finalizes. A `<kind>` re-points off the **last release tag**:

```bash
# develop sits at 0.1.6.dev0 (opened after v0.1.5); choose at release time:
git bump patch     # -> 0.1.6   (ship the placeholder target)
git bump minor     # -> 0.2.0   (it was actually a feature release)
git bump major     # -> 1.0.0
git bump release   # -> 0.1.6   (ship exactly what the cycle declared)
```

From a plain (non-dev) version, `<kind>` is just the normal increment.

### `git dev-release` — on-demand dev build

Run from `develop`. Bumps the source of truth to the next **dev** version, commits, pushes `develop`, and dispatches the repo's `dev-release.yml`, which builds the dev counterpart of each of the repo's publish targets that has one (the handbook's [`releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md#development-versioning)); in a repo without that workflow the bump and the push still happen, and the dispatch fails. For real releases use `git bump` / `git release`.

```bash
git dev-release patch       # next dev build toward the next patch
git dev-release minor       # re-points the cycle to the next minor (major likewise)
git dev-release --open      # open the next cycle post-release: X.Y.(Z+1).dev0 (X.Y.(Z+1)-dev0 for package.json; no publish)
git dev-release --dry-run patch
```

- **A dev version names the *next* release** plus a pre-release marker: `.devN` (PEP 440) for `pyproject.toml`, as in `0.1.5 < 0.1.6.dev0 < 0.1.6`, and `-devN` (semver, which npm and electron-builder require) for `package.json`. Builds toward the same target tick the counter (`dev0`, `dev1`, …) so each published artifact is distinct (TestPyPI rejects duplicates).
- **`--open`** is run right after a release (part of the back-merge cascade) to set `develop`'s honest version to the next-patch placeholder.
- `VERSION.txt` repos get a plain `-dev` marker and publish nothing — the dev *build* path is code-repo-only.

The full convention — when to open a cycle, how it interacts with `version-guard` and the release gate — is the **[handbook's `releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md) ("Development versioning")** + `ci.md` (`dev-release.yml`). dev-tools is the *tooling*; the handbook is the source of truth for the *flow*.

## `build-pages-site` — build a repo's documentation site

`build-pages-site` assembles the GitHub Pages site of a repo that publishes its `docs/` (the handbook's [`docs-site.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/docs-site.md)). It is the implementation that the handbook's `pages-docs.yml` template runs: the mechanics live here, and only the page shell (the styling and the introduction) stays per-repo. The one exception is pensa-grex, whose builder it generalises and which still runs its own `scripts/build_pages_site.py`.

It reads `docs/` and `site/` at the repo root and nothing else, and writes into `--out`:

| Path | What |
|---|---|
| `index.html` | generated: the page shell around the introduction (`site/intro.html`) and a list of every document in `docs/` |
| `<page>/` | every other file under `site/`, copied as it is, with the release tag stamped into each `.html` in place of `__LATEST_TAG__` |
| `docs/` | `docs/`, byte-identical to the repo, plus a generated `index.html` in every subfolder that holds documents (a folder that ships its own `index.html` keeps it) |

`site/` is optional, as is the introduction: a repo with neither publishes its `docs/` alone. pensa-grex's download page, `site/downloads/index.html`, is ordinary `site/` content, stamped like any other `.html` under `site/`. The documents are listed in five groups, in order: the northstar (`northstar.html`, else `northstar.md`), the other HTML documents, the Markdown specifications and notes, the ideas under consideration (`in-flight_ideas.md` and `*_ideas.md`), and `CONTRIBUTING.md`; within a group, by title. A Markdown document with an `.html` twin is listed once, under the twin, with a "Markdown source" link. An HTML document's title is its `<title>`, and its description its `<meta name="description">` when present; a Markdown document's title is its first `# ` heading; a document without a title fails the build. HTML documents are linked relatively; Markdown documents open in GitHub's rendered view, pinned to the release tag.

```bash
build-pages-site --out DIR [--tag vX.Y.Z] [--shell FILE] [--repo DIR]
```

- `--out DIR` (required): the directory to assemble into, new or empty. A non-empty directory, or one inside `docs/` or `site/`, is refused.
- `--tag vX.Y.Z`: the release to pin to, for a local run; by default the newest `v*` tag reachable from `HEAD` (`git describe --tags --abbrev=0 --match 'v[0-9]*'`). Either way it must be a `vX.Y.Z` release tag; a `vnext` is refused.
- `--shell FILE`: the page shell (below); by default a built-in shell in the ParkviewLab brand. A shell under `docs/` is refused, since it would be published as a document.
- `--repo DIR`: the repo to build; by default the current directory, which is where the pages workflow runs. It must be the root of its git checkout when it is inside one, so a subdirectory never borrows the enclosing checkout's remote. A checkout of dev-tools in a subfolder of that repo is not read.

The repo's GitHub address, for the pinned links, is read from the `origin` remote, else from `GITHUB_REPOSITORY`.

### The shell

The root index and every folder index are one HTML file, the shell, with these placeholders substituted:

| Placeholder | Value |
|---|---|
| `{{title}}` | the page title: the repo name on the root page, `<repo> · docs/<folder>` on a folder index |
| `{{intro}}` | `site/intro.html` without its leading comments, on the root page; empty on a folder index, and when there is no intro |
| `{{groups}}` | the document list: the five groups and, where the folder has subfolders holding documents, a "Folders" group (the one required placeholder) |
| `{{root}}` | the relative path from the page's folder to the site root: empty on the root page, `../../` in `docs/<folder>/` |
| `{{tag}}` | the release tag |
| `{{repo}}` | the repo name |
| `{{footer}}` | two `<span>`s: the release the site is published from, linked to its tree on GitHub, and a link to the repo |

A placeholder that starts its line is indented to that line's column, every line of a multi-line value with it, so the output follows the shell's own layout. A placeholder is written exactly as listed; any other `{{name}}`, a different case or spacing included, fails the build. A shell, and `site/intro.html`, may also carry `__LATEST_TAG__`, which the build substitutes as it does in a hand-built page. The generated list is a `<div class="group <key>">` per group (`northstar`, `html`, `specs`, `ideas`, `contributing`, `folders`), each holding an `<h3>` and a `<ul class="doclist">` of `<li class="doc">` cards with a `.doc-title` link and, when there is one, a `.doc-desc` paragraph and a `.doc-meta` line; a shell styles those classes. A shell kept under `site/` (say `site/shell.html`) is not published.

The built-in shell is the `DEFAULT_SHELL` string in the script, the starting point for a custom one: the handbook's brand palette and the component vocabulary of its `templates/md-to-html/default.html` (a header bar with the logo mark, a hero, a section label, cards, a footer) on the system font stacks, with no font file, no script and no network request, collapsing to one column below 680 px. pensa-grex's page, the reference this command was generalised from, is Googie-themed (its bundled fonts, its palette with the light/dark toggle, its hero with the Downloads card and the icons, its own footer), too particular to that site to serve here as an example. The table above is the whole interface.

### What it guarantees

Standard library only, so the deploy path installs nothing. Nothing generated is committed: the site is assembled into `--out`, and the workflow uploads that directory. The build fails when a document has no title, when a placeholder survives the stamp (after `__LATEST_TAG__` is substituted in the hand-built pages, the shell and the intro, a token still shaped like it: two underscores at one end, one or more at the other, and `TAG` or `LATEST` as a part of its name, such as `__LATEST_TAG_` or `__NEXT_TAG__`; a `__FILE__` quoted in a page is not one), and when a relative `href`, `src` or CSS `url()` in a page it generated or stamped does not resolve against the assembled directory; it only reports an unresolved reference inside an HTML document copied from `docs/`, which is published as the repo holds it, and it does not check copied Markdown at all. Every GitHub link is pinned to one release tag. That tag is the newest `v*` tag reachable from `HEAD` and must be a `vX.Y.Z` release tag; it may be the previous release's when a run starts before this release's tag lands; that leniency is deliberate (a manual re-run on the changelog commit must still build), and a repo with no `v*` tag at all is refused. The contract, and the reasoning behind it, are the handbook's [`docs-site.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/docs-site.md).

### In a repo's pages workflow

The workflow checks the adopting repo out at `main` with its tags, checks dev-tools out into a subfolder at a pinned tag, and runs the script from there:

```yaml
- uses: actions/checkout@v6
  with:
    ref: main             # always publish the released state, never develop
    fetch-depth: 0        # tags: the build reads the newest release from them
- uses: actions/checkout@v6
  with:
    repository: ParkviewLab/dev-tools
    ref: vX.Y.Z           # a released tag of dev-tools, pinned
    path: dev-tools
- uses: actions/setup-python@v6
  with:
    python-version: "3.13"
- name: Build the site
  run: python3 dev-tools/scripts/build-pages-site --out "${{ runner.temp }}/site"
  # a repo with its own shell adds: --shell site/shell.html
```

Locally, `install.sh` links `build-pages-site` into `~/.local/bin` like the other scripts, so the same build runs from a repo's root (`build-pages-site --out /tmp/site --tag vX.Y.Z`); open the result with `python3 -m http.server` from that directory.

## `generate-changelog` — a release's changelog section

`generate-changelog` writes the changelog section of one release: a Highlights paragraph written by a model, and the list of what the release holds, built from the repository's history at the tag and its merged pull requests. A release workflow that runs it does so from a checkout of dev-tools pinned to a release, so that repository's notes follow the rule of the dev-tools release its workflow pins, and the rule changes only with a dev-tools release.

```bash
generate-changelog [--mode generate|insert|both] [--tag vX.Y.Z] [--repo DIR] [--reuse-committed]
```

- `--mode`: `generate` writes the section to `release-body.md` at the repository root; `insert` puts `release-body.md` into `CHANGELOG.md` below `## [Unreleased]`, creating the file when it is absent, uses no network, and does nothing, saying so, when `CHANGELOG.md` already holds a section for the tag; `both`, the default, runs the two in order.
- `--tag vX.Y.Z`: the release. On a tag push the workflow gives it through `GITHUB_REF`; `--tag` is for a local run, a dry run and the repair of a release whose changelog job failed. The script accepts any existing `vX.Y.Z` tag, an earlier release's included; as ruled, notes already published stay as published, so a section generated for an earlier release, by a dry run for instance, is not used to change that release's published notes, in `CHANGELOG.md` or in its Release. Without a tag, the script refuses in every mode and exits with status 2.
- `--repo DIR`: the repository, by default the current directory, which must be the root of its git checkout. The script never reads the checkout it lives in, so a dev-tools checkout inside the workspace is not read; the only thing it takes from there is its own version, which it prints. The repository's GitHub address is read from the `origin` remote, else from `GITHUB_REPOSITORY`.
- `--reuse-committed`: what the release workflow passes. When `CHANGELOG.md` on `origin/main` already holds the tag's section, generate writes that section to `release-body.md` unchanged, reads nothing from GitHub and makes no model call, so a re-run of a failed job creates the Release from the committed text.

The section reads `## [vX.Y.Z] - YYYY-MM-DD` (the tagged commit's date), then `### Highlights` and the paragraph, then the list. The exit status is 0 on success, the placeholder paragraph included, and when insert finds the tag's section already in `CHANGELOG.md` and writes nothing; 1 on a failure while running: git, the GitHub read, or a `release-body.md` that cannot be read, does not begin with a `## [vX.Y.Z]` heading, or holds another tag's section; 2 on bad arguments: a command line the parser rejects, no tag, a tag that is not `vX.Y.Z`, generate with a tag that does not exist, `--repo` not the root of a git checkout, and insert with no `release-body.md`.

### What it needs, and where the rule is

The rule that builds the list (the range, which commits are listed, left out or treated as bookkeeping, the titles, and the groups and their order), the Highlights input and when the placeholder takes the paragraph's place, and the report the script prints and appends to the job summary are specified in one place: the docstring at the head of [`scripts/generate-changelog`](scripts/generate-changelog).

The script reads the repository's merged pull requests from GitHub through `gh`: with `GH_TOKEN` in a workflow, whose job then needs `pull-requests: read`, and with a person's own login locally. The Highlights call reads `ANTHROPIC_API_KEY`; without it the release still ships, with a placeholder paragraph.

### In a repo's release workflow

The changelog job checks the repository out with its whole history, checks dev-tools out into a subfolder at the commit of a pinned release, then runs the script twice: generate at the tag, and insert on a fresh `origin/main`.

```yaml
permissions:
  contents: write         # commits CHANGELOG.md to main and creates the Release
  pull-requests: read     # the merged pull requests the list is built from
steps:
  - uses: actions/checkout@v6
    with:
      fetch-depth: 0      # every branch and tag: the rule searches them all
  - uses: actions/checkout@v6
    with:
      repository: ParkviewLab/dev-tools
      ref: <the release's full commit SHA>   # vX.Y.Z
      path: dev-tools
  - uses: astral-sh/setup-uv@v8.1.0
  - name: Generate release-body.md
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    run: uv run --script dev-tools/scripts/generate-changelog --mode=generate --reuse-committed
  # then, on a fresh origin/main with release-body.md carried over:
  #   uv run --script dev-tools/scripts/generate-changelog --mode=insert
```

The pin is the release's full commit SHA (`git rev-parse vX.Y.Z^{commit}`) with the tag in a comment on the same line, and it names a release whose own release run passed. The policy is the handbook's, in [`ci.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/ci.md), "Shared dev scripts": a pin must be at or after its floor, the newest such release that changed the pinned script, and it moves during the repo's next piece of work, before its next release. The reasoning behind the shared script and its pin is recorded in the handbook's [`commits-and-changelogs-why.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/commits-and-changelogs-why.md). A local run, such as a dry run or a repair, uses a dev-tools worktree at the pinned commit, not the clone that `install.sh` links: that clone runs the script of whatever branch it has checked out, and so may apply a different rule from the pinned release's; the linked command serves only to try the script.

### Tests

`tests/test_generate_changelog.py` builds each case of the rule in a temporary repository, making the commits GitHub would make under GitHub's committer identity; it supplies the pull requests as recorded JSON and stubs the model, so it runs offline in the test workflow. These constructed-history unit tests are the release gate for the rule: a dev-tools release that changes the script is made once they pass in CI and the `profiles` mode of `tests/acceptance/acceptance.py` passes over the real-history check's representatives (below).

`tests/acceptance/` also holds the `full` mode, which runs the script against the ten repositories the rule was measured on, comparing every release's list with the recorded result, with the list a ruling now gives where one changed it (cogrind-workshop v0.1.0), or, for a release made after the measurement, with the expected set computed from GitHub's record. Its run of 2026-09-18 is the dated record of how the rule was validated (its result is in [`tests/acceptance/README.md`](tests/acceptance/README.md)); the mode is not a precondition of a release; it is run by hand, from the commit being released, when there is reason to (for instance, before a change wide enough that the representatives alone do not give confidence). The practice that replaces it as a precondition: when a real release anywhere produces a wrong list, the shape of history that caused it becomes a new constructed unit test in `tests/test_generate_changelog.py`, so the release gate keeps growing to cover what the corpus once stood in for.

The real-history check (`tests/acceptance/acceptance.py profiles`) runs the script's dry run on the latest release of one representative repository per publishing profile (`tests/acceptance/representatives.json`), and compares its list with the tag's published Release once that Release was made by the shared generator, else with the recorded, ruled or expected result — the same comparison `full` makes, but over one repository per profile instead of a ten-repository census. [`tests/acceptance/README.md`](tests/acceptance/README.md) defines a ruled change, records the rulings, describes the representatives and says how to run every mode.

## Release flow (in brief)

Releases are tag-driven and cut from `main`; CI gates publish on the tag being reachable from `origin/main`. The full flow + rationale (why bump+tag on `main`, the back-merge cascade, the CI gate) lives in the **[handbook's `releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md)**. The one-liner:

```bash
# on the <repo>-main worktree, after promoting develop -> main:
git bump <patch|minor|major|release>
git release
git push --follow-tags        # CI publishes
# then back-merge main -> develop
```

dev-tools is itself a `VERSION.txt` repo and is **released with these very tools** — `VERSION.txt` is the source of truth, bumped by `git bump` and tagged by `git release`. It ships no package, so a release promotes `develop → main` and tags, and the tag's push runs `.github/workflows/release.yml`, the handbook's documents assembly (`head.yml` + `gate.yml` + `documents.yml`) byte for byte: the three-check gate (the tag equals `VERSION.txt`, the tagged commit is on `main`, the version is greater than the previous tag's), then a GitHub Release with GitHub's generated notes. The gate runs once the tag exists, so it reports a bad tag but cannot prevent it. A ruleset on dev-tools refuses the move or deletion of any `v*` tag and names no bypass actor, so the gate's advice to re-tag from `main` cannot be followed here: a tag whose release run fails stays, no pin moves to it, and the next patch release supersedes it.

## Adding a tool

1. Drop the script (executable, with its shebang: `#!/usr/bin/env bash`; `#!/usr/bin/env python3` for a standard-library Python script; or `#!/usr/bin/env -S uv run --script` for a Python script that declares a dependency at an exact version in its PEP 723 metadata, with `[tool.uv] exclude-newer` fixing that dependency's own dependencies, and imports it only where it is used, so that its tests need the standard library alone) into `scripts/`. Non-executable files (like `_sot.sh`) are *sourced*, not symlinked.
2. Document it here.
3. PR onto `develop`. The bar: generic + cross-project, no project-specific logic. If it's only useful in one repo, it lives in that repo's `scripts/`.

## License

AGPL-3.0-or-later for the tooling and its tests (`scripts/**`, `tests/**`, `install.sh`, CI); CC-BY-4.0 for the docs, the Markdown under `tests/` included, and the repo meta. See [`LICENSING.md`](LICENSING.md).

---
<sub>© 2026 Gary Frattarola · Licensed under [CC-BY-4.0](LICENSES/CC-BY-4.0.txt) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
