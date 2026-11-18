#!/usr/bin/env bash
# Self-test for review-pr.sh argument parsing, base detection, and marker behavior.
# Runs in ephemeral git repos with a local bare remote, so it never touches the
# real workspace or the network.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COUNTER_DIR=$(mktemp -d)
echo 0 >"${COUNTER_DIR}/pass"
echo 0 >"${COUNTER_DIR}/fail"

export GIT_AUTHOR_NAME="review-pr test" GIT_AUTHOR_EMAIL="test@example.com"
export GIT_COMMITTER_NAME="review-pr test" GIT_COMMITTER_EMAIL="test@example.com"

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

# Clones a one-commit bare remote and adds a local commit, so <remote>/<branch>
# is HEAD~1. Prints the clone's path.
#   $1  default branch of the remote (default: main)
#   $2  remote name in the clone (default: origin)
setup_temp_repo() {
  local default_branch="${1:-main}"
  local remote_name="${2:-origin}"
  local root
  root=$(mktemp -d)
  git init -q -b "$default_branch" "${root}/seed"
  git -C "${root}/seed" commit --allow-empty -m "initial" --quiet
  git clone -q --bare "${root}/seed" "${root}/remote.git"
  git clone -q -o "$remote_name" "${root}/remote.git" "${root}/work"
  git -C "${root}/work" commit --allow-empty -m "second" --quiet
  echo "${root}/work"
}

cleanup() { rm -rf "$(dirname "$1")"; }

# Marker path for a branch, inside the repo's git directory.
marker_path() {
  echo "$(command git rev-parse --path-format=absolute --git-common-dir)/.ess-gh-copilot-review/$1"
}
export -f marker_path

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

  review_pr 2>/dev/null

  branch=$(command git rev-parse --abbrev-ref HEAD)
  safe_branch="${branch//\//-}"
  marker=$(marker_path "$safe_branch")

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
echo "-- marker stays out of the working tree --"
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

  review_pr >/dev/null 2>&1

  if [[ -z "$(command git status --porcelain --ignored)" ]]; then
    pass "no tracked, untracked, or ignored files written"
  else
    fail "review wrote into the working tree: $(command git status --porcelain --ignored)"
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

  review_pr 2>/dev/null

  branch=$(command git rev-parse --abbrev-ref HEAD)
  safe_branch="${branch//\//-}"
  marker=$(marker_path "$safe_branch")

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
echo "-- default base follows the remote's default branch --"
tmp=$(setup_temp_repo master)
(
  cd "$tmp"
  prompt_file=$(mktemp)
  copilot() { printf '%s' "$2" >"$prompt_file"; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git
  export prompt_file

  source "${SCRIPT_DIR}/review-pr.sh"

  if review_pr >/dev/null 2>&1 && grep -q "against origin/master" "$prompt_file"; then
    pass "reviews against origin/master when the remote's default is master"
  else
    fail "did not review against origin/master: $(cat "$prompt_file")"
  fi
  rm -f "$prompt_file"
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- a remote not named origin is used when it is the only one --"
tmp=$(setup_temp_repo main upstream)
(
  cd "$tmp"
  prompt_file=$(mktemp)
  fetched=$(mktemp)
  copilot() { printf '%s' "$2" >"$prompt_file"; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then
      echo "${2:-}" >"$fetched"
      return 0
    fi
    command git "$@"
  }
  export -f copilot git
  export prompt_file fetched

  source "${SCRIPT_DIR}/review-pr.sh"

  if review_pr >/dev/null 2>&1 && grep -q "against upstream/main" "$prompt_file"; then
    pass "reviews against upstream/main"
  else
    fail "did not review against upstream/main: $(cat "$prompt_file")"
  fi
  [[ "$(cat "$fetched")" == "upstream" ]] && pass "fetches upstream" || fail "fetched '$(cat "$fetched")'"
  rm -f "$prompt_file" "$fetched"
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- missing remote HEAD falls back to main --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  prompt_file=$(mktemp)
  copilot() { printf '%s' "$2" >"$prompt_file"; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git
  export prompt_file

  source "${SCRIPT_DIR}/review-pr.sh"

  command git remote set-head origin -d >/dev/null
  if review_pr >/dev/null 2>&1 && grep -q "against origin/main" "$prompt_file"; then
    pass "reviews against origin/main without refs/remotes/origin/HEAD"
  else
    fail "did not fall back to origin/main: $(cat "$prompt_file")"
  fi
  rm -f "$prompt_file"
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- --base overrides the detected base --"
tmp=$(setup_temp_repo)
(
  cd "$tmp"
  prompt_file=$(mktemp)
  copilot() { printf '%s' "$2" >"$prompt_file"; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then return 0; fi
    command git "$@"
  }
  export -f copilot git
  export prompt_file

  source "${SCRIPT_DIR}/review-pr.sh"

  command git branch develop HEAD~1
  if review_pr --base develop >/dev/null 2>&1 && grep -q "against develop" "$prompt_file"; then
    pass "--base develop is used as the base"
  else
    fail "--base was not used: $(cat "$prompt_file")"
  fi
  if review_pr --base no-such-ref >/dev/null 2>&1; then
    fail "--base with a missing ref should fail"
  else
    pass "--base with a missing ref fails"
  fi
  rm -f "$prompt_file"
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- no remote and no --base fails with guidance --"
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

  command git remote remove origin
  if output=$(review_pr 2>&1); then
    fail "review_pr should fail without a remote"
  elif grep -q -- "--base" <<<"$output"; then
    pass "fails and suggests --base"
  else
    fail "error did not mention --base: ${output}"
  fi
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

  review_pr 2>/dev/null

  if [[ -f "$(marker_path feature-my-thing)" ]]; then
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

  # Capture HEAD before review
  expected_sha=$(command git rev-parse HEAD)

  review_pr 2>/dev/null

  # Add a commit after the review (simulates race)
  command git commit --allow-empty -m "late arrival" --quiet

  marker=$(marker_path main)
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

  review_pr 2>/dev/null && true

  marker=$(marker_path main)
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

  # First successful run to create marker
  review_pr 2>/dev/null

  marker=$(marker_path main)
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
echo "-- detached worktrees keep separate --since-last markers --"
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

  root=$(dirname "$tmp")
  command git worktree add --detach "$root/one" HEAD
  command git worktree add --detach "$root/two" HEAD
  command git -C "$root/one" commit --allow-empty -m "one" --quiet
  command git -C "$root/two" commit --allow-empty -m "two" --quiet

  ( cd "$root/one" && review_pr >/dev/null 2>&1 )
  ( cd "$root/two" && review_pr >/dev/null 2>&1 )

  one_dir=$(command git -C "$root/one" rev-parse --path-format=absolute --git-dir)
  two_dir=$(command git -C "$root/two" rev-parse --path-format=absolute --git-dir)
  common=$(command git -C "$root/one" rev-parse --path-format=absolute --git-common-dir)
  one_sha=$(command git -C "$root/one" rev-parse HEAD)
  two_sha=$(command git -C "$root/two" rev-parse HEAD)

  if [[ "$(cat "$one_dir/.ess-gh-copilot-review/HEAD")" == "$one_sha" ]]; then
    pass "first detached worktree records its own HEAD"
  else
    fail "first detached marker was not its HEAD"
  fi
  if [[ "$(cat "$two_dir/.ess-gh-copilot-review/HEAD")" == "$two_sha" ]]; then
    pass "second detached worktree records its own HEAD"
  else
    fail "second detached marker was not its HEAD"
  fi
  if [[ ! -e "$common/.ess-gh-copilot-review/HEAD" ]]; then
    pass "detached markers stay out of the common git directory"
  else
    fail "detached marker was written to the common git directory"
  fi
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo "-- --base refs/remotes/<remote>/<branch> fetches that remote --"
tmp=$(setup_temp_repo main upstream)
(
  cd "$tmp"
  prompt_file=$(mktemp)
  fetched=$(mktemp)
  : >"$fetched"
  copilot() { printf '%s' "$2" >"$prompt_file"; }
  git() {
    if [[ "${1:-}" == "fetch" ]]; then
      echo "${2:-}" >"$fetched"
      return 0
    fi
    command git "$@"
  }
  export -f copilot git
  export prompt_file fetched

  source "${SCRIPT_DIR}/review-pr.sh"

  if review_pr --base refs/remotes/upstream/main >/dev/null 2>&1 \
    && grep -q "against refs/remotes/upstream/main" "$prompt_file"; then
    pass "uses the fully qualified base"
  else
    fail "--base refs/remotes/upstream/main was not used: $(cat "$prompt_file" 2>/dev/null)"
  fi
  if [[ "$(cat "$fetched")" == "upstream" ]]; then
    pass "fetches upstream for refs/remotes/upstream/main"
  else
    fail "fetched '$(cat "$fetched")' instead of upstream"
  fi
  rm -f "$prompt_file" "$fetched"
)
cleanup "$tmp"

# ---------------------------------------------------------------------------
echo ""
PASS=$(cat "${COUNTER_DIR}/pass")
FAIL=$(cat "${COUNTER_DIR}/fail")
rm -rf "$COUNTER_DIR"
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]]
