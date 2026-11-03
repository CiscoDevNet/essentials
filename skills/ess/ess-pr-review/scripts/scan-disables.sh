#!/usr/bin/env bash
#
# scan-disables.sh <out_dir> <base> <head>
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

OUT_DIR="${1:?usage: scan-disables.sh <out_dir> <base> <head>}"
BASE="${2:?missing base ref}"
HEAD="${3:?missing head ref}"

# Names come from a NUL-delimited diff so spaces and Git quoting stay intact.
# Each file's diff is parsed separately; the path is passed in, not read from
# the +++ header.
NAMES="$(mktemp)"
FINDINGS="$(mktemp)"
cleanup_scan() { rm -f "$NAMES" "$FINDINGS"; }
trap cleanup_scan EXIT

if ! git diff -z --name-only --diff-filter=ACMR "${BASE}...${HEAD}" -- \
  '*.py' '*.pyi' '*.ts' '*.tsx' >"$NAMES" 2>/dev/null; then
  error "scan-disables.sh: git diff failed for ${BASE}...${HEAD}"
fi

while IFS= read -r -d '' path; do
  [[ -n "$path" ]] || continue
  if ! FILE_DIFF="$(git diff --no-color "${BASE}...${HEAD}" -- "$path" 2>/dev/null)"; then
    error "scan-disables.sh: git diff failed for ${path}"
  fi
  SCAN_PATH="$path" awk '
function esc(s) {
  gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); gsub(/\t/, " ", s); sub(/\r$/, "", s)
  return s
}
BEGIN { path = ENVIRON["SCAN_PATH"] }
/^--- / { next }
/^\+\+\+ / { next }
/^@@ / { h = $3; sub(/^\+/, "", h); split(h, a, ","); ln = a[1] + 0; next }
{
  c = substr($0, 1, 1); rest = substr($0, 2)
  if (c == "+") {
    if (rest ~ /pylint:[[:space:]]*disable/ \
        || rest ~ /(#|\/\/)[[:space:]]*noqa/ \
        || rest ~ /type:[[:space:]]*ignore/ \
        || rest ~ /@ts-(ignore|expect-error)/) {
      body = rest; sub(/^[[:space:]]+/, "", body)
      printf "{\"path\": \"%s\", \"line\": %d, \"text\": \"%s\"}\n", esc(path), ln, esc(body)
    }
    ln++
  } else if (c == " ") {
    ln++
  }
}
' <<<"$FILE_DIFF" >>"$FINDINGS"
done <"$NAMES"

if [[ ! -s "$FINDINGS" ]]; then
  printf '[]\n' >"${OUT_DIR}/disables.json"
else
  {
    printf '[\n'
    first=1
    while IFS= read -r finding; do
      if [[ "$first" -eq 1 ]]; then
        first=0
      else
        printf ',\n'
      fi
      printf '  %s' "$finding"
    done <"$FINDINGS"
    printf '\n]\n'
  } >"${OUT_DIR}/disables.json"
fi
