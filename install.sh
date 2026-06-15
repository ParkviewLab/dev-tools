#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# install.sh — symlink every script in scripts/ into ~/.local/bin/
#
# Idempotent. Re-run safely: existing symlinks pointing at our scripts are left alone;
# existing files / wrong-target symlinks are replaced (-f).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$REPO_DIR/scripts"
TARGET_DIR="${HOME}/.local/bin"

if [[ ! -d "$SCRIPTS_DIR" ]]; then
  echo "install.sh: no scripts/ directory at $SCRIPTS_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

# Warn if ~/.local/bin isn't on PATH.
case ":$PATH:" in
  *":$TARGET_DIR:"*) ;;
  *) echo "install.sh: warning — $TARGET_DIR is not on \$PATH; add it to your shell rc" >&2 ;;
esac

installed=()
skipped=()

for script in "$SCRIPTS_DIR"/*; do
  [[ -f "$script" && -x "$script" ]] || continue
  name="$(basename "$script")"
  link="$TARGET_DIR/$name"

  # If link already points at our script, leave alone.
  if [[ -L "$link" && "$(readlink "$link")" == "$script" ]]; then
    skipped+=("$name")
    continue
  fi

  ln -sf "$script" "$link"
  installed+=("$name")
done

if (( ${#installed[@]} )); then
  echo "installed: ${installed[*]}"
fi
if (( ${#skipped[@]} )); then
  echo "already linked: ${skipped[*]}"
fi
echo "→ $TARGET_DIR"
