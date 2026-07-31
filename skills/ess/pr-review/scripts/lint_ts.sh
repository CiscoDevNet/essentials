#!/usr/bin/env bash
#
# lint_ts.sh <out_dir>
#
# Best-effort ESLint pass (with eslint-plugin-sonarjs when the repo config
# enables it) over the changed TypeScript files listed in <out_dir>/ts_files.txt.
#
# ESLint flat config is resolved from the working directory, so each app must be
# linted from the directory that holds its `eslint.config.*`. Changed files are
# therefore grouped by their nearest ancestor *config* dir, and eslint is run
# once per group from that dir. The eslint *binary* is resolved separately:
# in an npm-workspaces monorepo apps often have no local eslint, but the shared
# config's plugins (e.g. eslint-plugin-sonarjs) plus the eslint binary are
# hoisted to the *root* node_modules -- so the root binary is used, invoked from
# the app dir, which is exactly what lets the app's config resolve its plugins.
#
# A one-time `npm install` at the repo root is required to populate that hoisted
# node_modules. Output is one <out_dir>/eslint-<n>.json part per group (report.py
# merges the parts). If eslint cannot be resolved or run, the status records an
# actionable hint and the scan continues. Portable to bash 3.2 (macOS): no
# mapfile / associative arrays.

set -uo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${_LIB_DIR}/lib.sh"

OUT_DIR="${1:?usage: lint_ts.sh <out_dir>}"
STATUS_FILE="${OUT_DIR}/tools.tsv"

ROOT="$(repo_root)"

read_file_list "${OUT_DIR}/ts_files.txt"

if [[ "${#FILES[@]}" -eq 0 ]]; then
  echo "[]" > "${OUT_DIR}/eslint.json"
  status eslint "not run (no typescript files)"
  exit 0
fi

# Nearest ancestor dir (of the given file) that holds an eslint config; the run
# dir for flat config. Echoes a repo-relative dir, or returns non-zero if none.
find_config_dir() {
  local dir; dir="$(dirname "$1")"
  while :; do
    for cfg in eslint.config.mjs eslint.config.js eslint.config.cjs \
               eslint.config.ts .eslintrc.js .eslintrc.cjs .eslintrc.json \
               .eslintrc.yml .eslintrc.yaml; do
      [[ -f "${ROOT}/${dir}/${cfg}" ]] && { echo "$dir"; return 0; }
    done
    [[ "$dir" == "." || "$dir" == "/" ]] && break
    dir="$(dirname "$dir")"
  done
  return 1
}

# Resolve an eslint binary runnable from the config dir: the dir's own or any
# ancestor's (incl. the hoisted root) node_modules/.bin/eslint (absolute path),
# else "npx". Returns non-zero when nothing is available.
resolve_eslint_bin() {
  local dir; dir="${ROOT}/${1}"
  while [[ "$dir" != "/" ]]; do
    [[ -x "$dir/node_modules/.bin/eslint" ]] && { echo "$dir/node_modules/.bin/eslint"; return 0; }
    dir="$(dirname "$dir")"
  done
  # Only fall back to npx if eslint actually resolves there without a network
  # install; probe from the config dir so it matches the real run below. Blind
  # npx yields no JSON and a misleading "config error" when the fix is `npm
  # install` at the repo root -- returning non-zero routes to that message.
  if command -v npx >/dev/null 2>&1 \
     && ( cd "${ROOT}/${1}" && npx --no-install eslint --version >/dev/null 2>&1 ); then
    echo "npx"; return 0
  fi
  return 1
}

# Map each file to its config dir (or NONE) in a flat TSV -- no assoc arrays.
# NB: do not name this var GROUPS -- that is a read-only special bash variable
# (the user's group IDs); assignments to it are silently ignored.
GROUP_MAP="${OUT_DIR}/eslint-groups.tsv"
: > "$GROUP_MAP"
for f in "${FILES[@]}"; do
  if dir="$(find_config_dir "$f")"; then
    printf '%s\t%s\n' "$dir" "$f" >> "$GROUP_MAP"
  else
    printf 'NONE\t%s\n' "$f" >> "$GROUP_MAP"
  fi
done

RAN=0
ATTEMPTED=0
FAILED=0
INDEX=0
MISSING_BIN=0

# One eslint run per config dir, from that dir, with file paths relative to it.
for dir in $(cut -f1 "$GROUP_MAP" | sort -u); do
  [[ "$dir" == "NONE" ]] && continue
  BIN="$(resolve_eslint_bin "$dir")" || { MISSING_BIN=1; continue; }
  RELS=()
  while IFS=$'\t' read -r gdir gfile; do
    [[ "$gdir" == "$dir" ]] || continue
    RELS+=("${gfile#"$dir"/}")
  done < "$GROUP_MAP"
  INDEX=$((INDEX + 1))
  ATTEMPTED=$((ATTEMPTED + 1))
  PART="${OUT_DIR}/eslint-${INDEX}.json"
  if [[ "$BIN" == "npx" ]]; then
    ( cd "${ROOT}/${dir}" && npx --no-install eslint -f json "${RELS[@]}" ) > "$PART" 2>/dev/null || true
  else
    ( cd "${ROOT}/${dir}" && "$BIN" -f json "${RELS[@]}" ) > "$PART" 2>/dev/null || true
  fi
  # A run that produced no JSON array (crash, config error) is a failure, not a
  # skip: count it so the status below never mislabels it as "not run".
  if is_json_array "$PART"; then RAN=1; else echo "[]" > "$PART"; FAILED=$((FAILED + 1)); fi
done

# Ensure report.py finds at least one (empty) part even when nothing ran.
[[ "$INDEX" -gt 0 ]] || [[ -f "${OUT_DIR}/eslint.json" ]] || echo "[]" > "${OUT_DIR}/eslint.json"

if [[ "$ATTEMPTED" -eq 0 ]]; then
  if [[ "$MISSING_BIN" -eq 1 ]]; then
    status eslint "not run (eslint deps missing — run 'npm install' at repo root)"
  else
    status eslint "not run (no eslint config found for changed files)"
  fi
elif [[ "$FAILED" -eq 0 ]]; then
  status eslint ok
elif [[ "$RAN" -eq 1 ]]; then
  status eslint "partial (${FAILED} of ${ATTEMPTED} eslint runs produced no JSON — likely a config error)"
else
  status eslint "error (eslint ran but produced no JSON for ${ATTEMPTED} group(s) — check eslint config)"
fi
