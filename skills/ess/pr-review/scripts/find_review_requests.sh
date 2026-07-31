#!/usr/bin/env bash
#
# find_review_requests.sh
# Discover the current repo's open PRs where a review is requested of you
# (review-requested:@me). Use when /pr-review is invoked with no PR refs.
#
# Usage: find_review_requests.sh [--repo owner/repo] [--limit N] [--include-team]
#   --repo owner/repo - Repo to query (default: current remote)
#   --limit N         - Max PRs to return (default: 50)
#   --include-team    - Also include PRs requested from a team you belong to
#                       (default only counts direct, user-level requests)
#
# Output:
#   stdout - matching PR numbers, one per line (for the skill to loop over)
#   stderr - a human-readable table (number, branch, author, title)
#
# Drafts are skipped. Exits 0 with empty stdout when nothing matches.

set -euo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${_LIB_DIR}/lib.sh"

command -v gh >/dev/null 2>&1 || error "gh CLI not found on PATH"

OWNER_REPO=""
LIMIT="50"
INCLUDE_TEAM="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) OWNER_REPO="${2:-}"; shift 2 ;;
        --limit) LIMIT="${2:-}"; shift 2 ;;
        --include-team) INCLUDE_TEAM="true"; shift ;;
        -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

if [[ -z "$OWNER_REPO" ]]; then
    OWNER_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)" \
        || error "Could not determine repo from current remote; pass --repo owner/repo"
fi

# GitHub search distinguishes:
#   user-review-requested:@me - only direct, user-level review requests
#   review-requested:@me      - direct requests PLUS requests to a team you are on
# Default to the narrower user-level filter; --include-team broadens it.
if [[ "$INCLUDE_TEAM" == "true" ]]; then
    SEARCH="review-requested:@me"
else
    SEARCH="user-review-requested:@me"
fi
info "Scanning open PRs in ${OWNER_REPO} where review is requested of you (limit ${LIMIT})"

# Numbers + metadata as TSV (number<TAB>branch<TAB>author<TAB>title), drafts out.
PR_ROWS="$(gh pr list --repo "$OWNER_REPO" --state open --limit "$LIMIT" \
    --search "$SEARCH" \
    --json number,headRefName,author,title,isDraft \
    --jq '.[] | select(.isDraft == false)
          | [.number, .headRefName, (.author.login // ""), .title] | @tsv')" \
    || error "gh pr list failed for ${OWNER_REPO}"

if [[ -z "$PR_ROWS" ]]; then
    info "No open PRs currently request your review in ${OWNER_REPO}"
    exit 0
fi

printf 'PR\tBRANCH\tAUTHOR\tTITLE\n' >&2

MATCHES=()
while IFS=$'\t' read -r NUMBER BRANCH AUTHOR TITLE; do
    [[ -z "$NUMBER" ]] && continue
    MATCHES+=("$NUMBER")
    printf '%s\t%s\t%s\t%s\n' "$NUMBER" "$BRANCH" "${AUTHOR:-unknown}" "$TITLE" >&2
done <<< "$PR_ROWS"

if [[ ${#MATCHES[@]} -eq 0 ]]; then
    info "No open, non-draft PRs request your review in ${OWNER_REPO}"
    exit 0
fi

info "Matched ${#MATCHES[@]} PR(s)"
printf '%s\n' "${MATCHES[@]}"
