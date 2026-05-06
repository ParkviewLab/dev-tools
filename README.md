# ParkviewLab dev-tools

Shared developer tooling for repos under [`ParkviewLab/`](https://github.com/ParkviewLab) — small scripts that don't justify their own repo but want to live in one canonical place.

## Install

Clone once, run `install.sh`, done. The installer symlinks every script in `scripts/` into `~/.local/bin/` so each one is on `$PATH` as `git-<verb>` (or whatever its name is).

```bash
git clone https://github.com/ParkviewLab/dev-tools.git ~/dev-tools
cd ~/dev-tools
./install.sh
```

Updates: `cd ~/dev-tools && git pull`. Because the installer symlinks (not copies), every dev that ran `install.sh` once gets the new scripts on the next `git pull` — no re-run needed.

To remove: `./uninstall.sh` (planned).

### Requirements

- `~/.local/bin` on `$PATH` (default on most modern macOS / Linux setups).
- `uv` on `$PATH` for the Python helpers (`git-release`, `git-bump`).
- Bash 4+ (every script is `#!/usr/bin/env bash`).

## Scripts

### `git release` — tag a Python project release

Reads `[project].version` from `pyproject.toml` in the current directory and creates an annotated tag `v<version>` on `HEAD`. Refuses if the worktree is dirty or the tag already exists. Does **not** push — tells you the command to push.

```bash
git release
# tagged v0.1.5 (HEAD: abc1234)
# push with: git push --follow-tags
```

Why: Python projects in ParkviewLab keep the version in `pyproject.toml` only (single source of truth). Typing the version on `git tag` is a drift hazard. `git release` derives it.

### `git bump` — bump pyproject version + commit

Bumps `[project].version` in `pyproject.toml` (via `uv version --bump`), `git add`s the change (and `uv.lock` if uv touched it), commits with message `release v<new>`. Does **not** tag — that's `git release`'s job.

```bash
git bump patch    # 0.1.5 → 0.1.6
git bump minor    # 0.1.6 → 0.2.0
git bump major    # 0.2.0 → 1.0.0
git bump 0.1.7    # explicit version
```

Why split bump from tag: separation of concerns. You can review the bump commit in `git log` before tagging. The full release flow becomes:

```bash
git bump patch
git release
git push --follow-tags
```

## Release flow

Every ParkviewLab Python project follows the same flow ("Flow B"). The bump and tag both happen on `main`; CI gates publish on the tag being reachable from `origin/main`.

```
work on claude → merge claude → develop → merge develop → main
on main:
  git bump <patch|minor|major>     # creates "release v<new>" commit on main
  git release                       # annotated tag v<new>
  git push --follow-tags            # CI fires
back-merge:
  git -C ../develop merge main && git -C ../develop push
```

**Why bump+tag on main (not on `claude`):** clean feature-branch history; the bump is a deliberate "I'm shipping" act on main; the tag is trivially reachable from `origin/main` (the CI gate passes by construction); the bump commit never travels through merge conflicts.

**Why back-merge `main → develop` after release:** without it, develop's `pyproject.toml` lags main's, and the next `develop → main` promotion has a needless conflict on the version line every. single. time. The back-merge is two commands; do it immediately after pushing the tag.

**The CI gate** (in each repo's `.github/workflows/release.yml`) runs two checks before either publish job:

1. Tag matches `[project].version` in `pyproject.toml`.
2. Tagged commit is reachable from `origin/main`.

Both `docker` and `pypi` jobs `needs: gate`, so a failure prevents *any* artifact from shipping — no half-shipped state.

## Conventions enforced

These tools encode four patterns shared across every Python repo in ParkviewLab:

1. **`pyproject.toml` is the single source of truth for version.** Nothing else hard-codes or duplicates it.
2. **Tags are derived from pyproject; never typed.** `git release` enforces this.
3. **Releases come from `main`.** `git bump` + `git release` happen on the `main` worktree; `claude` and `develop` aren't release surfaces.
4. **Release CI gates publish on both invariants.** Tag-vs-pyproject mismatch *or* tag not reachable from `origin/main` → no artifact ships.

Together, you can't accidentally ship a tag that disagrees with the wheel, or ship from a branch that hasn't been promoted to `main`.

## Adding a new tool

1. Drop the script (executable, `#!/usr/bin/env bash` or similar) into `scripts/`.
2. Add a section to this README.
3. PR onto `develop`. Reviewer confirms the script is generic enough to belong here (cross-project, opinionated about cross-project conventions, no project-specific logic).

If a script is only useful in one repo, it lives in that repo's `scripts/`, not here.

## License

MIT. See `LICENSE`.
