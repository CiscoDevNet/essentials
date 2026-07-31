#!/usr/bin/env bash
#
# scan-pr.sh
# Run the repo's own linters over a PR diff and emit a compact, ranked report so
# the reviewer's attention goes to judgment, not to re-deriving lint findings.
#
# Usage:
#   scan-pr.sh <pr-ref> [--repo owner/repo] [--output DIR]
#   scan-pr.sh --base <ref> --head <ref> [--number N] [--repo owner/repo] [--output DIR]
#
#   <pr-ref>          - Full PR URL (https://github.com/<o>/<r>/pull/<N>) or a bare number.
#                       Fetches and pins the PR's actual head commit, so the current
#                       checkout does not matter and the local tree is never scanned.
#   --base / --head   - Explicit git refs to diff (default range: origin/main...HEAD)
#   --number N        - PR number for an explicit --base/--head range: names the
#                       output dir (...-<N>) and stamps the report with owner/repo#N.
#                       Batch reviews pass this so concurrent PRs never collide.
#   --repo owner/repo - Repo identity (a bare number, or an explicit range's slug)
#   --output DIR      - Output directory (default: /tmp/pr-review-<owner>-<repo>-<N>;
#                       an explicit range with no --number uses a short head hash)
#
# Writes into DIR (whatever the environment supports; missing tools => "not run"):
#   scan-meta.json  - base/head + changed-file counts + repo identity
#   tools.tsv       - per-tool run status (tool<TAB>status)
#   py_files.txt    - changed *.py paths (one per line)
#   ts_files.txt    - changed *.ts/*.tsx paths
#   ruff.json / pylint.json / bandit.json / eslint.json - raw linter output
#   disables.json   - suppression comments added by the diff
#   report.json / report.md - merged, ranked findings (read report.md)
#
# Portable to bash 3.2 (macOS): no associative arrays or mapfile. Depends only on
# git/gh plus whatever linters are installed, and on the repo's own
# auto-discovered linter config -- nothing outside this skill directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${SCRIPT_DIR}/lib.sh"

# --- parse args ---------------------------------------------------------------
PR_REF=""; BASE=""; HEAD=""; REPO_OVERRIDE=""; OUTPUT_DIR=""; NUMBER_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)   BASE="${2:-}"; shift 2 ;;
    --head)   HEAD="${2:-}"; shift 2 ;;
    --number) NUMBER_OVERRIDE="${2:-}"; shift 2 ;;
    --repo)   REPO_OVERRIDE="${2:-}"; shift 2 ;;
    --output) OUTPUT_DIR="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,33p' "$0"; exit 0 ;;
    -*) error "Unknown option: $1" ;;
    *)  if [[ -z "$PR_REF" ]]; then PR_REF="$1"; else error "Unexpected argument: $1"; fi; shift ;;
  esac
done

command -v git >/dev/null 2>&1 || error "git not found on PATH"
require_git_repo

OWNER=""; REPO=""; NUMBER=""

# --- resolve base/head + repo identity ---------------------------------------
if [[ -n "$PR_REF" ]]; then
  command -v gh >/dev/null 2>&1 || error "gh CLI required to resolve a PR ref"
  if [[ "$PR_REF" =~ ^https?://[^/]+/([^/]+)/([^/]+)/pull/([0-9]+) ]]; then
    OWNER="${BASH_REMATCH[1]}"; REPO="${BASH_REMATCH[2]}"; NUMBER="${BASH_REMATCH[3]}"
  elif [[ "$PR_REF" =~ ^[0-9]+$ ]]; then
    NUMBER="$PR_REF"
    if [[ -n "$REPO_OVERRIDE" ]]; then
      OWNER="${REPO_OVERRIDE%%/*}"; REPO="${REPO_OVERRIDE#*/}"
    else
      NWO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)" \
        || error "could not determine repo from remote; pass --repo owner/repo"
      OWNER="${NWO%%/*}"; REPO="${NWO#*/}"
    fi
  else
    error "could not parse PR reference: ${PR_REF} (expected a URL or a bare number)"
  fi
  PR_META="$(gh pr view "$NUMBER" --repo "${OWNER}/${REPO}" \
    --json baseRefName,headRefName,headRefOid --jq '[.baseRefName,.headRefName,.headRefOid]|@tsv')" \
    || error "gh pr view failed for ${OWNER}/${REPO}#${NUMBER}"
  BASE_REF="$(printf '%s' "$PR_META" | cut -f1)"
  HEAD_REF="$(printf '%s' "$PR_META" | cut -f2)"
  HEAD_OID="$(printf '%s' "$PR_META" | cut -f3)"
  info "fetching base ${BASE_REF}"
  # ``--`` separates the refspec from options so a branch name beginning with
  # ``-`` is never mistaken for a git flag.
  git fetch --quiet origin -- "$BASE_REF" || warn "could not fetch origin/${BASE_REF}"
  BASE="origin/${BASE_REF}"
  # Pin to the PR's actual head commit -- never the local working tree. This is
  # what stops a scan run from the wrong checkout from silently diffing the
  # local branch instead of the real PR. ``pull/<N>/head`` resolves the head of
  # the same-origin PRs this skill supports; fall back to the head branch name
  # if the pull ref is missing.
  info "fetching PR #${NUMBER} head ${HEAD_OID:0:8} (${HEAD_REF})"
  git fetch --quiet origin -- "pull/${NUMBER}/head" \
    || git fetch --quiet origin -- "$HEAD_REF" \
    || warn "could not fetch PR head for #${NUMBER}"
  # Verify guard: the exact PR head commit must be present locally after the
  # fetch, or we refuse to scan rather than fall back to the local tree.
  git cat-file -e "${HEAD_OID}^{commit}" 2>/dev/null \
    || error "PR #${NUMBER} head ${HEAD_OID} not available after fetch; refusing to scan the local tree"
  HEAD="$HEAD_OID"
else
  # Explicit --base/--head range. --repo makes the output slug and report
  # identity deterministic (batch reviews pass it); otherwise fall back to the
  # current remote. --number labels this range as a specific PR.
  if [[ -n "$REPO_OVERRIDE" ]]; then
    OWNER="${REPO_OVERRIDE%%/*}"; REPO="${REPO_OVERRIDE#*/}"
  elif [[ -z "$OWNER" ]] && command -v gh >/dev/null 2>&1; then
    NWO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
    if [[ -n "$NWO" ]]; then OWNER="${NWO%%/*}"; REPO="${NWO#*/}"; fi
  fi
  NUMBER="$NUMBER_OVERRIDE"
  BASE="${BASE:-origin/main}"
  HEAD="${HEAD:-HEAD}"
fi

# --- output dir ---------------------------------------------------------------
# The suffix must be unique per PR so concurrent/batch scans never share (and
# thus clobber) a directory. A PR number is best; for a bare --base/--head range
# fall back to the head SHA (or a hash of the range) instead of a literal that
# every range would collide on.
if [[ -z "$OUTPUT_DIR" ]]; then
  SAFE_OWNER="${OWNER//\//-}"; SAFE_REPO="${REPO//\//-}"
  if [[ -n "$NUMBER" ]]; then
    SUFFIX="$NUMBER"
  elif [[ "$HEAD" =~ ^[0-9a-f]{7,40}$ ]]; then
    SUFFIX="${HEAD:0:8}"
  else
    SUFFIX="$(hash_str "${BASE}...${HEAD}")"
  fi
  OUTPUT_DIR="/tmp/pr-review-${SAFE_OWNER:-local}-${SAFE_REPO:-repo}-${SUFFIX}"
fi
# Guard against a mistyped --output (e.g. /, ., .., $HOME) wiping unintended
# files before the rm -rf below.
case "$OUTPUT_DIR" in
  ""|/|.|..|"$HOME") error "refusing to remove unsafe output dir: '${OUTPUT_DIR}'" ;;
  */) error "output dir must not end with '/': '${OUTPUT_DIR}'" ;;
esac
rm -rf "$OUTPUT_DIR"; mkdir -p "$OUTPUT_DIR"
: > "${OUTPUT_DIR}/tools.tsv"
info "diff range: ${BASE}...${HEAD}"
info "output dir: ${OUTPUT_DIR}"

# --- changed files ------------------------------------------------------------
git diff --name-only --diff-filter=ACMR "${BASE}...${HEAD}" 2>/dev/null > "${OUTPUT_DIR}/changed.txt" \
  || error "git diff failed for range ${BASE}...${HEAD}"
grep -E '\.py$'       "${OUTPUT_DIR}/changed.txt" > "${OUTPUT_DIR}/py_files.txt" || true
grep -E '\.(ts|tsx)$' "${OUTPUT_DIR}/changed.txt" > "${OUTPUT_DIR}/ts_files.txt" || true
PY_COUNT="$(wc -l < "${OUTPUT_DIR}/py_files.txt" | tr -d ' ')"
TS_COUNT="$(wc -l < "${OUTPUT_DIR}/ts_files.txt" | tr -d ' ')"
info "changed files: ${PY_COUNT} python, ${TS_COUNT} typescript"

# --- run the linters (each sub-script appends its own status to tools.tsv) -----
if [[ "$PY_COUNT" -gt 0 ]]; then
  bash "${SCRIPT_DIR}/lint_python.sh" "$OUTPUT_DIR" || warn "python lint step failed"
else
  printf 'ruff\tnot run (no python files)\n'   >> "${OUTPUT_DIR}/tools.tsv"
  printf 'pylint\tnot run (no python files)\n' >> "${OUTPUT_DIR}/tools.tsv"
  printf 'bandit\tnot run (no python files)\n' >> "${OUTPUT_DIR}/tools.tsv"
fi

if [[ "$TS_COUNT" -gt 0 ]]; then
  bash "${SCRIPT_DIR}/lint_ts.sh" "$OUTPUT_DIR" || warn "typescript lint step failed"
else
  printf 'eslint\tnot run (no typescript files)\n' >> "${OUTPUT_DIR}/tools.tsv"
fi

# --- suppression comments added by the diff -----------------------------------
bash "${SCRIPT_DIR}/scan_disables.sh" "$OUTPUT_DIR" "$BASE" "$HEAD" || warn "disable scan failed"

# --- scan-meta.json -----------------------------------------------------------
{
  printf '{\n'
  printf '  "owner": "%s",\n' "$OWNER"
  printf '  "repo": "%s",\n' "$REPO"
  printf '  "number": "%s",\n' "$NUMBER"
  printf '  "base": "%s",\n' "$BASE"
  printf '  "head": "%s",\n' "$HEAD"
  printf '  "python_files": %s,\n' "$PY_COUNT"
  printf '  "typescript_files": %s\n' "$TS_COUNT"
  printf '}\n'
} > "${OUTPUT_DIR}/scan-meta.json"

# --- merge + rank -------------------------------------------------------------
PYRUN="$(py_runner)"
[[ -n "$PYRUN" ]] || error "no python interpreter found to build the report"
# report.py relativizes eslint's absolute paths against its cwd, so run it from
# the SCANNED repo's root -- otherwise invoking scan-pr.sh from a subdirectory
# leaks absolute paths into the report. repo_root() resolves the cwd's repo (the
# tree being scanned), not the skill's. Pass an absolute OUTPUT_DIR since we cd.
REPO_ROOT="$(repo_root)"
OUTPUT_DIR_ABS="$(cd "$OUTPUT_DIR" && pwd)"
# shellcheck disable=SC2086
( cd "$REPO_ROOT" && $PYRUN "${SCRIPT_DIR}/report.py" --input-dir "$OUTPUT_DIR_ABS" ) \
  || error "report.py failed"

info "report ready: ${OUTPUT_DIR}/report.md"
echo "${OUTPUT_DIR}/report.md"
