#!/usr/bin/env bash
#
# create_pr_worktree.sh
# Create a git worktree checked out ON a PR's branch (so work commits locally
# and pushes straight back to the PR), then run the repo's worktree setup.
#
# Mirrors the /worktree command's on-disk layout
# (~/.cursor/worktrees/<WORKTREE_ID>/<repo-key>) so /delete-worktree still
# works, but uses `git worktree add -B <branch>` instead of --detach.
#
# Usage: create_pr_worktree.sh --pr N --repo owner/repo [--branch B]
#   --pr N            - PR number (used to name the worktree)
#   --repo owner/repo - Repo the PR lives in
#   --branch B        - PR head branch (default: looked up via gh)
#
# Run from inside the target repo. Prints WORKTREE_ID, WORKTREE_PATH, BRANCH.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }
info() { echo -e "${GREEN}→${NC} $1" >&2; }
warn() { echo -e "${YELLOW}Warning:${NC} $1" >&2; }

PR_NUMBER=""
OWNER_REPO=""
BRANCH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pr) PR_NUMBER="${2:-}"; shift 2 ;;
        --repo) OWNER_REPO="${2:-}"; shift 2 ;;
        --branch) BRANCH="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

[[ -n "$PR_NUMBER" ]] || error "Missing --pr N"
[[ -n "$OWNER_REPO" ]] || error "Missing --repo owner/repo"
command -v gh >/dev/null 2>&1 || error "gh CLI not found on PATH"
command -v openssl >/dev/null 2>&1 || error "openssl not found on PATH"

REPO_ROOT="$(git rev-parse --show-toplevel)" || error "Not inside a git repository"

if [[ -z "$BRANCH" ]]; then
    BRANCH="$(gh pr view "$PR_NUMBER" --repo "$OWNER_REPO" --json headRefName --jq '.headRefName')" \
        || error "Could not look up branch for ${OWNER_REPO}#${PR_NUMBER}"
fi

# /worktree-compatible repo key: <basename>-<sha256(repo_root)[:12]>.
REPO_BASENAME="$(basename "$REPO_ROOT")"
if command -v shasum >/dev/null 2>&1; then
    REPO_HASH="$(printf '%s' "$REPO_ROOT" | shasum -a 256 | cut -c1-12)"
else
    REPO_HASH="$(printf '%s' "$REPO_ROOT" | sha256sum | cut -c1-12)"
fi
REPO_KEY="${REPO_BASENAME}-${REPO_HASH}"

WORKTREE_ID="pr-${PR_NUMBER}-$(openssl rand -hex 4)"
WORKTREE_DIR="${HOME}/.cursor/worktrees/${WORKTREE_ID}/${REPO_KEY}"

[[ -d "$WORKTREE_DIR" ]] && error "Worktree directory already exists: ${WORKTREE_DIR}"
mkdir -p "$(dirname "$WORKTREE_DIR")"

info "Fetching origin/${BRANCH}"
# `--` so a branch name starting with `-` is treated as a refspec, not an option.
git fetch origin -- "$BRANCH"

info "Creating worktree on branch ${BRANCH}"
# -B resets/creates a real local branch tracking origin/<branch>, checked out
# in the new worktree. Commits land on the branch; `git push origin <branch>`
# updates the PR. Fails if the branch is already checked out elsewhere -- see
# references/worktree-mechanics.md for that edge case.
git worktree add -B "$BRANCH" "$WORKTREE_DIR" "origin/${BRANCH}"

# Run the repo's worktree setup (mirrors the /worktree command).
WORKTREES_JSON="${REPO_ROOT}/.cursor/worktrees.json"
export ROOT_WORKTREE_PATH="$REPO_ROOT"
(
    cd "$WORKTREE_DIR"
    if [[ -f "$WORKTREES_JSON" ]] && command -v jq >/dev/null 2>&1; then
        info "Running setup-worktree from .cursor/worktrees.json"
        # setup-worktree may be a string, an array of strings, or absent. `// empty`
        # makes a missing/null key emit nothing (instead of the literal "null").
        jq -r 'if (."setup-worktree"|type) == "array" then ."setup-worktree"[] else (."setup-worktree" // empty) end' \
            "$WORKTREES_JSON" | while IFS= read -r cmd; do
            [[ -z "$cmd" || "$cmd" == "null" ]] && continue
            info "  \$ ${cmd}"
            # Fail fast: a half-provisioned worktree (e.g. failed `uv sync`) would
            # otherwise be reported as success and cause confusing downstream errors.
            bash -c "$cmd" || error "setup step failed: ${cmd}"
        done
    else
        # No .cursor/worktrees.json (or no jq): best-effort, project-agnostic
        # setup. Copy any .env files from the main tree so the worktree can run,
        # then sync the venv ONLY if this looks like a uv project. Non-uv repos
        # simply skip that step instead of hard-failing.
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
echo "BRANCH=${BRANCH}"
