#!/usr/bin/env bash
#
# create_review_worktree.sh
# Create a READ-ONLY git worktree checked out at a PR's head commit, so each PR
# in an N>1 review can be scanned in isolation without touching the main tree.
#
# Review is read-only: this uses `git worktree add --detach <headSha>` (NOT
# `-B <branch>`), so there is no local branch to accidentally commit or push to.
# Contrast with pr-address-comments-all/scripts/create_pr_worktree.sh, which
# needs a real branch because it writes back to the PR.
#
# The on-disk layout matches the /worktree command
# (~/.cursor/worktrees/<WORKTREE_ID>/<repo-key>) so /delete-worktree still works.
#
# Usage: create_review_worktree.sh --pr N --repo owner/repo
#   --pr N            - PR number (used to name the worktree)
#   --repo owner/repo - Repo the PR lives in
#
# Run from inside the target repo. Prints WORKTREE_ID, WORKTREE_PATH, HEAD_SHA.

set -euo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${_LIB_DIR}/lib.sh"

PR_NUMBER=""
OWNER_REPO=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pr) PR_NUMBER="${2:-}"; shift 2 ;;
        --repo) OWNER_REPO="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

[[ -n "$PR_NUMBER" ]] || error "Missing --pr N"
[[ -n "$OWNER_REPO" ]] || error "Missing --repo owner/repo"
command -v gh >/dev/null 2>&1 || error "gh CLI not found on PATH"
command -v openssl >/dev/null 2>&1 || error "openssl not found on PATH"

require_git_repo
REPO_ROOT="$(repo_root)"

# Resolve the PR's head branch and exact head commit. We check out the SHA
# (detached) rather than the branch tip so the review is pinned to what the PR
# is at now, even if it moves mid-run.
read -r BRANCH HEAD_SHA < <(gh pr view "$PR_NUMBER" --repo "$OWNER_REPO" \
    --json headRefName,headRefOid \
    --jq '[.headRefName, .headRefOid] | @tsv' | tr '\t' ' ') \
    || error "Could not look up head for ${OWNER_REPO}#${PR_NUMBER}"
[[ -n "$HEAD_SHA" ]] || error "Empty head SHA for ${OWNER_REPO}#${PR_NUMBER}"

# /worktree-compatible repo key: <basename>-<sha256(repo_root)[:12]>.
REPO_BASENAME="$(basename "$REPO_ROOT")"
REPO_HASH="$(sha256_short "$REPO_ROOT")"
REPO_KEY="${REPO_BASENAME}-${REPO_HASH}"

WORKTREE_ID="pr-${PR_NUMBER}-$(openssl rand -hex 4)"
WORKTREE_DIR="${HOME}/.cursor/worktrees/${WORKTREE_ID}/${REPO_KEY}"

[[ -d "$WORKTREE_DIR" ]] && error "Worktree directory already exists: ${WORKTREE_DIR}"
mkdir -p "$(dirname "$WORKTREE_DIR")"

info "Fetching origin/${BRANCH} (${HEAD_SHA:0:8})"
# `--` so a branch name starting with `-` is treated as a refspec, not an option.
git fetch origin -- "$BRANCH"

info "Creating read-only detached worktree at ${HEAD_SHA:0:8}"
# --detach: no local branch is created, so nothing can be committed/pushed by
# mistake. This is the key difference from the write-capable -all skill.
git worktree add --detach "$WORKTREE_DIR" "$HEAD_SHA"

# Run the repo's worktree setup so linters resolve (venv, .env). Mirrors
# create_pr_worktree.sh; kept identical so both skills behave the same.
WORKTREES_JSON="${REPO_ROOT}/.cursor/worktrees.json"
export ROOT_WORKTREE_PATH="$REPO_ROOT"
(
    cd "$WORKTREE_DIR"
    if [[ -f "$WORKTREES_JSON" ]] && command -v jq >/dev/null 2>&1; then
        info "Running setup-worktree from .cursor/worktrees.json"
        jq -r 'if (."setup-worktree"|type) == "array" then ."setup-worktree"[] else (."setup-worktree" // empty) end' \
            "$WORKTREES_JSON" | while IFS= read -r cmd; do
            [[ -z "$cmd" || "$cmd" == "null" ]] && continue
            info "  \$ ${cmd}"
            bash -c "$cmd" || error "setup step failed: ${cmd}"
        done
    else
        warn "jq or .cursor/worktrees.json unavailable; running best-effort default setup"
        rsync -am --exclude='node_modules' --exclude='.next' --exclude='.git' \
            --include='*/' --include='.env' --exclude='*' "${ROOT_WORKTREE_PATH}/" . \
            || warn "rsync of .env files into the worktree failed (continuing)"
        if command -v uv >/dev/null 2>&1 && [[ -f pyproject.toml || -f uv.lock ]]; then
            uv sync --all-packages || warn "uv sync --all-packages failed (continuing)"
        fi
    fi
)

echo "WORKTREE_ID=${WORKTREE_ID}"
echo "WORKTREE_PATH=${WORKTREE_DIR}"
echo "HEAD_SHA=${HEAD_SHA}"
