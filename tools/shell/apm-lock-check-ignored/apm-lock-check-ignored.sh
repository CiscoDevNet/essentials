#!/usr/bin/env bash
#
# Fail when apm.lock.yaml records a git-ignored file. APM copies every file in a
# skill directory, ignored or not, so a scratch file or secret left next to a
# skill's source would be deployed to .agents/skills/ and committed, by name and
# hash, in the lock.
#
# Usage:
#   ./tools/shell/apm-lock-check-ignored/apm-lock-check-ignored.sh [LOCK_FILE]
#
# Checks each deployed file and, for local dependencies, the source file it was
# copied from: a nested .gitignore in the source may not reach the copy. Reads
# only. Exits 1 if any file is ignored, 2 on a usage or git error.

set -euo pipefail

_LOCK_FILE="apm.lock.yaml"

# Print every deployed path in the lock, each followed, for a local dependency,
# by the source path it was copied from. Relies on the layout APM writes:
# dependencies are top-level "- " items with two-space-indented keys. A
# transitive local dependency's local_path is relative to the skill that
# declared it (../sibling); its anchored_local_path is relative to the root.
list_lock_paths() {
  awk '
    function flush(   i, marker, at, source) {
      marker = "skills/" name
      source = anchored_path != "" ? anchored_path : local_path
      for (i = 1; i <= count; i++) {
        print files[i]
        if (source == "") continue
        at = index(files[i], marker)
        if (at == 0) continue
        print source substr(files[i], at + length(marker))
      }
      count = 0
      name = ""
      local_path = ""
      anchored_path = ""
    }
    /^- / { flush(); in_files = 0 }
    /^[a-z_]+:/ { flush(); in_files = 0; next }
    /^  deployed_files:/ { in_files = 1; next }
    in_files && /^  - / { files[++count] = substr($0, 5); next }
    /^  [a-z_]+:/ { in_files = 0 }
    /^(- |  )name: / { name = $NF }
    /^  local_path: / { local_path = $NF; sub(/^\.\//, "", local_path) }
    /^  anchored_local_path: / { anchored_path = $NF; sub(/^\.\//, "", anchored_path) }
    END { flush() }
  ' "$1"
}

apm_lock_check_ignored() (
  local lock_file="${1:-$_LOCK_FILE}"
  if [[ ! -f "$lock_file" ]]; then
    echo "Error: ${lock_file} not found" >&2
    return 2
  fi

  # Lock paths are relative to the project root, where the lock lives.
  cd "$(dirname "$lock_file")"
  lock_file="$(basename "$lock_file")"

  local ignored
  local status=0
  # Tracked files are never reported, so a committed file that matches an
  # ignore pattern passes. Non-verbose output omits negated matches such as
  # !.env.example; those can still exit 0 with an empty list, which is clean.
  ignored=$(list_lock_paths "$lock_file" | git check-ignore --stdin) || status=$?
  case "$status" in
    0)
      if [[ -z "$ignored" ]]; then
        return 0
      fi
      echo "Error: ${lock_file} records git-ignored files:" >&2
      printf '%s\n' "$ignored" | sed 's/^/  /' >&2
      echo "APM copies every file in a skill directory. Move these out of it," >&2
      echo "rerun apm install, and commit the lock again." >&2
      return 1
      ;;
    1) return 0 ;;
    *)
      echo "Error: git check-ignore failed (exit ${status})" >&2
      return 2
      ;;
  esac
)

# Run only when executed directly. Sourcing just loads the functions.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  apm_lock_check_ignored "$@"
fi
