#!/usr/bin/env bash
#
# lib.sh - shared helpers for the pr-review skill scripts.
#
# Sourced (not executed) by the other scripts in this directory. It sets no
# shell options and owns no `set -e/-u`: each script keeps its own so that the
# lint scripts (which intentionally continue past tool failures) and the strict
# scripts (which exit on error) both behave correctly. Portable to bash 3.2
# (macOS): no associative arrays / mapfile.
#
# Source it with, right after the `set ...` line:
#   _LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=lib.sh
#   . "${_LIB_DIR}/lib.sh"

# --- logging (stderr, colorized) ---------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }
info()  { echo -e "${GREEN}→${NC} $1" >&2; }
warn()  { echo -e "${YELLOW}Warning:${NC} $1" >&2; }

# --- git ---------------------------------------------------------------------
# Toplevel of the repo containing the CURRENT WORKING DIRECTORY -- i.e. the tree
# being scanned/reviewed, NOT the tree that holds this skill. Callers must cd
# into the target repo first. Falls back to $PWD when outside a git repo.
repo_root() { git rev-parse --show-toplevel 2>/dev/null || pwd; }

# Exit with an error unless the cwd is inside a git work tree. Use before
# repo_root() when the pwd fallback would be wrong (e.g. worktree creation).
require_git_repo() {
  git rev-parse --git-dir >/dev/null 2>&1 || error "not inside a git repository"
}

# --- tool runners ------------------------------------------------------------
# Prefer the repo venv via uv when available, else bare python3.
py_runner() {
  if command -v uv >/dev/null 2>&1 && uv run python --version >/dev/null 2>&1; then
    echo "uv run python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  fi
}

# Echo a command prefix that can run the given tool via the repo venv (uv) when
# available, else the bare executable, else empty when unavailable.
resolve_tool() {
  local tool="$1"
  if command -v uv >/dev/null 2>&1 && uv run "$tool" --version >/dev/null 2>&1; then
    echo "uv run $tool"
  elif command -v "$tool" >/dev/null 2>&1; then
    echo "$tool"
  fi
}

# --- json / status helpers ---------------------------------------------------
# True when <file> exists, is non-empty, and starts with '[' (a JSON array).
is_json_array() { [[ -s "$1" ]] && [[ "$(head -c1 "$1")" == "[" ]]; }

# Append "tool<TAB>status" to $STATUS_FILE. The caller sets STATUS_FILE (usually
# "${OUT_DIR}/tools.tsv") before invoking this.
status() { printf '%s\t%s\n' "$1" "$2" >> "$STATUS_FILE"; }

# Read non-empty lines of <file> into the global FILES array (bash 3.2 safe).
read_file_list() {
  FILES=()
  local line
  while IFS= read -r line; do
    [[ -n "$line" ]] && FILES+=("$line")
  done < "$1"
}

# --- hashing -----------------------------------------------------------------
# Short hex hash of a string (sha1, 8 chars), tolerant of hosts lacking shasum.
hash_str() {
  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$1" | shasum | cut -c1-8
  elif command -v sha1sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha1sum | cut -c1-8
  else
    printf '%s' "$1" | cksum | tr -d ' ' | cut -c1-8
  fi
}

# Longer hex hash of a string (sha256, 12 chars) for /worktree-compatible repo
# keys. Falls back to openssl on hosts shipping neither shasum nor sha256sum.
sha256_short() {
  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$1" | shasum -a 256 | cut -c1-12
  elif command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | cut -c1-12
  else
    printf '%s' "$1" | openssl dgst -sha256 | awk '{print $NF}' | cut -c1-12
  fi
}
