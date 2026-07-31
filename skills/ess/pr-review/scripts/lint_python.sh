#!/usr/bin/env bash
#
# lint_python.sh <out_dir>
#
# Runs ruff, bandit, and a duplicate-code + perflint pylint pass over the changed
# Python files listed in <out_dir>/py_files.txt, writing machine-readable output:
#   ruff.json    - ruff check --output-format=json
#   bandit.json  - bandit -f json (security)
#   pylint.json  - pylint duplicate-code (R0801, re-enabled) + perflint
#
# Per-tool run status is appended to <out_dir>/tools.tsv as "tool<TAB>status".
# Each linter's config is auto-discovered from the repo. In a uv project the
# tools run via `uv run`; otherwise the bare executables are used. Portable to
# bash 3.2 (macOS): no mapfile / associative arrays.

set -uo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${_LIB_DIR}/lib.sh"

OUT_DIR="${1:?usage: lint_python.sh <out_dir>}"
STATUS_FILE="${OUT_DIR}/tools.tsv"

# Read the changed-file list into FILES (bash 3.2 compatible).
read_file_list "${OUT_DIR}/py_files.txt"

if [[ "${#FILES[@]}" -eq 0 ]]; then
  status ruff "not run (no python files)"
  status bandit "not run (no python files)"
  status pylint "not run (no python files)"
  exit 0
fi

# --- ruff ---------------------------------------------------------------------
RUFF="$(resolve_tool ruff)"
if [[ -n "$RUFF" ]]; then
  # shellcheck disable=SC2086
  $RUFF check --output-format=json --force-exclude -- "${FILES[@]}" > "${OUT_DIR}/ruff.json" 2>/dev/null || true
  if is_json_array "${OUT_DIR}/ruff.json"; then
    status ruff ok
  else
    echo "[]" > "${OUT_DIR}/ruff.json"; status ruff "ran (no parseable output)"
  fi
else
  status ruff "not run (tool unavailable)"
fi

# --- bandit -------------------------------------------------------------------
# Honor the repo's [tool.bandit] config (skips, test excludes) when present --
# bandit does not auto-discover pyproject.toml, so it must be passed explicitly.
BANDIT_CFG=()
REPO_ROOT="$(repo_root)"
if [[ -n "$REPO_ROOT" && -f "${REPO_ROOT}/pyproject.toml" ]] \
   && grep -q '^\[tool.bandit\]' "${REPO_ROOT}/pyproject.toml" 2>/dev/null; then
  BANDIT_CFG=(-c "${REPO_ROOT}/pyproject.toml")
fi
BANDIT="$(resolve_tool bandit)"
if [[ -n "$BANDIT" ]]; then
  # -ll: report medium+ severity only (drops B101 assert-in-test noise, keeps
  # real issues like B608 SQL injection). Explicit files bypass config excludes.
  # shellcheck disable=SC2086
  $BANDIT ${BANDIT_CFG[@]+"${BANDIT_CFG[@]}"} -ll -q -f json "${FILES[@]}" > "${OUT_DIR}/bandit.json" 2>/dev/null || true
  if [[ -s "${OUT_DIR}/bandit.json" ]] && [[ "$(head -c1 "${OUT_DIR}/bandit.json")" == "{" ]]; then
    status bandit ok
  else
    echo '{"results": []}' > "${OUT_DIR}/bandit.json"; status bandit "ran (no parseable output)"
  fi
else
  status bandit "not run (tool unavailable)"
fi

# --- pylint: duplicate-code (R0801) + perflint --------------------------------
# Root pyproject disables the C/R/W categories, so duplicate-code and the
# perflint W8xxx checks must be re-enabled explicitly here.
PYLINT="$(resolve_tool pylint)"
if [[ -n "$PYLINT" ]]; then
  PERF_ENABLE="duplicate-code,use-list-literal,use-dict-literal,use-tuple-over-list,use-set-for-membership,dotted-import-in-loop,use-fstring-for-concatenation,incorrect-dictionary-iterator,unnecessary-list-index-lookup"
  # shellcheck disable=SC2086
  $PYLINT --disable=all --enable="$PERF_ENABLE" --load-plugins=perflint \
    --output-format=json "${FILES[@]}" > "${OUT_DIR}/pylint.json" 2>/dev/null || true
  if ! is_json_array "${OUT_DIR}/pylint.json"; then
    # perflint plugin or a symbol was unavailable; fall back to duplicate-code only.
    # shellcheck disable=SC2086
    $PYLINT --disable=all --enable=duplicate-code \
      --output-format=json "${FILES[@]}" > "${OUT_DIR}/pylint.json" 2>/dev/null || true
  fi
  if is_json_array "${OUT_DIR}/pylint.json"; then
    status pylint ok
  else
    echo "[]" > "${OUT_DIR}/pylint.json"; status pylint "ran (no parseable output)"
  fi
else
  status pylint "not run (tool unavailable)"
fi
