# ParkviewLab dev-tools

Shared developer tooling for repos under [`ParkviewLab/`](https://github.com/ParkviewLab) — small scripts that don't justify their own repo but want to live in one canonical place.

## Install

Clone once, run `install.sh`. The installer symlinks every **executable** script in `scripts/` into `~/.local/bin/`, so each is on `$PATH` as `git-<verb>`.

```bash
git clone git@github.com:ParkviewLab/dev-tools.git ~/dev-tools
cd ~/dev-tools
./install.sh
```

Updates: `git pull`. Because the installer **symlinks** (not copies), a changed script is picked up on the next `git pull` with no re-run; a **brand-new** command needs one more `install.sh` run to add its symlink.

### Requirements

- `~/.local/bin` on `$PATH` (default on most modern macOS / Linux setups).
- Bash 4+ (every script is `#!/usr/bin/env bash`).
- Per the repo's version source of truth: `uv` for `pyproject.toml`, `node`/`npm` for `package.json`, nothing extra for `VERSION.txt`.
- `gh` (GitHub CLI) for `git dev-release`.

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

Run from `develop`. Bumps the source of truth to the next **dev** version, commits, pushes `develop`, and dispatches the repo's `dev-release.yml` (which publishes a GHCR `:dev` image + `X.Y.Z.devN` to TestPyPI). For real releases use `git bump` / `git release`.

```bash
git dev-release patch       # next dev build toward the next patch
git dev-release minor       # re-points the cycle to the next minor (major likewise)
git dev-release --open      # open the next cycle post-release: X.Y.(Z+1).dev0 (no publish)
git dev-release --dry-run patch
```

- **A dev version names the *next* release** + `.devN` (PEP 440): `0.1.5 < 0.1.6.dev0 < 0.1.6`. Builds toward the same target tick the counter (`dev0`, `dev1`, …) so each published artifact is distinct (TestPyPI rejects duplicates).
- **`--open`** is run right after a release (part of the back-merge cascade) to set `develop`'s honest version to the next-patch placeholder.
- `VERSION.txt` repos get a plain `-dev` marker and publish nothing — the dev *build* path is code-repo-only.

The full convention — when to open a cycle, how it interacts with `version-guard` and the release gate — is the **[handbook's `releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md) ("Development versioning")** + `ci.md` (`dev-release.yml`). dev-tools is the *tooling*; the handbook is the source of truth for the *flow*.

## Release flow (in brief)

Releases are tag-driven and cut from `main`; CI gates publish on the tag being reachable from `origin/main`. The full flow + rationale (why bump+tag on `main`, the back-merge cascade, the CI gate) lives in the **[handbook's `releases.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/releases.md)**. The one-liner:

```bash
# on the <repo>-main worktree, after promoting develop -> main:
git bump <patch|minor|major|release>
git release
git push --follow-tags        # CI publishes
# then back-merge main -> develop
```

dev-tools is itself a `VERSION.txt` repo and is **released with these very tools** — `VERSION.txt` is the source of truth, bumped by `git bump` and tagged by `git release`. It ships no package, so a release just promotes `develop → main` and tags (no CI publish step).

## Adding a tool

1. Drop the script (executable, `#!/usr/bin/env bash`) into `scripts/`. Non-executable files (like `_sot.sh`) are *sourced*, not symlinked.
2. Document it here.
3. PR onto `develop`. The bar: generic + cross-project, no project-specific logic. If it's only useful in one repo, it lives in that repo's `scripts/`.

## License

AGPL-3.0-or-later for the tooling (`scripts/**`, `install.sh`, CI); CC-BY-4.0 for the docs & repo meta. See [`LICENSING.md`](LICENSING.md).

---
<sub>© 2026 Gary Frattarola · Licensed under [CC-BY-4.0](LICENSES/CC-BY-4.0.txt) · part of [ParkviewLab](https://github.com/ParkviewLab)</sub>
