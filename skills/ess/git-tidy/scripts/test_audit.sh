#!/usr/bin/env bash
#
# test_audit.sh
# Build a throwaway repo that exhibits every category audit.sh can assign, run
# the audit against it, and assert the classification. Runs entirely offline:
# the "remote" is a local bare repo and PR state comes from a fixture file via
# GIT_TIDY_PR_FIXTURE, so no GitHub access is needed.
#
# Usage: test_audit.sh [--keep]
#   --keep  - leave the scratch repo and report in place for inspection
#
# Exits non-zero on the first failed assertion.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${SCRIPT_DIR}/lib.sh"

KEEP="false"
[[ "${1:-}" == "--keep" ]] && KEEP="true"

PASS=0
FAIL=0

# --- assertions ---------------------------------------------------------------
assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    PASS=$((PASS + 1))
    echo "  ok   ${label}"
  else
    FAIL=$((FAIL + 1))
    echo "  FAIL ${label}: expected '${expected}', got '${actual}'"
  fi
}

assert_contains() {
  local label="$1" needle="$2" file="$3"
  if grep -qF -- "$needle" "$file"; then
    PASS=$((PASS + 1))
    echo "  ok   ${label}"
  else
    FAIL=$((FAIL + 1))
    echo "  FAIL ${label}: '${needle}' not found in $(basename "$file")"
  fi
}

assert_absent() {
  local label="$1" needle="$2" file="$3"
  if grep -qF -- "$needle" "$file"; then
    FAIL=$((FAIL + 1))
    echo "  FAIL ${label}: '${needle}' should not appear in $(basename "$file")"
  else
    PASS=$((PASS + 1))
    echo "  ok   ${label}"
  fi
}

# --- scratch repo -------------------------------------------------------------
# Resolve symlinks: on macOS mktemp hands back /var/... while git reports the
# real /private/var/..., and the assertions compare paths verbatim.
TMP_ROOT="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/git-tidy-test.XXXXXX")" && pwd -P)"
cleanup() {
  if [[ "$KEEP" == "true" ]]; then
    echo "Scratch repo kept at: ${TMP_ROOT}"
  else
    chmod -R u+w "$TMP_ROOT" 2>/dev/null || true
    rm -rf "$TMP_ROOT"
  fi
}
trap cleanup EXIT

ORIGIN="${TMP_ROOT}/origin.git"
WORK="${TMP_ROOT}/work"
OUT="${TMP_ROOT}/report"

# Isolate from the caller's git identity, hooks, signing, and templates.
export GIT_CONFIG_GLOBAL="${TMP_ROOT}/gitconfig"
export GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME="git-tidy test" GIT_AUTHOR_EMAIL="test@example.com"
export GIT_COMMITTER_NAME="git-tidy test" GIT_COMMITTER_EMAIL="test@example.com"
: > "$GIT_CONFIG_GLOBAL"

g() { git -C "$WORK" "$@"; }

commit() {
  echo "$1" >> "${WORK}/log.txt"
  g add -A
  g commit -q -m "$1"
}

info "Building scratch repo at ${TMP_ROOT}"

git init -q --bare "$ORIGIN"
git init -q "$WORK"
git -C "$WORK" symbolic-ref HEAD refs/heads/main
g remote add origin "$ORIGIN"

commit "c1"
commit "c2"
C2="$(g rev-parse HEAD)"
commit "c3"
C3="$(g rev-parse HEAD)"
g push -q origin main

# fresh-start: created off the base tip, nothing committed yet.
g branch fresh main

# merged-ancestor: sits at an older commit that main already contains.
g branch ancestor "$C2"
g branch 'ancestor;echo-pwned' "$C2"

# pr-merged-verified: one commit, squash-merged upstream, tip still matches.
g checkout -q -b squashed "$C3"
commit "squashed work"
SQUASHED_TIP="$(g rev-parse HEAD)"
g push -q origin squashed

# pr-merged-diverged: PR merged at the first commit, then a second was added.
g checkout -q -b diverged "$C3"
commit "diverged work"
DIVERGED_MERGED_AT="$(g rev-parse HEAD)"
commit "extra work after the merge"

# pr-open: one commit with a PR still open.
g checkout -q -b open-pr "$C3"
commit "open work"
OPEN_TIP="$(g rev-parse HEAD)"
g push -q origin open-pr

# unmerged-no-pr plus superseded: `sub` is an ancestor of `wip`.
g checkout -q -b wip "$C3"
commit "wip one"
WIP_ONE="$(g rev-parse HEAD)"
commit "wip two"
g branch sub "$WIP_ONE"

g checkout -q main

# --- worktrees ----------------------------------------------------------------
# stale-merged: clean worktree holding a branch already contained in main.
g worktree add -q "${TMP_ROOT}/wt-ancestor" ancestor

# dirty: uncommitted changes, must never be offered for removal.
g worktree add -q "${TMP_ROOT}/wt-dirty" wip
echo "scratch" > "${TMP_ROOT}/wt-dirty/uncommitted.txt"

# prunable: registration survives after the directory is deleted by hand.
g worktree add -q --detach "${TMP_ROOT}/wt-gone" "$C2"
rm -rf "${TMP_ROOT}/wt-gone"

# --- PR fixture ---------------------------------------------------------------
# Columns: headRefName, number, state, mergedAt, headRefOid, url
FIXTURE="${TMP_ROOT}/prs.tsv"
{
  printf 'squashed\t101\tMERGED\t2026-01-01T00:00:00Z\t%s\thttps://example.com/101\n' "$SQUASHED_TIP"
  printf 'diverged\t102\tMERGED\t2026-01-02T00:00:00Z\t%s\thttps://example.com/102\n' "$DIVERGED_MERGED_AT"
  printf 'open-pr\t103\tOPEN\t-\t%s\thttps://example.com/103\n' "$OPEN_TIP"
} > "$FIXTURE"

# --- run ----------------------------------------------------------------------
info "Running audit"
( cd "$WORK" && GIT_TIDY_PR_FIXTURE="$FIXTURE" \
  "${SCRIPT_DIR}/audit.sh" --output "$OUT" --no-size >/dev/null )

BRANCHES="${OUT}/branches.tsv"
WORKTREES="${OUT}/worktrees.tsv"
REPORT="${OUT}/report.md"

category_of() { awk -F'\t' -v b="$1" '$1 == b { print $3 }' "$BRANCHES"; }
disposition_of() { awk -F'\t' -v b="$1" '$1 == b { print $4 }' "$BRANCHES"; }
wt_category_of() { awk -F'\t' -v p="$1" '$1 == p { print $4 }' "$WORKTREES"; }
wt_disposition_of() { awk -F'\t' -v p="$1" '$1 == p { print $5 }' "$WORKTREES"; }

echo
echo "Branch classification"
assert_eq "main is the base"                "base"               "$(category_of main)"
assert_eq "fresh is fresh-start"            "fresh-start"        "$(category_of fresh)"
assert_eq "ancestor is merged-ancestor"     "merged-ancestor"    "$(category_of ancestor)"
assert_eq "squashed is pr-merged-verified"  "pr-merged-verified" "$(category_of squashed)"
assert_eq "diverged is pr-merged-diverged"  "pr-merged-diverged" "$(category_of diverged)"
assert_eq "open-pr is pr-open"              "pr-open"            "$(category_of open-pr)"
assert_eq "wip is unmerged-no-pr"           "unmerged-no-pr"     "$(category_of wip)"
assert_eq "sub is superseded"               "superseded"         "$(category_of sub)"

echo
echo "Branch dispositions"
assert_eq "fresh is never auto-deleted"     "ask"                "$(disposition_of fresh)"
assert_eq "ancestor deletes with -d"        "safe-d"             "$(disposition_of ancestor)"
assert_eq "squashed needs -D"               "safe-D"             "$(disposition_of squashed)"
assert_eq "diverged asks first"             "ask"                "$(disposition_of diverged)"
assert_eq "open-pr is kept"                 "keep"               "$(disposition_of open-pr)"
assert_eq "wip is kept"                     "keep"               "$(disposition_of wip)"
assert_eq "sub asks first"                  "ask"                "$(disposition_of sub)"

echo
echo "Branch tips"
assert_eq "branches.tsv keeps full tip SHA" "$C2" \
  "$(awk -F'\t' '$1 == "ancestor" { print $2 }' "$BRANCHES")"

echo
echo "Remote presence"
assert_eq "pushed branch reads live"        "live"   "$(awk -F'\t' '$1 == "squashed" { print $7 }' "$BRANCHES")"
assert_eq "local-only branch reads absent"  "absent" "$(awk -F'\t' '$1 == "wip" { print $7 }' "$BRANCHES")"

echo
echo "Worktree classification"
assert_eq "main tree is primary"       "primary"      "$(wt_category_of "$WORK")"
assert_eq "clean merged tree is stale" "stale-merged" "$(wt_category_of "${TMP_ROOT}/wt-ancestor")"
assert_eq "dirty tree is dirty"        "dirty"        "$(wt_category_of "${TMP_ROOT}/wt-dirty")"
assert_eq "deleted tree is prunable"   "prunable"     "$(wt_category_of "${TMP_ROOT}/wt-gone")"
assert_eq "dirty tree is kept"         "keep"         "$(wt_disposition_of "${TMP_ROOT}/wt-dirty")"

echo
echo "Remediation block"
assert_contains "prunable registration is pruned" "git worktree prune" "$REPORT"
assert_contains "squash merge uses -D"            "git branch -D -- squashed" "$REPORT"
assert_contains "ancestor uses -d"                "git branch -d -- ancestor" "$REPORT"
assert_contains "branch name is shell-escaped" \
  'git branch -d -- ancestor\;echo-pwned' "$REPORT"
assert_eq "each safe branch gets one delete command" "3" \
  "$(grep -cE '^git branch -[dD] -- ' "$REPORT")"
assert_absent   "fresh-start is not in a delete command" "branch -d fresh" "$REPORT"
# The dirty tree belongs in the inventory table; what it must never appear in
# is a removal command.
assert_absent   "dirty tree is never removed" \
  "git worktree remove \"${TMP_ROOT}/wt-dirty\"" "$REPORT"

# The worktree holding `ancestor` must be released before the branch delete,
# or `git branch -d` refuses.
WT_LINE="$(grep -n "git worktree remove" "$REPORT" | head -1 | cut -d: -f1 || echo 0)"
BR_LINE="$(grep -n "git branch -d -- ancestor" "$REPORT" | head -1 | cut -d: -f1 || echo 0)"
if [[ "$WT_LINE" -gt 0 && "$BR_LINE" -gt 0 && "$WT_LINE" -lt "$BR_LINE" ]]; then
  PASS=$((PASS + 1)); echo "  ok   worktree removal is ordered before branch deletion"
else
  FAIL=$((FAIL + 1)); echo "  FAIL worktree removal must precede branch deletion (${WT_LINE} vs ${BR_LINE})"
fi

echo
echo "Report artifacts"
for f in report.md report.json branches.tsv worktrees.tsv; do
  if [[ -s "${OUT}/${f}" ]]; then
    PASS=$((PASS + 1)); echo "  ok   ${f} is non-empty"
  else
    FAIL=$((FAIL + 1)); echo "  FAIL ${f} is missing or empty"
  fi
done
assert_contains "report.json keeps full tip SHA" "\"tip\": \"${C2}\"" "${OUT}/report.json"
if have python3; then
  if python3 -m json.tool "${OUT}/report.json" >/dev/null 2>&1; then
    PASS=$((PASS + 1)); echo "  ok   report.json parses"
  else
    FAIL=$((FAIL + 1)); echo "  FAIL report.json is not valid JSON"
  fi
fi

# The audit must not have mutated the repo it inspected.
BRANCH_COUNT="$(git -C "$WORK" for-each-ref --format='%(refname)' refs/heads | wc -l | tr -d ' ')"
assert_eq "audit deleted no branches" "9" "$BRANCH_COUNT"

echo
echo "Checkout remediation"
g branch 'base;evil' main
g checkout -q 'ancestor;echo-pwned'
CHECKOUT_OUT="${OUT}-checkout"
( cd "$WORK" && GIT_TIDY_PR_FIXTURE="$FIXTURE" \
  "${SCRIPT_DIR}/audit.sh" --base 'base;evil' --output "$CHECKOUT_OUT" --no-size >/dev/null )
assert_contains "checkout target is shell-escaped" \
  $'git checkout base\\;evil   # release the branch you are on' "${CHECKOUT_OUT}/report.md"
g checkout -q main
g branch -D 'base;evil' >/dev/null 2>&1 || true

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "All ${PASS} assertions passed."
  exit 0
fi
echo "${FAIL} of $((PASS + FAIL)) assertions failed."
exit 1
