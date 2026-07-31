#!/usr/bin/env bash
#
# scan_disables.sh <out_dir> <base> <head>
#
# Scans the ADDED lines of the diff for suppression comments the PR introduces:
#   Python:     # pylint: disable=...   # noqa   # type: ignore
#   TypeScript: // @ts-ignore   // @ts-expect-error
#
# Writes <out_dir>/disables.json as a JSON array of {path, line, text}, where
# line is the new-file line number. The LLM evaluates whether each suppression
# is justified (see references/pylint-disables.md) -- this script only locates
# them. Uses only git + awk (no jq / python dependency).

set -uo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${_LIB_DIR}/lib.sh"

OUT_DIR="${1:?usage: scan_disables.sh <out_dir> <base> <head>}"
BASE="${2:?missing base ref}"
HEAD="${3:?missing head ref}"

# Capture the diff first so a git failure (bad refs, missing commits) is caught
# and surfaced to the caller, rather than feeding awk an empty stream and writing
# a silently incomplete disables list.
if ! DIFF="$(git diff --no-color "${BASE}...${HEAD}" -- '*.py' '*.pyi' '*.ts' '*.tsx' 2>/dev/null)"; then
  error "scan_disables.sh: git diff failed for ${BASE}...${HEAD}"
fi

printf '%s\n' "$DIFF" | awk '
function esc(s) {
  gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); gsub(/\t/, " ", s); sub(/\r$/, "", s)
  return s
}
BEGIN { printf "["; first = 1 }
/^\+\+\+ / { f = $2; sub(/^b\//, "", f); next }
/^--- /    { next }
/^@@ /     { h = $3; sub(/^\+/, "", h); split(h, a, ","); ln = a[1] + 0; next }
{
  c = substr($0, 1, 1); rest = substr($0, 2)
  if (c == "+") {
    if (rest ~ /pylint:[[:space:]]*disable/ \
        || rest ~ /(#|\/\/)[[:space:]]*noqa/ \
        || rest ~ /type:[[:space:]]*ignore/ \
        || rest ~ /@ts-(ignore|expect-error)/) {
      body = rest; sub(/^[[:space:]]+/, "", body)
      if (first) { first = 0 } else { printf "," }
      printf "\n  {\"path\": \"%s\", \"line\": %d, \"text\": \"%s\"}", esc(f), ln, esc(body)
    }
    ln++
  } else if (c == " ") {
    ln++
  }
}
END { if (first) printf "]\n"; else printf "\n]\n" }
' > "${OUT_DIR}/disables.json"
