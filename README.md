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

## Conventions enforced

These tools encode three patterns shared across every Python repo in ParkviewLab:

1. **`pyproject.toml` is the single source of truth for version.** Nothing else hard-codes or duplicates it.
2. **Tags are derived from pyproject; never typed.** `git release` enforces this.
3. **Release CI verifies the tag matches pyproject before publishing.** A defense-in-depth check; the tag wouldn't disagree if you used `git release`, but the check catches manual-tag mistakes.

Together, you can't accidentally ship a tag that disagrees with the wheel.

## Adding a new tool

1. Drop the script (executable, `#!/usr/bin/env bash` or similar) into `scripts/`.
2. Add a section to this README.
3. PR onto `develop`. Reviewer confirms the script is generic enough to belong here (cross-project, opinionated about cross-project conventions, no project-specific logic).

If a script is only useful in one repo, it lives in that repo's `scripts/`, not here.

## License

MIT. See `LICENSE`.
