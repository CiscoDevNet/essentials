#!/usr/bin/env bash
#
# fetch_pr.sh
# Look up ONE PR reference and dump everything the skill needs to plan and
# address its review comments.
#
# Usage: fetch_pr.sh <pr-ref> [--repo owner/repo] [--output DIR]
#   <pr-ref>          - Full PR URL (https://github.com/<o>/<r>/pull/<N>) or a bare number
#   --repo owner/repo - Repo to use for a bare number (default: current remote)
#   --output DIR      - Output directory (default: /tmp/pr-address-<owner>-<repo>-<number>)
#
# Writes into DIR:
#   meta.env      - OWNER=, REPO=, NUMBER=, BRANCH=, TITLE=, STATE= (shell-escaped)
#   comments.json - raw inline review comments (gh api .../pulls/<N>/comments)
#   threads.json  - unresolved review threads as NDJSON {threadId,commentId,path,line,body}
#
# Also prints the meta block to stdout. Exits non-zero if gh fails -- never
# fabricates data.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }
info() { echo -e "${GREEN}→${NC} $1" >&2; }
warn() { echo -e "${YELLOW}Warning:${NC} $1" >&2; }

command -v gh >/dev/null 2>&1 || error "gh CLI not found on PATH"

PR_REF=""
REPO_OVERRIDE=""
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            REPO_OVERRIDE="${2:-}"; shift 2 ;;
        --output)
            OUTPUT_DIR="${2:-}"; shift 2 ;;
        -h|--help)
            sed -n '2,22p' "$0"; exit 0 ;;
        -*)
            error "Unknown option: $1" ;;
        *)
            if [[ -z "$PR_REF" ]]; then PR_REF="$1"; else error "Unexpected argument: $1"; fi
            shift ;;
    esac
done

[[ -n "$PR_REF" ]] || error "Missing <pr-ref>. See --help."

# Parse the PR reference into OWNER / REPO / NUMBER.
if [[ "$PR_REF" =~ ^https?://[^/]+/([^/]+)/([^/]+)/pull/([0-9]+) ]]; then
    OWNER="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
    NUMBER="${BASH_REMATCH[3]}"
elif [[ "$PR_REF" =~ ^[0-9]+$ ]]; then
    NUMBER="$PR_REF"
    if [[ -n "$REPO_OVERRIDE" ]]; then
        OWNER="${REPO_OVERRIDE%%/*}"
        REPO="${REPO_OVERRIDE#*/}"
    else
        NAME_WITH_OWNER="$(gh repo view --json nameWithOwner --jq .nameWithOwner)" \
            || error "Could not determine repo from current remote; pass --repo owner/repo"
        OWNER="${NAME_WITH_OWNER%%/*}"
        REPO="${NAME_WITH_OWNER#*/}"
    fi
else
    error "Could not parse PR reference: ${PR_REF} (expected a URL or a bare number)"
fi

# Default output dir is owner/repo-qualified so the same PR number in different
# repos does not collide under /tmp. Sanitize any '/' in owner/repo to '-'.
if [[ -z "$OUTPUT_DIR" ]]; then
    SAFE_OWNER="${OWNER//\//-}"
    SAFE_REPO="${REPO//\//-}"
    OUTPUT_DIR="/tmp/pr-address-${SAFE_OWNER}-${SAFE_REPO}-${NUMBER}"
fi
mkdir -p "$OUTPUT_DIR"

info "PR #${NUMBER} in ${OWNER}/${REPO}"

# Metadata (branch is what the worktree checks out). gh has a built-in --jq,
# so no external jq/python dependency is needed.
BRANCH="$(gh pr view "$NUMBER" --repo "${OWNER}/${REPO}" --json headRefName --jq '.headRefName')" \
    || error "gh pr view failed for ${OWNER}/${REPO}#${NUMBER}"
TITLE="$(gh pr view "$NUMBER" --repo "${OWNER}/${REPO}" --json title --jq '.title')" \
    || error "gh pr view (title) failed for ${OWNER}/${REPO}#${NUMBER}"
STATE="$(gh pr view "$NUMBER" --repo "${OWNER}/${REPO}" --json state --jq '.state')" \
    || error "gh pr view (state) failed for ${OWNER}/${REPO}#${NUMBER}"

# Inline review comments to address.
gh api "repos/${OWNER}/${REPO}/pulls/${NUMBER}/comments" > "${OUTPUT_DIR}/comments.json" \
    || error "gh api comments failed for ${OWNER}/${REPO}#${NUMBER}"

# Unresolved review threads (thread id + first comment's databaseId/path/line/body),
# paginated through ALL pages so a PR with >100 threads is never truncated. One
# gh call per page; each page emits its unresolved threads as NDJSON plus a final
# "@@PAGE<TAB>hasNextPage<TAB>endCursor" marker, so no external jq is needed.
THREADS_QUERY='
query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes {
          id
          isResolved
          comments(first: 1) { nodes { databaseId path line originalLine body } }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}'
: > "${OUTPUT_DIR}/threads.json"
CURSOR=""
while :; do
    if [[ -z "$CURSOR" ]]; then PAGE_ARG=(-F cursor=null); else PAGE_ARG=(-f cursor="$CURSOR"); fi
    PAGE_OUT="$(gh api graphql -f query="$THREADS_QUERY" \
        -F owner="$OWNER" -F repo="$REPO" -F number="$NUMBER" "${PAGE_ARG[@]}" \
        --jq '(.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | {threadId: .id, commentId: .comments.nodes[0].databaseId, path: .comments.nodes[0].path, line: (.comments.nodes[0].line // .comments.nodes[0].originalLine), body: .comments.nodes[0].body}), ("@@PAGE\t" + (.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage|tostring) + "\t" + (.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // ""))')" \
        || error "gh api graphql (reviewThreads) failed for ${OWNER}/${REPO}#${NUMBER}"
    HAS_NEXT="false"; NEXT_CURSOR=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        if [[ "$line" == "@@PAGE"$'\t'* ]]; then
            IFS=$'\t' read -r _ HAS_NEXT NEXT_CURSOR <<< "$line"
        else
            printf '%s\n' "$line" >> "${OUTPUT_DIR}/threads.json"
        fi
    done <<< "$PAGE_OUT"
    CURSOR="$NEXT_CURSOR"
    [[ "$HAS_NEXT" == "true" && -n "$CURSOR" ]] || break
done

THREAD_COUNT="$(grep -c '"threadId"' "${OUTPUT_DIR}/threads.json" 2>/dev/null || echo 0)"
info "Unresolved threads: ${THREAD_COUNT}"

# Write + emit the meta block. Values are shell-escaped with printf %q so a
# title containing spaces/quotes/newlines round-trips safely when sourced.
META_FILE="${OUTPUT_DIR}/meta.env"
{
    printf 'OWNER=%q\n' "$OWNER"
    printf 'REPO=%q\n' "$REPO"
    printf 'NUMBER=%q\n' "$NUMBER"
    printf 'BRANCH=%q\n' "$BRANCH"
    printf 'TITLE=%q\n' "$TITLE"
    printf 'STATE=%q\n' "$STATE"
    printf 'OUTPUT_DIR=%q\n' "$OUTPUT_DIR"
    printf 'THREAD_COUNT=%q\n' "$THREAD_COUNT"
} | tee "$META_FILE"

info "Wrote ${META_FILE}, comments.json, threads.json to ${OUTPUT_DIR}"
