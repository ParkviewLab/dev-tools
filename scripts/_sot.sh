#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# _sot.sh — version Source-of-Truth helpers for the ParkviewLab git-* release scripts.
# Sourced (not run) by git-bump, git-release, git-dev-release. NOT executable, so
# install.sh does not symlink it as a `git-` command.
#
# Three SoT shapes, auto-detected: pyproject.toml ([project].version), package.json
# (version), and a top-level VERSION.txt. See the handbook's releases.md.

# --- detection -------------------------------------------------------------
sot_kind() {  # echoes: pyproject | package | version-txt ; non-zero if none
  if   [[ -f pyproject.toml ]]; then echo pyproject
  elif [[ -f package.json   ]]; then echo package
  elif [[ -f VERSION.txt    ]]; then echo version-txt
  else
    echo "no version source of truth (pyproject.toml / package.json / VERSION.txt) in $(pwd)" >&2
    return 1
  fi
}

# --- read ------------------------------------------------------------------
sot_read() {  # echoes the current version
  case "$(sot_kind)" in
    pyproject)   uv run --quiet python -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' ;;
    package)     node -p "require('./package.json').version" 2>/dev/null || python3 -c 'import json;print(json.load(open("package.json"))["version"])' ;;
    version-txt) tr -d '[:space:]' < VERSION.txt ;;
  esac
}

# --- write -----------------------------------------------------------------
sot_write() {  # $1 = new version. writes it; echoes the file(s) to `git add`.
  local v="$1" files
  case "$(sot_kind)" in
    pyproject)
      uv version "$v" >/dev/null
      files="pyproject.toml"
      [[ -n "$(git status --porcelain uv.lock 2>/dev/null)" ]] && files="$files uv.lock" ;;
    package)
      npm version "$v" --no-git-tag-version --allow-same-version >/dev/null
      files="package.json"
      [[ -n "$(git status --porcelain package-lock.json 2>/dev/null)" ]] && files="$files package-lock.json" ;;
    version-txt)
      printf '%s\n' "$v" > VERSION.txt
      files="VERSION.txt" ;;
  esac
  echo "$files"
}

# --- version math (Option A: smart finalize) -------------------------------
sot_strip_dev() {  # $1 -> public base (drops .devN / -dev[N])
  local b="${1%%.dev*}"; b="${b%%-dev*}"; echo "$b"
}

sot_last_release() {  # most recent vX.Y.Z tag (sans the v), or empty
  local t; t="$(git describe --tags --match 'v[0-9]*' --abbrev=0 2>/dev/null)" || return 0
  echo "${t#v}"
}

# sot_compute_next <current> <major|minor|patch|release|EXPLICIT>
sot_compute_next() {
  local cur="$1" arg="$2" base start X Y Z
  base="$(sot_strip_dev "$cur")"
  case "$arg" in
    release) echo "$base"; return ;;          # finalize: ship the declared target
    major|minor|patch) ;;                      # fall through
    *) echo "$arg"; return ;;                  # explicit version string
  esac
  if [[ "$base" != "$cur" ]]; then            # a dev version -> re-point off the last release
    start="$(sot_last_release)"; [[ -z "$start" ]] && start="$base"
  else                                         # a plain version -> increment in place
    start="$base"
  fi
  IFS=. read -r X Y Z <<<"$start"
  case "$arg" in
    major) echo "$((X+1)).0.0" ;;
    minor) echo "$X.$((Y+1)).0" ;;
    patch) echo "$X.$Y.$((Z+1))" ;;
  esac
}

# --- dev versions (for git-dev-release) ------------------------------------
sot_dev_n() {  # echoes the .devN / -devN number in $1, or -1 if none
  case "$1" in
    *.dev[0-9]*) echo "${1##*.dev}" ;;
    *-dev[0-9]*) echo "${1##*-dev}" ;;
    *)           echo -1 ;;
  esac
}

# sot_dev_version <current> <major|minor|patch> -> the next dev version toward that target
sot_dev_version() {
  local cur="$1" kind="$2" target n sep k
  k="$(sot_kind)"
  target="$(sot_compute_next "$cur" "$kind")"
  if [[ "$k" == version-txt ]]; then
    echo "${target}-dev"; return            # docs repos publish nothing -> no counter needed
  fi
  # Pre-release separator is SoT-specific: PEP-440 '.devN' for pyproject (PyPI),
  # but semver '-devN' for package (npm / electron-builder reject '.devN').
  # Either form is read back by sot_dev_n / sot_strip_dev.
  if [[ "$k" == pyproject ]]; then sep=".dev"; else sep="-dev"; fi
  n="$(sot_dev_n "$cur")"
  if [[ "$(sot_strip_dev "$cur")" == "$target" && "$n" -ge 0 ]]; then
    echo "${target}${sep}$((n+1))"          # next build toward the same target
  else
    echo "${target}${sep}0"                 # first build toward a (new) target
  fi
}
