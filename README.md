# ParkviewLab dev-tools

Shared developer tooling for repos under [`ParkviewLab/`](https://github.com/ParkviewLab) — small scripts that don't justify their own repo but want to live in one canonical place.

## Install

Clone once, run `install.sh`. The installer symlinks every **executable** script in `scripts/` into `~/.local/bin/`, so each is on `$PATH` under its file name: `git-<verb>` for the version helpers, `git back-merge` among them, `back-merge-check` for the check that `git back-merge` and the version guard run, `build-pages-site` for the site builder, `assemble-workflows` for a repo's release workflows, `generate-changelog` for the changelog generator (a dry run or a repair runs it from a dev-tools worktree at the pinned release instead; see its section).

```bash
git clone git@github.com:ParkviewLab/dev-tools.git ~/dev-tools
cd ~/dev-tools
./install.sh
```

Updates: `git pull`. Because the installer **symlinks** (not copies), a changed script is picked up on the next `git pull` with no re-run; a **brand-new** command needs one more `install.sh` run to add its symlink.

### Requirements

- `~/.local/bin` on `$PATH` (default on most modern macOS / Linux setups).
- Bash 3.2 or later for the version helpers and `back-merge-check` (`#!/usr/bin/env bash`).
- `python3` (3.13) for `build-pages-site`, which uses the standard library only.
- `python3` 3.11 or later for `assemble-workflows`, for `tomllib`.
- `uv` for `generate-changelog`, which runs under `uv run --script`: uv provides Python 3.13, downloading it where the machine has none, and installs the `anthropic` SDK at the exact version the script declares, with that SDK's dependencies as PyPI held them at the script's `exclude-newer` date, for its Highlights call. The script also needs git 2.38 or later, for `git merge-tree --write-tree`.
- Per the repo's version source of truth: `uv` for `pyproject.toml`, `node`/`npm` for `package.json`, nothing extra for `VERSION.txt`. `git back-merge` and `back-merge-check` parse the version file at a commit: `pyproject.toml` with `python3` where it is 3.11 or later, for `tomllib`, and otherwise with the Python 3.11 or later that `uv` provides; `package.json` with `python3`, and otherwise with `node`.
- `gh` (GitHub CLI) for `git dev-release` and `git back-merge`, and for `generate-changelog`, which reads the repository's merged pull requests through it.
- git 2.40 or later for `back-merge-check` and `git back-merge`, which use `git merge-tree --write-tree`, and its `--merge-base` for a release picked onto `main`.

## The version helpers

`git release`, `git bump`, `git dev-release` and `git back-merge` are **source-of-truth aware** — each auto-detects and operates on whichever the repo uses:

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

**Finalizing a dev cycle.** When `develop` carries a dev version (the open-cycle placeholder — e.g. `0.1.6.dev0`, opened after `v0.1.5`; see `git back-merge`, or `git dev-release --open` before a repo's switch), `git bump` drops the `.devN` and finalizes. A `<kind>` re-points off the **last release tag**:

```bash
# develop sits at 0.1.6.dev0 (opened after v0.1.5); choose at release time:
git bump patch     # -> 0.1.6   (ship the placeholder target)
git bump minor     # -> 0.2.0   (it was actually a feature release)
git bump major     # -> 1.0.0
git bump release   # -> 0.1.6   (ship exactly what the cycle declared)
```

From a plain (non-dev) version, `<kind>` is just the normal increment.

### `git dev-release` — on-demand dev build

A dev build is a candidate for local testing: the dev counterpart of each of the repo's publish targets that has one (the handbook's [`releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md#development-versioning)). `git dev-release` follows the repo's `dev-release.yml` as it stands on `origin/develop`:

- Where the workflow declares the `kind` input, the build takes its version in the CI workspace, computed from the newest release tag, the kind and the run number, and nothing is committed: the command dispatches the workflow on `develop` with that input.
- Where it does not, in a repo that does not yet allow merge commits, the command bumps the source of truth to the next **dev** version of the chosen target, commits, pushes `develop` and dispatches the workflow; run it from `develop`. There, in a repo without that workflow, the bump and the push still happen, and the dispatch fails. A repo that allows merge commits refuses (below).

For real releases use `git bump` / `git release`, and `git back-merge` after them.

```bash
git dev-release patch       # a dev build toward the next patch
git dev-release minor       # ...toward the next minor (major likewise)
git dev-release --open      # before the switch only: open the next cycle, X.Y.(Z+1).dev0 (X.Y.(Z+1)-dev0 for package.json); no publish
git dev-release --open --direct   # after the switch, only after the exception's direct back-merge: the same, by a direct push
git dev-release --dry-run patch
```

- **A dev version names the *next* release** plus a pre-release marker: `.devN` (PEP 440) for `pyproject.toml`, as in `0.1.5 < 0.1.6.dev0 < 0.1.6`, and `-devN` (semver, which npm and electron-builder require) for `package.json`. Builds toward the same target take distinct numbers (`dev0`, `dev1`, …), so each published artifact is distinct (TestPyPI rejects duplicates).
- **Before a repo's switch to merge commits**, `--open` is run right after a release, with the direct back-merge, to set `develop`'s honest version to the next-patch placeholder. Once the repo allows merge commits, `develop` takes no direct push: the open cycle arrives as the second commit of the back-merge pull request (`git back-merge`, below), so `--open` refuses there, and so does a dev build whose workflow lacks the `kind` input. The one exception is the direct back-merge (the handbook's [`releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md#the-releases-last-step-the-back-merge-pull-request), "The release's last step: the back-merge pull request"), made where `git back-merge` refuses, with administrators unbound for its one push (its procedure is under `git back-merge`, below): after its merge, made and resolved by hand in the `develop` worktree, `git dev-release --open --direct` writes the next-patch placeholder after the release `develop` then carries (`X.Y.(Z+1)` becomes `X.Y.(Z+2).dev0`, or `X.Y.(Z+2)-dev0` for `package.json`), commits it as the open-cycle commit, and pushes `develop`, so that one push carries the merge commit and that commit. It refuses unless `develop` then carries the version of `main`'s newest release (the highest `vX.Y.Z` tag on `origin/main`, fetched with the tags) and holds that release's commit, the state the exception's merge leaves once its version lines are resolved to `main`'s: a `develop` at any other version, its placeholder among them, has not had that merge, and the refusal names the version found and the one expected; nor has a `develop` at that version without the commit, whose version was set by hand, and the refusal says the exception's merge is missing. Where GitHub refuses the push because `develop`'s protection binds administrators, it says to switch `enforce_admins` off for the one push, push `develop` and switch it on again. `--direct` is allowed only with `--open`, and in a repo that has not switched it changes nothing. Where `gh` cannot read that setting, which GitHub returns only to a caller with admin rights on the repo, the command stops rather than take the repo for one that has not switched.
- **A `VERSION.txt` repo** has no dev build and skips the open cycle, as the handbook's `releases.md` says, so the command refuses there.

The full convention — when to open a cycle, how it interacts with `version-guard` and the release gate — is the **[handbook's `releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md) ("Development versioning")** + `ci.md` (`dev-release.yml`). dev-tools is the *tooling*; the handbook is the source of truth for the *flow*.

### `git back-merge` — the release back into develop, by pull request

In a repo that merges pull requests with merge commits, a release ends with `git back-merge` rather than a direct push to `develop`: the release on `main` comes back into `develop` through a pull request that `develop`'s required checks examine, among them, in a repo that has switched, the version guard in its back-merge mode (below). Run it from any worktree of the repo, under the release ask, which covers the command's merge of its own pull request and its force push of its own branch, and nothing else.

```bash
git back-merge             # the newest release tag
git back-merge v1.2.3      # a named release tag, which must be main's version
git back-merge --dry-run   # build and check locally; push, open, merge and pull nothing
```

It waits first for the release's workflow runs to conclude, then requires the changelog commit, where the release writes one, on `main`; a release whose changelog job failed is accepted once the repair is in place, that commit on `main` and a GitHub Release for the tag. In a temporary worktree it then builds `back-merge-<tag>` from `origin/develop` with `git merge --no-ff origin/main`, and in a repo whose version is in `pyproject.toml` or `package.json` adds the open-cycle commit, `chore: open <placeholder> dev cycle`, the placeholder being `X.Y.(Z+1).dev0`, or `X.Y.(Z+1)-dev0` for `package.json`, written by `_sot.sh`.

A release picked onto `main` goes back the same way. Such a release is a hotfix: a pull request picked with `git cherry-pick -m 1`, then bumped and tagged, so that what the back-merge brings of `main`'s first-parent history, from the tag down to the first commit `develop` already holds, has no promotion from `develop`. In a code repo the plain merge of such a release conflicts on the project's version lines by construction, since `main` has moved them to the hotfix's version and `develop` to its placeholder. The merge is therefore made with `git commit-tree` from the tree that `back-merge-check --merge-tree` gives: the automatic merge in which the project's version lines of `develop` and of the merge base are first set to `main`'s. That tree is given only for the version change the release flow makes, the single merge base at a release R and `develop` at R's next-patch placeholder, which R's back-merge opened. The open-cycle commit follows as for any release, so that after the hotfix `X.Y.(Z+1)` `develop` reads `X.Y.(Z+2).dev0`, or `X.Y.(Z+2)-dev0` for `package.json`. The build says which way it went.

Where the check gives no such tree because `develop`'s version is not the one the release flow sets, the command refuses with the version-line repair (the handbook's [`releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md#the-releases-last-step-the-back-merge-pull-request), "The release's last step: the back-merge pull request"), naming the version to restore: one reviewed commit restoring `develop`'s version lines (the version file and its lockfile) to that version, pushed to `develop` directly, with `enforce_admins` switched off and on again where administrators are bound, then `git back-merge` again. The version is R's next-patch placeholder, or, where the merge base is not at a release (a first release reached by a fast-forward), the merge base's own version, which makes the automatic merge clean. Where `develop`'s own version file cannot be read, it refuses with the ordinary repair: a pull request into `develop` that fixes the file, then `git back-merge` again. Where the merge conflicts, or where `develop` and `main` have more than one merge base and their automatic merge is not clean (a clean one is taken as it is), it refuses and prescribes the exception, the direct back-merge (the same section), with its procedure, which every refusal that names the exception states in the same words: in the `develop` worktree, bring `main` and `develop` up to date and run `git merge --no-ff main`; resolve the version lines to `main`'s release version and every other conflict by hand; commit the merge; then, in a code repo, run `git dev-release --open --direct`, which writes the next placeholder and pushes both commits in one push, or, in a `VERSION.txt` repo, push `develop`. Where administrators are bound, switch `enforce_admins` off before that push and on again after it. The pull request that reconciles a conflict, an ordinary pull request into `develop` that brings `develop`'s side of each conflicting passage into agreement with `main`'s, does not apply to a hotfix: there `main`'s side is the older one, and it would undo `develop`'s newer work.

It checks the result with `back-merge-check`, pushes the branch, opens the pull request `chore(release): back-merge main into develop after <tag>` with the label `release-bookkeeping` (created if absent), and closes any open back-merge pull request of an older tag, with a comment naming the new one, since that one's version can no longer equal `main`'s. It waits for `develop`'s required checks and merges with `--merge --match-head-commit`, never `--admin`. Every `gh` call acts on the repository that `origin` names.

Each step first tests whether it is done, so a second run after an interruption resumes, and a pull request merged by another hand while the command waits is recognised as landed; one closed by another hand stops the run, and a new run opens a new pull request. It adopts, rebuilds or closes only pull requests into `develop` from this repository, never a fork's. An open pull request whose head contains `develop` and passes the check is taken as it is; any other is rebuilt from the new `develop` and force-pushed, never updated with GitHub's "Update branch", which the check refuses. The branch is also rebuilt when its head is replaced by another push while the checks run, or when `develop` moves then in a repo that requires up-to-date branches; after three rebuilds the command gives up, leaving the pull request open. It refuses before merging when a version change reached `develop` outside the release flow during a release made by promotion, whether or not the merge would conflict, with the version-line repair (above), naming the version `develop` was promoted at; where `develop` and `main` have more than one merge base, that repair would be wrong, since the promotion can be an earlier release's made from a `develop` that did not yet hold the back-merge that has since moved its version, and it prescribes the exception (above) instead. A release made by promotion whose versions agree is built with `git merge --no-ff` whatever its merge bases, and lands where `back-merge-check` passes it. It seeks that promotion on the tag's first-parent line as far as `develop` already holds it, which is what the back-merge brings of `main`'s own history: a release picked onto `main` is then not compared with a promotion `develop` already holds, and an earlier release's promotion that has not been back-merged is still seen. It refuses any other conflict when it merges, a picked release's as above, and each refusal states its remedy. An error of `back-merge-check`, such as a git before 2.40, is reported as an error, with no repair. In a repo that does not yet allow merge commits it refuses and quotes the handbook's `releases.md`, whose direct back-merge is still in force there. Afterwards it removes its worktree, deletes its branch on `origin` where GitHub has not, fast-forwards the local `develop` worktree (a dry run says it would, and leaves it), and lists the open working branches on `origin` that do not yet contain the new `develop`, with their pull requests, and each pull request into `develop` from a fork that does not, merging into none of them.

It reads `GIT_BACK_MERGE_POLL` (seconds between polls, default 15), `GIT_BACK_MERGE_TIMEOUT` (seconds to wait for the release and for the checks, default 3600) and `PARKVIEWLAB_HANDBOOK` (the released handbook's worktree, default `<org root>/handbook/handbook-main`). In a repo that has not switched it quotes that worktree's `docs/releases.md` section headed exactly "Until a repository has switched". Until a handbook release carries that section, it quotes instead the section as handbook v0.27.0 released it, headed exactly "After the release: the back-merge cascade (mandatory)", while that section still gives the direct back-merge. It quotes no other section, such as the one on the back-merge pull request, whose text names `merge --no-ff` as well.

### `back-merge-check` — what a back-merge pull request may bring

```bash
back-merge-check <base> <head> [<main-ref>] [<tag>]
back-merge-check --merge-tree <develop> <main-ref> <tag>
```

It decides whether a back-merge pull request brings into `develop` exactly the released state of `main` and, at most, the open-cycle commit. No person reviews that pull request before `git back-merge` merges it, so the check is its gate. `git back-merge` runs it on its own branch before pushing; in a repo that has switched, the version guard runs it in its back-merge mode, checked out from dev-tools at a pinned release; both apply one rule. The merge must be the automatic merge of its parents, except that for a release picked onto `main`, in tag mode, it may instead be the merge with the project's version lines of `develop` and of the merge base set to `main`'s, where `develop` and `main` have one merge base, at a release R, and `develop` holds R's next-patch placeholder. The versions it compares are the project's own: `[project].version` in `pyproject.toml` and the top-level `version` in `package.json`, each parsed, and `VERSION.txt` with its whitespace stripped. Its conditions are specified in one place, the comment at the head of [`scripts/back-merge-check`](scripts/back-merge-check). The exit status is 0 when the check passes, 1 when it fails, and 2 on a usage or repository error, such as a shallow clone, a git before 2.40 where a release picked onto `main` needs `git merge-tree --merge-base`, or a version file that nothing at hand can parse.

With `--merge-tree` it prints, on its last line, the tree it accepts for the merge of a back-merge of `<tag>` made from those two commits, exits 1 with the reason where there is none, and exits 2 on such an error; `git back-merge` makes a picked release's merge from that tree.

### Tests

`tests/test_back_merge_check.py` builds, in temporary repositories, the clean back-merges the check passes (with and without the open-cycle commit, for each kind of version file, with lockfiles of a real one's size) and, for each of its conditions, the heads it refuses: extra commits, an altered or hand-resolved merge, parents off `develop` or off `main`, wrong versions, a lockfile left behind or changed on a dependency's line, a second commit in a `VERSION.txt` repo, commits pushed to `main` after the tag, a shallow clone, and attempts to pass other changes through the open-cycle commit or the changelog commit (unusual file names, lines that look like diff headers, a mode change, a submodule whose changes are ignored, NUL bytes, numbers that compare equal, characters a locale collates away, a version line outside `[project]`, and a tag that shadows `main`), besides files with CRLF line endings, which must pass. It builds as well the back-merge of a release picked onto `main`, which it passes with the version lines set to `main`'s (in each kind of version file, with CRLF endings, a lockfile dependency at the project's old version, and another table's version line, none of which may be rewritten) and refuses with a hand edit, with `develop`'s version, with a conflict elsewhere, with two merge bases, or with a version change on `develop` other than the release flow's own, a first release reached by a fast-forward among them; a release made by promotion whose version changed on `develop`, which that path must never admit, also where that promotion is an earlier release's not yet back-merged or the head's merge has a stale first parent; version files whose project version, or name, follows another table's or a nested one, or which cannot be parsed or have nothing to parse them; a git without `merge-tree --merge-base`; and a repository with thousands of release tags. `tests/test_git_back_merge.py` and `tests/test_git_dev_release.py` run the two commands end to end against a bare origin, with fakes of `gh`, `uv` and `npm` from `tests/backmerge_support.py`: the fake GitHub keeps its state in a JSON file, its pull-request merge really merges into the origin's `develop`, it answers errors as `gh` does, and it evaluates `--jq` filters with the system `jq`. The tests run the scripts under the `bash` on `PATH`, or the one `BACKMERGE_TEST_BASH` names. CI runs them under the runner's bash 5; the scripts must also run under macOS's bash 3.2, which CI does not run, so the suite is run locally under `/bin/bash` on a Mac before a release.

## `build-pages-site` — build a repo's documentation site

`build-pages-site` assembles the GitHub Pages site of a repo that publishes its `docs/` (the handbook's [`docs-site.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/docs-site.md)). It is the implementation that the handbook's `pages-docs.yml` template runs: the mechanics live here, and only the page shell (the styling and the introduction) stays per-repo. The one exception is pensa-grex, whose builder it generalises and which still runs its own `scripts/build_pages_site.py`.

It reads `docs/` and `site/` at the repo root and nothing else, and writes into `--out`:

| Path | What |
|---|---|
| `index.html` | generated: the page shell around the introduction (`site/intro.html`) and a list of every document in `docs/` |
| `<page>/` | every other file under `site/`, copied as it is, with the release tag stamped into each `.html` in place of `__LATEST_TAG__` |
| `docs/` | `docs/`, byte-identical to the repo, plus a generated `index.html` in every subfolder that holds documents (a folder that ships its own `index.html` keeps it) |

`site/` is optional, as is the introduction: a repo with neither publishes its `docs/` alone. pensa-grex's download page, `site/downloads/index.html`, is ordinary `site/` content, stamped like any other `.html` under `site/`. The documents are listed in five groups, in order: the northstar (`northstar.html`, else `northstar.md`), the other HTML documents, the Markdown specifications and notes, the ideas under consideration (`in-flight_ideas.md` and `*_ideas.md`), and `CONTRIBUTING.md`; within a group, by title. A Markdown document with an `.html` twin is listed once, under the twin, with a "Markdown source" link. An HTML document's title is its `<title>`, less a leading "ParkviewLab · " (the brand, which the browser tab keeps and the index leaves out, so that branded and unbranded titles read alike), and its description its `<meta name="description">` when present; a Markdown document's title is its first `# ` heading; a document without a title fails the build. HTML documents are linked relatively; Markdown documents open in GitHub's rendered view, pinned to the release tag.

```bash
build-pages-site --out DIR [--tag vX.Y.Z] [--shell FILE] [--repo DIR]
```

- `--out DIR` (required): the directory to assemble into, new or empty. A non-empty directory, or one inside `docs/` or `site/`, is refused.
- `--tag vX.Y.Z`: the release to pin to, for a local run; by default the newest `v*` tag reachable from `HEAD` (`git describe --tags --abbrev=0 --match 'v[0-9]*'`). Either way it must be a `vX.Y.Z` release tag, optionally with a pre-release or build suffix (`v1.2.3-rc.1`); a `vnext` is refused.
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

Standard library only, so the deploy path installs nothing. Nothing generated is committed: the site is assembled into `--out`, and the workflow uploads that directory. The build fails when a document has no title, when a placeholder survives the stamp (after `__LATEST_TAG__` is substituted in the hand-built pages, the shell and the intro, a token still shaped like it: two underscores at one end, one or more at the other, and `TAG` or `LATEST` as a part of its name, such as `__LATEST_TAG_` or `__NEXT_TAG__`; a `__FILE__` quoted in a page is not one), and when a relative `href`, `src` or CSS `url()` in a page it generated or stamped does not resolve against the assembled directory; it only reports an unresolved reference inside an HTML document copied from `docs/`, which is published as the repo holds it, and it does not check copied Markdown at all. Every link to the repository's files on GitHub is pinned to one release tag (the footer's link to the repository itself is not). That tag is the newest `v*` tag reachable from `HEAD` and must be a `vX.Y.Z` release tag, optionally with a pre-release or build suffix; it may be the previous release's when a run starts before this release's tag lands; that leniency is deliberate (a manual re-run on the changelog commit must still build), and a repo with no `v*` tag at all is refused. The contract, and the reasoning behind it, are the handbook's [`docs-site.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/docs-site.md).

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

## `assemble-workflows` — a repo's release workflows from the handbook's parts

Writes a repository's `.github/workflows/release.yml`, and `dev-release.yml` where it has dev builds, from the handbook's parts, by the recipe in the handbook's [`ci.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/ci.md). Needs Python 3.11 or later, for `tomllib`. It is the tool form of that recipe: the head, the gate, the job of each publish target in the order `docker`, `pypi`, `npm`, `installers`, then the job that creates the GitHub Release, with `TARGET_JOBS` replaced by the repo's target jobs and the installers download step kept only with the installers target.

```sh
assemble-workflows --handbook ~/dev/github/ParkviewLab/handbook/handbook-main          # write them
assemble-workflows --handbook ~/dev/github/ParkviewLab/handbook/handbook-main --check  # compare only
```

`--check` writes nothing and reports each difference from the assembly, naming the job it falls in. A pin of a dev-tools release, the `ref:` line of a step that checks out `ParkviewLab/dev-tools`, is the repo's own: the handbook's pin rule lets it differ from the part's, since a pin at or after its floor is current, so the check leaves it out of the comparison and prints it on a line of its own, for the convention auditor and the release preflight to judge by that rule; and writing the workflows keeps the repo's own pin in each job rather than the part's. It exits 0 when every workflow matches or every difference is a declared slot, 1 when a difference is undeclared, and 2 on a usage or declaration error, so CI and the convention auditor can run it.

What a repo publishes, and where it differs from the parts on purpose, is declared in `.github/workflows/.assembly.toml`:

```toml
targets = ["docker", "pypi"]   # the release targets, in any order
dev = true                     # dev builds; false when the key is absent
header = "…"                   # the SPDX header, placed above the head part

[[slots]]                      # each documented difference from a part
job = "docker"                 # the job as `--check` prints it
reason = "three images from one Dockerfile, one matrix leg each"
workflow = "release"           # or "dev-release", or "both"; default "release"
```

Dev parts exist for `docker`, `pypi` (as `testpypi`) and `installers`; `npm` has none, since dev builds are for local testing, so `dev = true` with no such target is a declaration error. The blank and comment lines that introduce a job count as part of it, so the comment documenting a slot falls in the job it documents; a difference in the lines above the first job is reported as `the head`, and a slot declares it as `job = "the head"`. Writing the workflows removes a `dev-release.yml` the declaration no longer calls for, so that a write is always followed by a passing check.

A repo with no such file has its targets read from the jobs its `release.yml` already carries and its header from that file's leading comment, and declares no slot, so the check runs anywhere without preparing the repo first.

### Tests

`tests/test_assemble_workflows.py` builds a small handbook of parts and a repo in a temporary directory for each case: the target combinations in use and all four together in the recipe's order, the installers download step kept and dropped, the documents target's own final job, the header on both workflows, a stale dev workflow removed, an inferred declaration, the job a difference is attributed to (a leading comment belongs to the job it introduces), a declared slot passing the check and an undeclared difference failing it, a slot's scope over the two workflows, a dev-tools pin left to the pin rule by the check and kept by the assembly, and each declaration error. The parts the fixtures build are shaped like the handbook's own, leading blank line and comment block included, since the attribution depends on them. Standard-library `unittest`, no network.

## Release flow (in brief)

Releases are tag-driven and cut from `main`; CI gates publish on the tag being reachable from `origin/main`. The full flow + rationale (why bump+tag on `main`, the back-merge cascade, the CI gate) lives in the **[handbook's `releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md)**. The one-liner:

```bash
# on the <repo>-main worktree, after promoting develop -> main:
git bump <patch|minor|major|release>
git release
git push --follow-tags        # CI publishes
git back-merge                # a repo that allows merge commits; before its switch, the direct back-merge of releases.md
```

dev-tools is itself a `VERSION.txt` repo and is **released with these very tools** — `VERSION.txt` is the source of truth, bumped by `git bump` and tagged by `git release`. It ships no package, so a release promotes `develop → main` and tags, and the tag's push runs `.github/workflows/release.yml`, the handbook's documents assembly (`head.yml` + `gate.yml` + `documents.yml`) byte for byte: the three-check gate (the tag equals `VERSION.txt`, which carries no dev marker; the tagged commit is on `main`; the version is greater than the previous tag's), then a GitHub Release with GitHub's generated notes. The gate runs once the tag exists, so it reports a bad tag but cannot prevent it. A ruleset on dev-tools refuses the move or deletion of any `v*` tag and names no bypass actor, so the gate's advice to re-tag from `main` cannot be followed here: a tag whose release run fails stays, no pin moves to it, and the next patch release supersedes it.

## Adding a tool

1. Drop the script (executable, with its shebang: `#!/usr/bin/env bash`; `#!/usr/bin/env python3` for a standard-library Python script; or `#!/usr/bin/env -S uv run --script` for a Python script that declares a dependency at an exact version in its PEP 723 metadata, with `[tool.uv] exclude-newer` fixing that dependency's own dependencies, and imports it only where it is used, so that its tests need the standard library alone) into `scripts/`. Non-executable files (like `_sot.sh`) are *sourced*, not symlinked.
2. Document it here.
3. PR onto `develop`. The bar: generic + cross-project, no project-specific logic. If it's only useful in one repo, it lives in that repo's `scripts/`.

## License

AGPL-3.0-or-later for the tooling and its tests (`scripts/**`, `tests/**`, `install.sh`, CI); CC-BY-4.0 for the docs, the Markdown under `tests/` included, and the repo meta. See [`LICENSING.md`](LICENSING.md).

---
<sub>© 2026 Gary Frattarola · Licensed under [CC-BY-4.0](LICENSES/CC-BY-4.0.txt) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
