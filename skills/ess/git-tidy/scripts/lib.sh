#!/usr/bin/env bash
#
# lib.sh - shared helpers for the git-tidy skill scripts.
#
# Sourced (not executed) by the other scripts in this directory. It sets no
# shell options and owns no `set -e/-u`: each script keeps its own. Portable to
# bash 3.2 (macOS): no associative arrays / mapfile.
#
# Source it with, right after the `set ...` line:
#   _LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=lib.sh
#   . "${_LIB_DIR}/lib.sh"

# --- logging (stderr, colorized) ---------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }
info()  { echo -e "${GREEN}=>${NC} $1" >&2; }
warn()  { echo -e "${YELLOW}Warning:${NC} $1" >&2; }

# --- git ---------------------------------------------------------------------
# Exit unless the cwd is inside a git work tree. Callers must cd into the target
# repo first; git-tidy always operates on the repo containing the cwd, never on
# the tree that happens to hold this skill.
require_git_repo() {
  git rev-parse --git-dir >/dev/null 2>&1 || error "not inside a git repository"
}

# Toplevel of the repo containing the cwd. Falls back to $PWD outside a repo.
repo_root() { git rev-parse --show-toplevel 2>/dev/null || pwd; }

# True when <ref> resolves to a commit.
ref_exists() { git rev-parse --verify --quiet "$1^{commit}" >/dev/null 2>&1; }

# Echo the first of the candidate refs that exists. Empty when none do.
first_existing_ref() {
  local ref
  for ref in "$@"; do
    if ref_exists "$ref"; then echo "$ref"; return 0; fi
  done
  return 1
}

# Strip a leading "<remote>/" from a ref: origin/main -> main.
strip_remote_prefix() { echo "${1#*/}"; }

# --- tool availability -------------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }

# --- hashing -----------------------------------------------------------------
# Short hex hash of a string (sha1, 8 chars), tolerant of hosts lacking shasum.
hash_str() {
  if have shasum; then
    printf '%s' "$1" | shasum | cut -c1-8
  elif have sha1sum; then
    printf '%s' "$1" | sha1sum | cut -c1-8
  else
    printf '%s' "$1" | cksum | tr -d ' ' | cut -c1-8
  fi
}

# --- formatting --------------------------------------------------------------
# Human-readable size from a kilobyte count: 1536 -> "1.5M".
human_size() {
  local kb="${1:-0}"
  if [[ -z "$kb" || "$kb" == "0" ]]; then
    echo "-"
  elif [[ "$kb" -lt 1024 ]]; then
    echo "${kb}K"
  elif [[ "$kb" -lt 1048576 ]]; then
    awk -v k="$kb" 'BEGIN { printf "%.1fM", k / 1024 }'
  else
    awk -v k="$kb" 'BEGIN { printf "%.1fG", k / 1048576 }'
  fi
}

# Escape a string for embedding in a JSON double-quoted value.
json_escape() {
  printf '%s' "$1" | awk '
    BEGIN { RS = "\n"; first = 1 }
    {
      gsub(/\\/, "\\\\")
      gsub(/"/, "\\\"")
      gsub(/\t/, "\\t")
      gsub(/\r/, "\\r")
      if (!first) printf "\\n"
      printf "%s", $0
      first = 0
    }
  '
}

# --- tsv ---------------------------------------------------------------------
# Look up a row in a TSV file by exact match on field <col>, echoing the row.
# Empty output when no row matches. Branch names and paths cannot contain tabs,
# so exact field matching is safe.
tsv_lookup() {
  local file="$1" col="$2" key="$3"
  [[ -f "$file" ]] || return 0
  awk -F'\t' -v c="$col" -v k="$key" '$c == k { print; exit }' "$file"
}

# Echo field <n> of a tab-separated row.
tsv_field() { echo "$1" | cut -f"$2"; }
