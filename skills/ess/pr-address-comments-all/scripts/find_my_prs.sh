#!/usr/bin/env bash
#
# find_my_prs.sh
# Discover the current repo's open PRs authored by you that need attention:
# either the review decision is CHANGES_REQUESTED, or there is at least one
# unresolved review thread.
#
# Usage: find_my_prs.sh [--repo owner/repo] [--limit N]
#   --repo owner/repo - Repo to query (default: current remote)
#   --limit N         - Max PRs to scan (default: 50)
#
# Output:
#   stdout - matching PR numbers, one per line (for the skill to loop over)
#   stderr - a human-readable table (number, decision, unresolved, branch, title)
#
# Exits 0 with empty stdout when nothing matches.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }
info() { echo -e "${GREEN}→${NC} $1" >&2; }
warn() { echo -e "${YELLOW}Warning:${NC} $1" >&2; }

command -v gh >/dev/null 2>&1 || error "gh CLI not found on PATH"

OWNER_REPO=""
LIMIT="50"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) OWNER_REPO="${2:-}"; shift 2 ;;
        --limit) LIMIT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

if [[ -z "$OWNER_REPO" ]]; then
    OWNER_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)" \
        || error "Could not determine repo from current remote; pass --repo owner/repo"
fi
OWNER="${OWNER_REPO%%/*}"
REPO="${OWNER_REPO#*/}"

info "Scanning my open PRs in ${OWNER_REPO} (limit ${LIMIT})"

# My open PRs with their review decision and branch, as TSV (number<TAB>decision<TAB>branch<TAB>title).
PR_ROWS="$(gh pr list --repo "$OWNER_REPO" --author "@me" --state open --limit "$LIMIT" \
    --json number,reviewDecision,headRefName,title \
    --jq '.[] | [.number, (.reviewDecision // ""), .headRefName, .title] | @tsv')" \
    || error "gh pr list failed for ${OWNER_REPO}"

if [[ -z "$PR_ROWS" ]]; then
    info "No open PRs authored by you in ${OWNER_REPO}"
    exit 0
fi

UNRESOLVED_QUERY='
query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes { isResolved }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}'

# Count unresolved review threads for one PR, paginating through ALL threads (a
# single page of 100 can otherwise misclassify a busy PR as having 0 unresolved).
# Echoes the total on success; returns non-zero if any gh call fails.
count_unresolved_threads() {
    local number="$1"
    local cursor="" total=0 page resp count has_next end_cursor
    while :; do
        # First page passes a JSON null cursor (-F magic); later pages pass the
        # opaque endCursor as a raw string (-f) to avoid any injection concerns.
        if [[ -z "$cursor" ]]; then
            page=(-F cursor=null)
        else
            page=(-f cursor="$cursor")
        fi
        resp="$(gh api graphql -f query="$UNRESOLVED_QUERY" \
            -F owner="$OWNER" -F repo="$REPO" -F number="$number" "${page[@]}" \
            --jq '.data.repository.pullRequest.reviewThreads as $t
                  | [ ([$t.nodes[] | select(.isResolved == false)] | length | tostring),
                      ($t.pageInfo.hasNextPage | tostring),
                      ($t.pageInfo.endCursor // "") ] | @tsv')" || return 1
        IFS=$'\t' read -r count has_next end_cursor <<< "$resp"
        total=$(( total + count ))
        if [[ "$has_next" == "true" && -n "$end_cursor" ]]; then
            cursor="$end_cursor"
        else
            break
        fi
    done
    printf '%s' "$total"
}

printf 'PR\tDECISION\tUNRESOLVED\tBRANCH\tTITLE\n' >&2

MATCHES=()
while IFS=$'\t' read -r NUMBER DECISION BRANCH TITLE; do
    [[ -z "$NUMBER" ]] && continue
    UNRESOLVED="$(count_unresolved_threads "$NUMBER")" \
        || { warn "Could not read threads for #${NUMBER}; skipping"; continue; }

    if [[ "$DECISION" == "CHANGES_REQUESTED" || "$UNRESOLVED" -gt 0 ]]; then
        MATCHES+=("$NUMBER")
        printf '%s\t%s\t%s\t%s\t%s\n' "$NUMBER" "${DECISION:-NONE}" "$UNRESOLVED" "$BRANCH" "$TITLE" >&2
    fi
done <<< "$PR_ROWS"

if [[ ${#MATCHES[@]} -eq 0 ]]; then
    info "No open PRs need attention (no changes-requested or unresolved comments)"
    exit 0
fi

info "Matched ${#MATCHES[@]} PR(s)"
printf '%s\n' "${MATCHES[@]}"
