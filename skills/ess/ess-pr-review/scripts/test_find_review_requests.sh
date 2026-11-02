#!/usr/bin/env bash
#
# test_find_review_requests.sh
# Exercise find-review-requests.sh's --author filtering. Runs entirely offline:
# the PR list comes from a JSON fixture via PR_REVIEW_PR_FIXTURE and org team
# membership from a TSV fixture via PR_REVIEW_TEAM_FIXTURE, so no GitHub access
# (and no gh CLI) is needed.
#
# Usage: test_find_review_requests.sh [--keep]
#   --keep  - leave the fixture directory in place for inspection
#
# Exits non-zero if any assertion failed.

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
  local label="$1" needle="$2" haystack="$3"
  if printf '%s' "$haystack" | grep -qF -- "$needle"; then
    PASS=$((PASS + 1))
    echo "  ok   ${label}"
  else
    FAIL=$((FAIL + 1))
    echo "  FAIL ${label}: '${needle}' not found in output"
  fi
}

assert_not_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s' "$haystack" | grep -qF -- "$needle"; then
    FAIL=$((FAIL + 1))
    echo "  FAIL ${label}: '${needle}' unexpectedly found in output"
  else
    PASS=$((PASS + 1))
    echo "  ok   ${label}"
  fi
}

assert_fails() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    FAIL=$((FAIL + 1))
    echo "  FAIL ${label}: command unexpectedly succeeded"
  else
    PASS=$((PASS + 1))
    echo "  ok   ${label}"
  fi
}

# An empty result and a crash both produce no stdout, so any assertion expecting
# "" must also prove the run succeeded.
assert_ok() {
  local label="$1"; shift
  if run_raw "$@" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
    echo "  ok   ${label}"
  else
    FAIL=$((FAIL + 1))
    echo "  FAIL ${label}: expected exit 0, got $?"
  fi
}

# --- fixtures -----------------------------------------------------------------
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pr-review-find-test.XXXXXX")"
cleanup() {
  if [[ "$KEEP" == "true" ]]; then
    info "Fixtures kept at ${TMP_ROOT}"
  else
    rm -rf "$TMP_ROOT"
  fi
}
trap cleanup EXIT

PRS="${TMP_ROOT}/prs.json"
EMPTY_PRS="${TMP_ROOT}/empty-prs.json"
TEAMS="${TMP_ROOT}/teams.tsv"

# Shape mirrors `gh pr list --json number,headRefName,author,title,isDraft,commits`.
# PR 104 is a draft and must never appear. PR 105's commit author has an empty
# login and email, covering the blob builder's empty-field guard. PR 103's commit
# author name ("Caroline Chen") deliberately differs from its profile name
# ("Carol Chen"), so a term can only match it via the commit lookup.
cat > "$PRS" <<'JSON'
[
  { "number": 101, "headRefName": "feat-a", "isDraft": false,
    "title": "Add widget cache",
    "author": { "login": "alice", "name": "Alice Anderson" },
    "commits": [ { "authors": [
      { "login": "alice", "name": "Alice Anderson", "email": "alice@example.com" } ] } ] },

  { "number": 102, "headRefName": "feat-b", "isDraft": false,
    "title": "Fix pagination",
    "author": { "login": "bob_corp", "name": "Bob Brown" },
    "commits": [ { "authors": [
      { "login": "", "name": "Bob Brown", "email": "bob.brown@corp.example.com" } ] } ] },

  { "number": 103, "headRefName": "feat-c", "isDraft": false,
    "title": "Tidy imports",
    "author": { "login": "carol", "name": "Carol Chen" },
    "commits": [ { "authors": [
      { "login": "carol", "name": "Caroline Chen", "email": "carol@example.com" } ] } ] },

  { "number": 104, "headRefName": "feat-draft", "isDraft": true,
    "title": "WIP do not review",
    "author": { "login": "alice", "name": "Alice Anderson" },
    "commits": [ { "authors": [
      { "login": "alice", "name": "Alice Anderson", "email": "alice@example.com" } ] } ] },

  { "number": 105, "headRefName": "feat-e", "isDraft": false,
    "title": "Bump docs",
    "author": { "login": "dave", "name": "Dave Davis" },
    "commits": [ { "authors": [
      { "login": "", "name": "", "email": "" } ] } ] },

  { "number": 106, "headRefName": "feat-f", "isDraft": false,
    "title": "Rename helper",
    "author": { "login": "erin", "name": "" },
    "commits": [ { "authors": [
      { "login": "erin", "name": "Erin Evans", "email": "erin@example.com" } ] } ] }
]
JSON

# An empty review queue, for the "the query returned nothing" path.
printf '[]\n' > "$EMPTY_PRS"

# Columns: org/slug<TAB>login
{
  printf 'acme/reviewers\talice\n'
  printf 'acme/reviewers\tcarol\n'
  printf 'other/outsiders\tbob_corp\n'
  # A "login" that is only ever a fragment of a display name. Team members are
  # matched exactly, so this must select nothing.
  printf 'acme/fragment\tali\n'
  # Key present, login empty: a real team with no visible members. Distinct from
  # an absent key, which models a bad slug.
  printf 'acme/empty\t\n'
} > "$TEAMS"

# --- runner -------------------------------------------------------------------
# Returns the PR numbers on stdout, comma-joined, with stderr discarded.
run_filter() {
  local out
  out="$(PR_REVIEW_PR_FIXTURE="$PRS" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
    "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets "$@" 2>/dev/null)"
  printf '%s' "$out" | tr '\n' ',' | sed 's/,$//'
}

# Returns stderr only, for warning assertions.
run_stderr() {
  PR_REVIEW_PR_FIXTURE="$PRS" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
    "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets "$@" 2>&1 >/dev/null
}

run_raw() {
  PR_REVIEW_PR_FIXTURE="$PRS" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
    "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets "$@"
}

# Returns stderr only, with the commit-author lookup forced to fail for the given
# space-separated PR numbers. The run is expected to exit non-zero.
run_stderr_commit_fail() {
  local numbers="$1"; shift
  PR_REVIEW_PR_FIXTURE="$PRS" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
    PR_REVIEW_COMMIT_FAIL="$numbers" \
    "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets "$@" 2>&1 >/dev/null \
    || true
}

# Same as run_raw, for a caller-supplied PR fixture.
run_raw_with_prs() {
  local prs="$1"; shift
  PR_REVIEW_PR_FIXTURE="$prs" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
    "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets "$@"
}

echo
echo "No filter"
assert_eq "returns every non-draft PR" "101,102,103,105,106" "$(run_filter)"

echo
echo "Login terms"
assert_eq "exact login" "101" "$(run_filter --author alice)"
assert_eq "login is case-insensitive" "101" "$(run_filter --author ALICE)"
assert_eq "draft stays excluded when filtering" "101" "$(run_filter --author alice)"

echo
echo "Display-name terms"
assert_eq "full display name" "101" "$(run_filter --author 'Alice Anderson')"
assert_eq "first name only (substring)" "103" "$(run_filter --author Carol)"
assert_eq "name is case-insensitive" "103" "$(run_filter --author 'CAROL CHEN')"
assert_eq "profile display name" "102" "$(run_filter --author 'Bob Brown')"
# PR 106's author has no profile name, so this can only match via its commits.
assert_eq "falls back to commit author name" "106" "$(run_filter --author 'Erin Evans')"
# PR 103's author DOES have a profile name; its commit author name just differs
# from it, so the escalation must not be gated on an empty profile name.
assert_eq "commit author name differing from the profile name" "103" \
  "$(run_filter --author Caroline)"

echo
echo "Email terms"
assert_eq "commit author email" "102" "$(run_filter --author bob.brown@corp.example.com)"
assert_eq "email matches whole field only" "" "$(run_filter --author corp.example.com)"
assert_ok "partial email exits 0 rather than erroring" --author corp.example.com
# PR 105's commit author fields are all empty; escalating must not break.
assert_ok "empty commit-author fields survive escalation" --author nobody@example.com

echo
echo "Team terms"
assert_eq "org/slug expands to members" "101,103" \
  "$(run_filter --author @acme/reviewers)"
assert_eq "bare slug uses the repo's org" "101,103" \
  "$(run_filter --author @reviewers)"
assert_eq "team from another org" "102" "$(run_filter --author @other/outsiders)"
assert_eq "team members match logins exactly, not name fragments" "" \
  "$(run_filter --author @acme/fragment)"
assert_ok "a team matching nothing exits 0 rather than erroring" --author @acme/fragment
# A team that exists but has no visible members is an unmatched term, not a
# configuration error, so it warns and still exits 0.
assert_eq "an empty team yields no PRs" "" "$(run_filter --author @acme/empty)"
assert_ok "an empty team exits 0 rather than erroring" --author @acme/empty
assert_contains "an empty team warns" "has no visible members" \
  "$(run_stderr --author @acme/empty)"
assert_contains "an empty team still reports the unmatched term" "match '@acme/empty'" \
  "$(run_stderr --author @acme/empty)"

echo
echo "Multiple terms"
assert_eq "two logins union" "101,103" "$(run_filter --author alice --author carol)"
assert_eq "team plus a login unions" "101,102,103" \
  "$(run_filter --author @acme/reviewers --author bob_corp)"
assert_eq "overlapping terms do not duplicate a PR" "101" \
  "$(run_filter --author alice --author 'Alice Anderson')"
# 'alice' is settled by the list query; 'Caroline' can only be settled by PR 103's
# commit authors. An early match must not stop the later term from being resolved,
# or from being recorded as a hit.
assert_eq "a term matching only via commits still keeps its PR" "101,103" \
  "$(run_filter --author alice --author Caroline)"
assert_not_contains "a term matched only via commits does not warn" "match 'Caroline'" \
  "$(run_stderr --author alice --author Caroline)"

echo
echo "Unmatched and malformed terms"
assert_eq "unmatched term yields no PRs" "" "$(run_filter --author nobody)"
if run_raw --author nobody >/dev/null 2>&1; then
  PASS=$((PASS + 1)); echo "  ok   unmatched term still exits 0"
else
  FAIL=$((FAIL + 1)); echo "  FAIL unmatched term should exit 0"
fi
assert_contains "unmatched term warns" "match 'nobody'" "$(run_stderr --author nobody)"
assert_contains "filter reports how many were kept" "kept 1 of 5" \
  "$(run_stderr --author alice)"
assert_fails "unknown team exits non-zero" \
  env PR_REVIEW_PR_FIXTURE="$PRS" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
  "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets --author @acme/missing
assert_fails "--author with no value exits non-zero" \
  env PR_REVIEW_PR_FIXTURE="$PRS" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
  "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets --author
assert_contains "truncated queue warns" "raise --limit" \
  "$(run_stderr --limit 5 --author alice)"
# The fixture holds 6 rows, one of them a draft. The draft still consumed a
# --limit slot, so a limit of 6 is a truncated queue even though only 5 PRs are
# reviewable.
assert_contains "drafts count toward the limit" "raise --limit" \
  "$(run_stderr --limit 6 --author alice)"

echo
echo "Empty review queue"
assert_eq "empty queue yields no PRs" "" \
  "$(run_raw_with_prs "$EMPTY_PRS" --author nobody 2>/dev/null | tr '\n' ',' | sed 's/,$//')"
if run_raw_with_prs "$EMPTY_PRS" --author nobody >/dev/null 2>&1; then
  PASS=$((PASS + 1)); echo "  ok   empty queue exits 0"
else
  FAIL=$((FAIL + 1)); echo "  FAIL empty queue should exit 0"
fi
assert_contains "empty queue still warns about the unmatched term" "match 'nobody'" \
  "$(run_raw_with_prs "$EMPTY_PRS" --author nobody 2>&1 >/dev/null)"

echo
echo "Commit-lookup failures"
# A failed lookup must not be indistinguishable from "this PR does not match":
# it warns per PR, prints everything it does know, then exits non-zero.
COMMIT_FAIL_OUT="$(run_stderr_commit_fail 106 --author 'Erin Evans')"
assert_contains "a failed commit lookup warns for that PR" \
  "could not read commit authors for PR #106" "$COMMIT_FAIL_OUT"
assert_contains "a failed commit lookup reports incomplete results" \
  "results are incomplete" "$COMMIT_FAIL_OUT"
assert_contains "a failed commit lookup still prints the table" "feat-a" \
  "$(run_stderr_commit_fail 106 --author alice)"
assert_fails "a failed commit lookup exits non-zero" \
  env PR_REVIEW_PR_FIXTURE="$PRS" PR_REVIEW_TEAM_FIXTURE="$TEAMS" \
  PR_REVIEW_COMMIT_FAIL=106 \
  "${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets --author 'Erin Evans'

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo "All ${PASS} assertions passed."
  exit 0
fi
echo "${FAIL} of $((PASS + FAIL)) assertions failed."
exit 1
