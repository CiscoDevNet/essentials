#!/usr/bin/env bash
#
# fetch-pr.sh
# Look up ONE PR reference and dump everything the skill needs to plan and
# address its review comments.
#
# Usage: fetch-pr.sh <pr-ref> [--repo owner/repo] [--output DIR]
#   <pr-ref>          - Full PR URL (https://github.com/<o>/<r>/pull/<N>) or a bare number
#   --repo owner/repo - Repo to use for a bare number (default: current remote)
#   --output DIR      - Output directory (default: /tmp/pr-address-<owner>-<repo>-<number>)
#
# Writes into DIR:
#   meta.env      - OWNER=, REPO=, NUMBER=, BRANCH=, TITLE=, STATE= (shell-escaped)
#   comments.json - raw inline review comments (gh api .../pulls/<N>/comments)
#   threads.json  - one NDJSON object per comment {threadId,commentId,path,line,root,body}; root=true is the reply target
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

# Unresolved review threads, including every comment (not only the first).
# One NDJSON object per comment: {threadId,commentId,path,line,root,body}.
# root=true is the first comment; reply to that commentId. Thread pages and
# comment pages are both paginated. Each gh --jq page emits compact JSON via
# @json plus @@COMMENTS / @@PAGE markers, so no external jq is needed.
THREADS_QUERY='
query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes {
          id
          isResolved
          comments(first: 100) {
            nodes { databaseId path line originalLine body }
            pageInfo { hasNextPage endCursor }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}'
THREAD_JQ='
(.data.repository.pullRequest.reviewThreads.nodes[]
  | select(.isResolved == false)
  | . as $t
  | (
      $t.comments.nodes
      | to_entries[]
      | {
          threadId: $t.id,
          commentId: .value.databaseId,
          path: .value.path,
          line: (.value.line // .value.originalLine),
          root: (.key == 0),
          body: .value.body
        }
      | @json
    ),
    (
      select($t.comments.pageInfo.hasNextPage)
      | "@@COMMENTS\t" + $t.id + "\t" + ($t.comments.pageInfo.endCursor // "")
    )
),
("@@PAGE\t" + (.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage|tostring) + "\t" + (.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // ""))
'
COMMENTS_QUERY='
query($id:ID!, $cursor:String) {
  node(id: $id) {
    ... on PullRequestReviewThread {
      id
      comments(first: 100, after: $cursor) {
        nodes { databaseId path line originalLine body }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}'
COMMENT_JQ='
.data.node as $t
| (
    $t.comments.nodes[]
    | {
        threadId: $t.id,
        commentId: .databaseId,
        path: .path,
        line: (.line // .originalLine),
        root: false,
        body: .body
      }
    | @json
  ),
  (
    select($t.comments.pageInfo.hasNextPage)
    | "@@COMMENTS\t" + $t.id + "\t" + ($t.comments.pageInfo.endCursor // "")
  )
'

: > "${OUTPUT_DIR}/threads.json"
COMMENT_QUEUE="${OUTPUT_DIR}/.comment-queue"
: > "$COMMENT_QUEUE"

# Split one gh --jq page into comment rows, comment-continuation markers, and
# the thread-page marker. Sets HAS_NEXT and NEXT_CURSOR when @@PAGE is present.
consume_page() {
    local page_out="$1"
    HAS_NEXT="false"
    NEXT_CURSOR=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        if [[ "$line" == "@@PAGE"$'\t'* ]]; then
            IFS=$'\t' read -r _ HAS_NEXT NEXT_CURSOR <<< "$line"
        elif [[ "$line" == "@@COMMENTS"$'\t'* ]]; then
            printf '%s\n' "$line" >> "$COMMENT_QUEUE"
        else
            printf '%s\n' "$line" >> "${OUTPUT_DIR}/threads.json"
        fi
    done <<< "$page_out"
}

CURSOR=""
while :; do
    if [[ -z "$CURSOR" ]]; then PAGE_ARG=(-F cursor=null); else PAGE_ARG=(-f cursor="$CURSOR"); fi
    PAGE_OUT="$(gh api graphql -f query="$THREADS_QUERY" \
        -F owner="$OWNER" -F repo="$REPO" -F number="$NUMBER" "${PAGE_ARG[@]}" \
        --jq "$THREAD_JQ")" \
        || error "gh api graphql (reviewThreads) failed for ${OWNER}/${REPO}#${NUMBER}"
    consume_page "$PAGE_OUT"
    CURSOR="$NEXT_CURSOR"
    [[ "$HAS_NEXT" == "true" && -n "$CURSOR" ]] || break
done

# A comment page can enqueue another @@COMMENTS marker. Drop the marker being
# handled before the request so a retry cannot process it twice.
while [[ -s "$COMMENT_QUEUE" ]]; do
    IFS=$'\t' read -r _ THREAD_NODE COMMENT_CURSOR < "$COMMENT_QUEUE"
    tail -n +2 "$COMMENT_QUEUE" > "${COMMENT_QUEUE}.next"
    mv "${COMMENT_QUEUE}.next" "$COMMENT_QUEUE"
    [[ -n "${THREAD_NODE}" && -n "${COMMENT_CURSOR}" ]] \
        || error "Malformed comment page marker for ${OWNER}/${REPO}#${NUMBER}"
    PAGE_OUT="$(gh api graphql -f query="$COMMENTS_QUERY" \
        -F id="$THREAD_NODE" -f cursor="$COMMENT_CURSOR" \
        --jq "$COMMENT_JQ")" \
        || error "gh api graphql (reviewThread comments) failed for ${OWNER}/${REPO}#${NUMBER}"
    consume_page "$PAGE_OUT"
done
rm -f "$COMMENT_QUEUE"

# Count threads, not comments. grep -c exits 1 when the count is 0; do not
# append a second 0 with `|| echo`.
THREAD_COUNT="$(grep -c '"root":true' "${OUTPUT_DIR}/threads.json" 2>/dev/null || true)"
THREAD_COUNT="${THREAD_COUNT:-0}"
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
