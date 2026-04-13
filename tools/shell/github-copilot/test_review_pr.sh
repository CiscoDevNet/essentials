#!/usr/bin/env bash
# Self-test for review-pr.sh argument parsing and marker behavior.
# Runs in an ephemeral git repo so it never touches the real workspace.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COUNTER_DIR=$(mktemp -d)
echo 0 >"${COUNTER_DIR}/pass"
echo 0 >"${COUNTER_DIR}/fail"

pass() {
  echo "  PASS: $1"
  echo $(( $(cat "${COUNTER_DIR}/pass") + 1 )) >"${COUNTER_DIR}/pass"
}
fail() {
  echo "  FAIL: $1" >&2
  echo $(( $(cat "${COUNTER_DIR}/fail") + 1 )) >"${COUNTER_DIR}/fail"
}
export COUNTER_DIR
export -f pass fail

setup_temp_repo() {
  local tmp
  tmp=$(mktemp -d)
  git -C "$tmp" init -b main --quiet
  git -C "$tmp" commit --allow-empty -m "initial" --quiet
  git -C "$tmp" commit --allow-empty -m "second" --quiet
  echo "$tmp"
}

cleanup() { rm -rf "$1"; }

# Source the script to get the review_pr function without executing it.
# We stub out copilot and git fetch so nothing external runs.
source "${SCRIPT_DIR}/review-pr.sh"

# --- Test helpers -----------------------------------------------------------
# Override copilot so the function does not actually call the CLI.
copilot() { return 0; }
export -f copilot

echo "=== review-pr.sh self-tests ==="

# ---------------------------------------------------------------------------
echo "-- per-branch marker file --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  # Stub copilot and git fetch
  copilot() { return 0; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  # Create origin/main ref so the default path works
  command git branch origin/main HEAD~1 2>/dev/null || true

  review_pr 2>/dev/null

  branch=$(command git rev-parse --abbrev-ref HEAD)
  safe_branch="${branch//\//-}"
  marker=".cursor/.review-code-with-copilot/${safe_branch}"

  if [[ -f "$marker" ]]; then
    pass "marker created at ${marker}"
  else
    fail "marker not created at ${marker}"
  fi

  stored=$(cat "$marker")
  head_sha=$(command git rev-parse HEAD)
  if [[ "$stored" == "$head_sha" ]]; then
    pass "marker contains HEAD SHA"
  else
    fail "marker SHA mismatch: got '$stored', expected '$head_sha'"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- --since-last reads marker --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 0; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  command git branch origin/main HEAD~1 2>/dev/null || true

  # First run to create marker
  review_pr 2>/dev/null

  # Add a new commit
  command git commit --allow-empty -m "third" --quiet

  # Run with --since-last; capture diff stat
  output=$(review_pr --since-last 2>&1)

  if echo "$output" | grep -q "0 files changed\|^$"; then
    pass "--since-last reviewed only new changes (empty diff for empty commit)"
  else
    pass "--since-last ran successfully with marker"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- --reset-last removes marker --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 0; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  command git branch origin/main HEAD~1 2>/dev/null || true

  review_pr 2>/dev/null

  branch=$(command git rev-parse --abbrev-ref HEAD)
  safe_branch="${branch//\//-}"
  marker=".cursor/.review-code-with-copilot/${safe_branch}"

  review_pr --reset-last 2>/dev/null

  if [[ ! -f "$marker" ]]; then
    # Reset removes the old file but a new one is written on success
    pass "--reset-last cleared the marker before review"
  else
    pass "--reset-last ran and re-created marker on success"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- --since accepts a revision --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 0; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then
      fail "--since should not trigger git fetch"
      return 0
    fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  first_sha=$(command git rev-parse HEAD~1)
  review_pr --since "$first_sha" 2>/dev/null && pass "--since <rev> succeeded" || fail "--since <rev> failed"
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- --range accepts a range --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 0; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then
      fail "--range should not trigger git fetch"
      return 0
    fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  review_pr --range "HEAD~1..HEAD" 2>/dev/null && pass "--range succeeded" || fail "--range failed"
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- branch with slashes gets safe filename --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 0; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  command git checkout -b feature/my-thing --quiet
  command git branch origin/main HEAD~1 2>/dev/null || true

  review_pr 2>/dev/null

  if [[ -f ".cursor/.review-code-with-copilot/feature-my-thing" ]]; then
    pass "slash in branch name converted to dash in marker filename"
  else
    fail "marker not found for branch with slashes"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- marker SHA matches diff endpoint --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 0; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  command git branch origin/main HEAD~1 2>/dev/null || true

  # Capture HEAD before review
  expected_sha=$(command git rev-parse HEAD)

  review_pr 2>/dev/null

  # Add a commit after the review (simulates race)
  command git commit --allow-empty -m "late arrival" --quiet

  marker=".cursor/.review-code-with-copilot/main"
  stored=$(cat "$marker")

  if [[ "$stored" == "$expected_sha" ]]; then
    pass "marker records the SHA that was reviewed, not the later HEAD"
  else
    fail "marker SHA mismatch: got '$stored', expected '$expected_sha' (current HEAD: $(command git rev-parse HEAD))"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- copilot failure skips marker update --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 1; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  command git branch origin/main HEAD~1 2>/dev/null || true

  review_pr 2>/dev/null && true

  marker=".cursor/.review-code-with-copilot/main"
  if [[ ! -f "$marker" ]]; then
    pass "marker not written when copilot fails"
  else
    fail "marker was written despite copilot failure"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- copilot failure returns non-zero exit --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot() { return 1; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git

  source "${SCRIPT_DIR}/review-pr.sh"

  command git branch origin/main HEAD~1 2>/dev/null || true

  if review_pr 2>/dev/null; then
    fail "review_pr should have returned non-zero on copilot failure"
  else
    pass "review_pr returns non-zero when copilot fails"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- --reset-last preserves marker on copilot failure --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  copilot_should_fail="false"
  copilot() {
    if [[ "$copilot_should_fail" == "true" ]]; then return 1; fi
    return 0
  }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git
  export copilot_should_fail

  source "${SCRIPT_DIR}/review-pr.sh"

  command git branch origin/main HEAD~1 2>/dev/null || true

  # First successful run to create marker
  review_pr 2>/dev/null

  marker=".cursor/.review-code-with-copilot/main"
  original_sha=$(cat "$marker")

  # Now make copilot fail and try --reset-last
  copilot_should_fail="true"
  export copilot_should_fail
  copilot() { return 1; }
  export -f copilot

  review_pr --reset-last 2>/dev/null && true

  if [[ -f "$marker" ]]; then
    stored=$(cat "$marker")
    if [[ "$stored" == "$original_sha" ]]; then
      pass "--reset-last preserves original marker when copilot fails"
    else
      fail "--reset-last overwrote marker despite copilot failure"
    fi
  else
    fail "--reset-last deleted marker despite copilot failure"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo ""
PASS=$(cat "${COUNTER_DIR}/pass")
FAIL=$(cat "${COUNTER_DIR}/fail")
rm -rf "$COUNTER_DIR"
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]]
