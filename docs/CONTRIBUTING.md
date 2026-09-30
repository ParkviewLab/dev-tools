<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>

SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing

This repo follows the ParkviewLab conventions; the authoritative, org-wide version of all of this is the [ParkviewLab handbook](https://github.com/ParkviewLab/handbook/tree/main). The essentials:

## Branch & PR flow

- Branch off `develop` into an ephemeral worktree named with a prefix: `feature-`, `bug-`/`fix-`, `doc-`, `test-`, `ops-`, `ci-`, `build-`, `release-` (hyphen, not slash). See the handbook's `branching.md`.
- Open a PR into `develop`. The repo is merge-commit only, so the merge button can only make a merge commit; merging is the maintainer's action.
- Releases are cut from `main` via the CLI (`git merge --no-ff develop`, then `git bump` and `git release`), not a PR, and end with the back-merge pull request from `back-merge-<tag>`, which `git back-merge` opens, checks and merges. See the handbook's `releases.md`.

## Commit / PR-title convention (this is what the release notes read)

A PR is merged with a merge commit titled `<PR title> (#N)`, so the PR title becomes the commit subject. A release publishes a GitHub Release whose notes GitHub generates from the merged pull requests, one line for each, with its title and link; `.github/release.yml` leaves the back-merge pull requests out, and this repository keeps no `CHANGELOG.md`. Prefix every PR title with a [Conventional Commit](https://www.conventionalcommits.org/) type (`feat:`, `fix:`, `perf:`, `refactor:`, `docs:`, `test:`, `revert:`, or `chore:` / `ci:` / `build:` / `style:` for maintenance), with a `!` after the type for a breaking change.

## Local checks before opening a PR

Run the same checks CI requires, so the PR is green on arrival:

```bash
python3 -m unittest discover -s tests -v
uvx --from "reuse[charset-normalizer]" reuse lint
```

A PR can't be merged until the required checks pass (the tests, REUSE, the version guard; see the handbook's `ci.md`). Push after each commit.

## Versioning

The version lives in `VERSION.txt` only; never hard-code it elsewhere, and never type it on a `git tag` line: use `git bump` / `git release` from this repository. See the handbook's `releases.md`.

## Changes to the scripts that workflows run

Three scripts run inside other repositories' workflows, each from a checkout of this repository at an exact release: `back-merge-check` (the version guard), `generate-changelog` (the release's changelog job) and `build-pages-site` (the documentation site). A change to one of them reaches a repository only when that repository's pin moves: the version guard's and the changelog job's pins follow the floor policy in the handbook's `ci.md` ("Shared dev scripts"), and the documentation site's pin is bumped deliberately (`docs-site.md`). So a release that changes `back-merge-check` or `generate-changelog` raises that script's floor, and a release that changes any of the three should say in its notes what changed for the repositories that pin it.

## AI contributors

Follow the behavioural contract in the handbook's `ai-collaboration.md` (notably: merging a feature pull request is the user's action, and tagging and releasing need an explicit, per-release go-ahead).
