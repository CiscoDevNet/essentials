#!/usr/bin/env bash
#
# reply_and_resolve.sh
# Reply to a PR review comment and resolve its thread. Encapsulates the
# error-prone Step 9 of pr-address-comments (SKILL.md):
#   - REST reply via POST /repos/<o>/<r>/pulls/<N>/comments with in_reply_to
#     (NOT the /replies sub-resource, which 404s)
#   - GraphQL resolveReviewThread mutation
#
# Usage:
#   reply_and_resolve.sh --repo owner/repo --pr N \
#     --comment-id ID --thread-id TID --body "Fixed — <what changed>"
#
# Only call this for threads that were actually ADDRESSED in code. Skip
# discussion-only threads.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }
info() { echo -e "${GREEN}→${NC} $1" >&2; }

OWNER_REPO=""
PR_NUMBER=""
COMMENT_ID=""
THREAD_ID=""
BODY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) OWNER_REPO="${2:-}"; shift 2 ;;
        --pr) PR_NUMBER="${2:-}"; shift 2 ;;
        --comment-id) COMMENT_ID="${2:-}"; shift 2 ;;
        --thread-id) THREAD_ID="${2:-}"; shift 2 ;;
        --body) BODY="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

[[ -n "$OWNER_REPO" ]] || error "Missing --repo owner/repo"
[[ -n "$PR_NUMBER" ]] || error "Missing --pr N"
[[ -n "$COMMENT_ID" ]] || error "Missing --comment-id ID"
[[ -n "$THREAD_ID" ]] || error "Missing --thread-id TID"
[[ -n "$BODY" ]] || error "Missing --body \"message\""
command -v gh >/dev/null 2>&1 || error "gh CLI not found on PATH"

info "Replying to comment ${COMMENT_ID} on ${OWNER_REPO}#${PR_NUMBER}"
gh api "repos/${OWNER_REPO}/pulls/${PR_NUMBER}/comments" \
    -f body="$BODY" \
    -F in_reply_to="$COMMENT_ID" >/dev/null \
    || error "Reply failed for comment ${COMMENT_ID}"

info "Resolving thread ${THREAD_ID}"
gh api graphql -f query='
mutation($threadId:ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { isResolved }
  }
}' -F threadId="$THREAD_ID" >/dev/null \
    || error "Resolve failed for thread ${THREAD_ID}"

info "Replied + resolved thread ${THREAD_ID}"
