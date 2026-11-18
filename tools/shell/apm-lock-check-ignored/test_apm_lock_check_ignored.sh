#!/usr/bin/env bash
# Self-test for apm-lock-check-ignored.sh: a lock that records a git-ignored
# deployed or source file fails, and a clean lock passes.
# Runs in an ephemeral git repo with a hand-written lock.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=0
FAIL=0

pass() {
  echo "  PASS: $1"
  PASS=$((PASS + 1))
}
fail() {
  echo "  FAIL: $1" >&2
  FAIL=$((FAIL + 1))
}

# shellcheck source=apm-lock-check-ignored.sh
source "${SCRIPT_DIR}/apm-lock-check-ignored.sh"

TMP_REPO=$(mktemp -d)
ERR="${TMP_REPO}/err.txt"
git -C "$TMP_REPO" init -b main --quiet
trap 'rm -rf "$TMP_REPO"' EXIT

# Runs apm_lock_check_ignored on the repo's lock and reports its exit code.
run() {
  local status=0
  apm_lock_check_ignored "${TMP_REPO}/apm.lock.yaml" >/dev/null 2>"$ERR" || status=$?
  echo "$status"
}

# Writes a lock with one local dependency, "demo", deploying the given files
# relative to the skill directory.
write_lock() {
  {
    printf 'lockfile_version: %s\n' "'1'"
    printf 'dependencies:\n'
    printf -- '- repo_url: _local/demo\n'
    printf '  name: demo\n'
    printf '  deployed_files:\n'
    printf '  - .agents/skills/demo\n'
    local file
    for file in "$@"; do
      printf '  - .agents/skills/demo/%s\n' "$file"
    done
    printf '  source: local\n'
    printf '  local_path: ./skills/demo\n'
    printf 'deployments:\n'
    printf '  owners:\n'
    printf '  - ./skills/demo\n'
  } >"${TMP_REPO}/apm.lock.yaml"
}

# Writes a lock where "demo" is a transitive dependency of "parent", recorded
# the way APM does: local_path relative to the parent, anchored to the root.
write_transitive_lock() {
  {
    printf 'lockfile_version: %s\n' "'1'"
    printf 'dependencies:\n'
    printf -- '- repo_url: _local/demo\n'
    printf '  name: demo\n'
    printf '  depth: 2\n'
    printf '  deployed_files:\n'
    printf '  - .agents/skills/demo\n'
    local file
    for file in "$@"; do
      printf '  - .agents/skills/demo/%s\n' "$file"
    done
    printf '  source: local\n'
    printf '  local_path: ../demo\n'
    printf '  declaring_parent: ./skills/parent\n'
    printf '  anchored_local_path: skills/demo\n'
    printf 'deployments:\n'
  } >"${TMP_REPO}/apm.lock.yaml"
  return 0
}

printf 'tmp-*\n' >"${TMP_REPO}/.gitignore"
mkdir -p "${TMP_REPO}/skills/demo/input"
printf '*\n!.gitignore\n' >"${TMP_REPO}/skills/demo/input/.gitignore"

echo "=== apm-lock-check-ignored.sh self-tests ==="

echo "-- a lock with no ignored files passes --"
write_lock SKILL.md scripts/run.sh
status=$(run)
[[ "$status" == 0 ]] && pass "exits 0" || fail "exited ${status}"

echo "-- an ignored deployed file fails and is named --"
write_lock SKILL.md tmp-notes.md
status=$(run)
[[ "$status" == 1 ]] && pass "exits 1" || fail "exited ${status}"
grep -q '\.agents/skills/demo/tmp-notes\.md' "$ERR" && pass "names the file" || fail "file not named"

echo "-- a file ignored only at its source fails --"
write_lock SKILL.md input/goals.md
status=$(run)
[[ "$status" == 1 ]] && pass "exits 1" || fail "exited ${status}"
grep -q 'skills/demo/input/goals\.md' "$ERR" && pass "names the source" || fail "source not named"

echo "-- a transitive dependency is checked at its anchored source --"
write_transitive_lock SKILL.md
status=$(run)
[[ "$status" == 0 ]] && pass "clean lock exits 0" || fail "exited ${status}: $(cat "$ERR")"
write_transitive_lock SKILL.md input/goals.md
status=$(run)
[[ "$status" == 1 ]] && pass "ignored source exits 1" || fail "exited ${status}"
grep -q '^  skills/demo/input/goals\.md' "$ERR" && pass "names the anchored source" || fail "source not named"

echo "-- a tracked file that matches an ignore pattern passes --"
mkdir -p "${TMP_REPO}/.agents/skills/demo"
printf 'kept\n' >"${TMP_REPO}/.agents/skills/demo/tmp-kept.md"
printf 'kept\n' >"${TMP_REPO}/skills/demo/tmp-kept.md"
git -C "$TMP_REPO" add -f .agents/skills/demo/tmp-kept.md skills/demo/tmp-kept.md
write_lock SKILL.md tmp-kept.md
status=$(run)
[[ "$status" == 0 ]] && pass "exits 0" || fail "exited ${status}"

echo "-- an untracked file re-included by a negation passes --"
mkdir -p "${TMP_REPO}/skills/demo"
printf '*.example\n!.env.example\n' >"${TMP_REPO}/skills/demo/.gitignore"
printf 'example\n' >"${TMP_REPO}/skills/demo/.env.example"
write_lock SKILL.md .env.example
status=$(run)
[[ "$status" == 0 ]] && pass "exits 0" || fail "exited ${status}: $(cat "$ERR")"

echo "-- a missing lock exits 2 --"
rm "${TMP_REPO}/apm.lock.yaml"
status=$(run)
[[ "$status" == 2 ]] && pass "exits 2" || fail "exited ${status}"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]]
