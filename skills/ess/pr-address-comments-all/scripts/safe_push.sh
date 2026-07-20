#!/usr/bin/env bash
#
# safe_push.sh
# Push the current worktree HEAD to a PR branch WITHOUT ever hanging, even when
# the remote branch moved while a subagent was working. This prevents the known
# failure where a raw `git push` is rejected (non-fast-forward) and a follow-up
# interactive `git pull --rebase` stalls a non-interactive background subagent.
#
# Behaviour:
#   1) Force non-interactive git so no editor/pager/credential prompt can block.
#   2) Try `git push <remote> HEAD:<branch>` (works for attached or detached HEAD).
#   3) On rejection: fetch, then non-interactive `git rebase <remote>/<branch>`:
#        - clean rebase -> retry the push (bounded by --max-attempts)
#        - CONFLICT     -> `git rebase --abort` (leave NO rebase in progress) and
#                          exit 3 so the caller re-applies on the fresh base or
#                          escalates to the orchestrator. It never waits for input.
#
# Usage: safe_push.sh --branch B [--remote origin] [--max-attempts 3]
#
# Exit codes:
#   0  pushed successfully
#   2  bad usage / not in a git work tree / dirty worktree / pre-existing rebase|merge|cherry-pick|revert
#   3  remote moved with CONFLICTING changes -- re-apply on the updated base or
#      escalate (guaranteed no rebase left in progress)
#   4  push still rejected after --max-attempts (e.g. a flapping remote)
#   5  operational git failure (e.g. fetch failed)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

error() { echo -e "${RED}Error:${NC} $1" >&2; exit 2; }
op_error() { echo -e "${RED}Error:${NC} $1" >&2; exit 5; }
info() { echo -e "${GREEN}→${NC} $1" >&2; }
warn() { echo -e "${YELLOW}Warning:${NC} $1" >&2; }

BRANCH=""
REMOTE="origin"
MAX_ATTEMPTS=3

while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch) BRANCH="${2:-}"; shift 2 ;;
        --remote) REMOTE="${2:-}"; shift 2 ;;
        --max-attempts) MAX_ATTEMPTS="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

[[ -n "$BRANCH" ]] || error "Missing --branch B"
if ! [[ "$MAX_ATTEMPTS" =~ ^[0-9]+$ ]] || (( MAX_ATTEMPTS < 1 )); then
    error "--max-attempts must be an integer >= 1 (got: ${MAX_ATTEMPTS})"
fi
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || error "Not inside a git work tree"
if ! git diff-index --quiet HEAD --; then
    error "Working tree has uncommitted changes to tracked files -- commit or stash before pushing"
fi

# A background agent has no TTY: an editor, pager, or credential prompt would
# block forever. Force every git step to be non-interactive.
export GIT_EDITOR=true
export GIT_SEQUENCE_EDITOR=true
export GIT_PAGER=cat
export PAGER=cat
export GIT_TERMINAL_PROMPT=0

# Refuse to start on top of a half-finished rebase/merge/cherry-pick/revert -- that
# is exactly the stuck state this script exists to avoid creating.
_git_path() { git rev-parse --git-path "$1"; }
if [[ -d "$(_git_path rebase-merge)" || -d "$(_git_path rebase-apply)" \
   || -f "$(_git_path MERGE_HEAD)" || -f "$(_git_path CHERRY_PICK_HEAD)" \
   || -f "$(_git_path REVERT_HEAD)" ]]; then
    error "A rebase, merge, cherry-pick, or revert is already in progress -- finish or abort it before pushing"
fi

attempt=1
while (( attempt <= MAX_ATTEMPTS )); do
    info "Push attempt ${attempt}/${MAX_ATTEMPTS}: ${REMOTE} HEAD:${BRANCH}"
    if git push "$REMOTE" "HEAD:${BRANCH}"; then
        info "Pushed to ${REMOTE}/${BRANCH}"
        exit 0
    fi

    if (( attempt >= MAX_ATTEMPTS )); then
        echo "SAFE_PUSH_REJECTED: push still rejected after ${MAX_ATTEMPTS} attempts (remote may be flapping)." >&2
        exit 4
    fi

    warn "Push rejected -- ${REMOTE}/${BRANCH} likely moved; fetching and rebasing"
    git fetch "$REMOTE" -- "$BRANCH" || op_error "git fetch ${REMOTE} ${BRANCH} failed"

    if git rebase "${REMOTE}/${BRANCH}"; then
        info "Rebased cleanly onto ${REMOTE}/${BRANCH}; retrying push"
        attempt=$(( attempt + 1 ))
        continue
    fi

    # Conflict: abort so we never leave a half-finished rebase that hangs the agent.
    warn "Rebase hit conflicts; aborting to leave a clean tree"
    git rebase --abort || true
    echo "SAFE_PUSH_CONFLICT: ${REMOTE}/${BRANCH} moved with conflicting changes." >&2
    echo "Re-apply the approved fixes on the updated base, or escalate to the orchestrator to finish inline." >&2
    exit 3
done

echo "SAFE_PUSH_REJECTED: push still rejected after ${MAX_ATTEMPTS} attempts (remote may be flapping)." >&2
exit 4
