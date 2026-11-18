#!/usr/bin/env bash
#
# find-review-requests.sh
# Discover the current repo's open PRs where a review is requested of you
# (review-requested:@me). Use when /ess-pr-review is invoked with no PR refs.
#
# Usage: find-review-requests.sh [--repo owner/repo] [--limit N] [--include-team]
#                                [--author TERM]...
#   --repo owner/repo - Repo to query (default: current remote)
#   --limit N         - Max PRs to return (default: 50)
#   --include-team    - Also include PRs requested from a team you belong to
#                       (default only counts direct, user-level requests)
#   --author TERM     - Keep only PRs from TERM. Repeatable; a PR is kept when
#                       it matches ANY term. TERM is one of:
#                         @me              - you
#                         @org/team-slug   - members of that GitHub org team
#                         @team-slug       - same, in this repo's own org
#                         anything else    - a GitHub login or email (exact), or
#                                            a display name (substring), matched
#                                            against the PR author and its
#                                            commit authors
#
# --author only ever NARROWS the review-requested set; it cannot surface a PR
# that was never assigned to you. Listing org team members needs the `read:org`
# scope on your gh token.
#
# Environment:
#   PR_REVIEW_PR_FIXTURE   - path to a `gh pr list --json` JSON array that stands
#                            in for the live query, so test_find_review_requests.sh
#                            can exercise filtering offline
#   PR_REVIEW_TEAM_FIXTURE - path to a TSV of "org/slug<TAB>login" rows that
#                            stands in for org team member lookups
#   PR_REVIEW_COMMIT_FAIL  - space-separated PR numbers whose commit-author lookup
#                            should fail, so the test can reach that path (only
#                            honored alongside PR_REVIEW_PR_FIXTURE)
#
# Output:
#   stdout - matching PR numbers, one per line (for the skill to loop over)
#   stderr - a human-readable table (number, branch, author, title)
#
# Drafts are skipped. Exits 0 with empty stdout when nothing matches. Exits
# non-zero, after printing the table and every warning, when a commit-author
# lookup failed and the results are therefore incomplete.
#
# This script only reads; it posts and writes nothing, so it takes no --dry-run
# and never prompts. Portable to bash 3.2 (macOS): no associative arrays and no
# unguarded expansion of a possibly-empty array.

set -euo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${_LIB_DIR}/lib.sh"

PR_FIXTURE="${PR_REVIEW_PR_FIXTURE:-}"
TEAM_FIXTURE="${PR_REVIEW_TEAM_FIXTURE:-}"
COMMIT_FAIL_NUMBERS="${PR_REVIEW_COMMIT_FAIL:-}"

# gh is only needed for the live queries; the fixtures replace both of them.
if [[ -z "$PR_FIXTURE" || -z "$TEAM_FIXTURE" ]]; then
    command -v gh >/dev/null 2>&1 || error "gh CLI not found on PATH"
fi

OWNER_REPO=""
LIMIT="50"
INCLUDE_TEAM="false"
RAW_TERMS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) OWNER_REPO="${2:-}"; shift 2 ;;
        --limit) LIMIT="${2:-}"; shift 2 ;;
        --include-team) INCLUDE_TEAM="true"; shift ;;
        --author)
            [[ -n "${2:-}" ]] || error "--author needs a value"
            RAW_TERMS+=("$2"); shift 2 ;;
        -h|--help) sed -n '2,43p' "$0"; exit 0 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

if [[ -z "$OWNER_REPO" ]]; then
    OWNER_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)" \
        || error "Could not determine repo from current remote; pass --repo owner/repo"
fi
REPO_OWNER="${OWNER_REPO%%/*}"

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# Logins of a GitHub org team. Members come back one per line; the caller turns
# them into exact-match terms.
team_members() {
    local org="$1" slug="$2"
    if [[ -n "$TEAM_FIXTURE" ]]; then
        [[ -f "$TEAM_FIXTURE" ]] \
            || error "PR_REVIEW_TEAM_FIXTURE not found: $TEAM_FIXTURE"
        # A row whose key is present but whose login is empty models a real team
        # with no visible members (warn, exit 0); an absent key models a bad slug
        # and must fail, like the live `gh api` call does.
        awk -F'\t' -v key="${org}/${slug}" \
            '$1 == key { found = 1; if ($2 != "") print $2 }
             END { exit(found ? 0 : 1) }' "$TEAM_FIXTURE"
        return
    fi
    gh api --paginate "orgs/${org}/teams/${slug}/members" --jq '.[].login'
}

# --- resolve --author terms ---------------------------------------------------
# Each raw term keeps its own row so an unmatched term can be reported using the
# text the user typed rather than whatever it expanded to. Parallel arrays stand
# in for the associative array bash 3.2 does not have:
#   TERM_LOGINS[i] - "|login|login|" for @me and @org/team terms, else empty
#   TERM_FREE[i]   - lowercased free text for every other term, else empty
#   TERM_HIT[i]    - 1 once the term has kept at least one PR
TERM_LOGINS=()
TERM_FREE=()
TERM_HIT=()

if [[ ${#RAW_TERMS[@]} -gt 0 ]]; then
    for RAW in "${RAW_TERMS[@]}"; do
        LOGINS=""
        FREE=""
        case "$RAW" in
            @me)
                ME="$(gh api user --jq .login)" \
                    || error "could not resolve @me; check 'gh auth status'"
                LOGINS="|$(lower "$ME")|"
                ;;
            @*)
                SPEC="${RAW#@}"
                if [[ "$SPEC" == */* ]]; then
                    ORG="${SPEC%%/*}"
                    SLUG="${SPEC#*/}"
                else
                    ORG="$REPO_OWNER"
                    SLUG="$SPEC"
                fi
                [[ -n "$ORG" && -n "$SLUG" ]] \
                    || error "could not parse team from '${RAW}'; expected @org/team-slug"
                # A failure here is a bad slug or a token without read:org --
                # a configuration problem, not an empty result -- so stop.
                MEMBERS="$(team_members "$ORG" "$SLUG")" \
                    || error "could not list members of ${ORG}/${SLUG}; check the slug and that your gh token has the read:org scope"
                LOGINS="|"
                COUNT=0
                while IFS= read -r MEMBER; do
                    [[ -n "$MEMBER" ]] || continue
                    LOGINS="${LOGINS}$(lower "$MEMBER")|"
                    COUNT=$((COUNT + 1))
                done <<< "$MEMBERS"
                # A successful but empty response is an unmatched term, not a
                # configuration error: with no logins and no free text the term
                # keeps nothing and the per-term warning below reports it.
                if [[ "$COUNT" -eq 0 ]]; then
                    warn "team ${ORG}/${SLUG} has no visible members; check the slug and that your gh token has the read:org scope"
                    LOGINS=""
                else
                    info "Team ${ORG}/${SLUG}: ${COUNT} member(s)"
                fi
                ;;
            *)
                FREE="$(lower "$RAW")"
                ;;
        esac
        TERM_LOGINS+=("$LOGINS")
        TERM_FREE+=("$FREE")
        TERM_HIT+=("0")
    done
fi

# Only free-text terms can ever need commit-author data, which the PR list query
# does not carry. @me and @org/team terms are answered entirely by that query, so
# this flag short-circuits the per-PR escalation when every term is one of those.
HAS_FREE="false"
if [[ ${#TERM_FREE[@]} -gt 0 ]]; then
    for FREE in "${TERM_FREE[@]}"; do
        if [[ -n "$FREE" ]]; then
            HAS_FREE="true"
            break
        fi
    done
fi

# --- query --------------------------------------------------------------------
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

# Columns: number, branch, author login, title, a draft flag, then two
# lowercased match blobs.
#   exact blob - "|login|...|", for terms that must match a whole field
#   name  blob - "|display name|...|", for substring matching
# `.author` carries both the login and the profile display name, so filtering by
# either costs no extra request. Commit authors are deliberately NOT requested
# here: `commits` on a 50-PR list expands to more than GitHub's 500,000-node
# GraphQL ceiling, so they are looked up per PR, lazily, further down. Drafts are
# returned rather than filtered here so the loop can count every row the query
# actually spent its --limit on. Both blobs are internal -- they never reach the
# table.
JQ_ROWS='.[]
    | (.author.login // "") as $login
    | ([$login] | map(select(. != "") | ascii_downcase) | unique) as $exact
    | ([.author.name // empty]
       | map(select(. != "") | ascii_downcase) | unique) as $names
    | [.number, .headRefName, $login, .title,
       (if .isDraft then "1" else "0" end),
       "|" + ($exact | join("|")) + "|",
       "|" + ($names | join("|")) + "|"] | @tsv'

# Same two blobs, built from one PR's commit authors.
JQ_COMMITS='([.commits[]?.authors[]?.login // empty]
        + [.commits[]?.authors[]?.email // empty]
       | map(select(. != "") | ascii_downcase) | unique) as $exact
    | ([.commits[]?.authors[]?.name // empty]
       | map(select(. != "") | ascii_downcase) | unique) as $names
    | ["|" + ($exact | join("|")) + "|",
       "|" + ($names | join("|")) + "|"] | @tsv'

if [[ -n "$PR_FIXTURE" ]]; then
    # Test seam: a canned `gh pr list --json` array stands in for the live query
    # so the filtering below can be exercised offline. The same jq programs run
    # either way, so the blobs under test are the real ones.
    [[ -f "$PR_FIXTURE" ]] || error "PR_REVIEW_PR_FIXTURE not found: $PR_FIXTURE"
    command -v jq >/dev/null 2>&1 || error "jq is required when PR_REVIEW_PR_FIXTURE is set"
    PR_ROWS="$(jq -r "$JQ_ROWS" < "$PR_FIXTURE")" \
        || error "could not parse PR fixture: $PR_FIXTURE"
    info "PR fixture: ${PR_FIXTURE}"
else
    PR_ROWS="$(gh pr list --repo "$OWNER_REPO" --state open --limit "$LIMIT" \
        --search "$SEARCH" \
        --json number,headRefName,author,title,isDraft \
        --jq "$JQ_ROWS")" \
        || error "gh pr list failed for ${OWNER_REPO}"
fi

# Commit authors for one PR, as "exact_blob<TAB>name_blob". Only reached when a
# term needs data the list query does not carry. Returns non-zero when the lookup
# fails, so the caller can report incomplete results rather than silently
# treating a failed lookup as "this PR does not match".
commit_blobs() {
    local number="$1" out
    if [[ -n "$PR_FIXTURE" ]]; then
        # Test seam: the fixture path never touches gh, so this lists the PR
        # numbers whose lookup should fail, making the failure path reachable
        # offline.
        case " ${COMMIT_FAIL_NUMBERS} " in
            *" ${number} "*)
                warn "could not read commit authors for PR #${number}: forced by PR_REVIEW_COMMIT_FAIL"
                return 1
                ;;
        esac
        jq -r --argjson n "$number" \
            ".[] | select(.number == \$n) | ${JQ_COMMITS}" < "$PR_FIXTURE"
        return
    fi
    if ! out="$(gh pr view "$number" --repo "$OWNER_REPO" --json commits \
        --jq "$JQ_COMMITS" 2>&1)"; then
        warn "could not read commit authors for PR #${number}: ${out}"
        return 1
    fi
    printf '%s\n' "$out"
}

# An empty queue needs no guard: `while ... <<< ""` yields one empty line, which
# the loop's empty-NUMBER check skips, so the loop is a no-op and control still
# reaches the per-term warnings and the zero-match message below.

# --- filter and report --------------------------------------------------------
# Quoted case patterns match literally, so a term containing *, ? or [ cannot
# turn into a glob and over-match.
term_matches() {
    local index="$1" exact_blob="$2" name_blob="$3"
    local logins="${TERM_LOGINS[index]}"
    local free="${TERM_FREE[index]}"

    if [[ -n "$logins" ]]; then
        local login
        local -a parts=()
        IFS='|' read -r -a parts <<< "$logins"
        if [[ ${#parts[@]} -gt 0 ]]; then
            for login in "${parts[@]}"; do
                [[ -n "$login" ]] || continue
                case "$exact_blob" in *"|${login}|"*) return 0 ;; esac
            done
        fi
    fi

    if [[ -n "$free" ]]; then
        # A login or email has to match a whole field; a display name is allowed
        # to match part of one, so "Bob" finds "Bob Brown".
        case "$exact_blob" in *"|${free}|"*) return 0 ;; esac
        case "$name_blob" in *"${free}"*) return 0 ;; esac
    fi

    return 1
}

printf 'PR\tBRANCH\tAUTHOR\tTITLE\n' >&2

MATCHES=()
# FETCHED counts every row the query returned, drafts included, so the truncation
# check below reflects what --limit actually consumed. SEEN counts the reviewable
# (non-draft) PRs the filter had to judge.
SEEN=0
FETCHED=0
COMMIT_LOOKUP_FAILED="false"
while IFS=$'\t' read -r NUMBER BRANCH AUTHOR TITLE IS_DRAFT EXACT_BLOB NAME_BLOB; do
    [[ -z "$NUMBER" ]] && continue
    FETCHED=$((FETCHED + 1))
    [[ "$IS_DRAFT" == "1" ]] && continue
    SEEN=$((SEEN + 1))

    if [[ ${#RAW_TERMS[@]} -gt 0 ]]; then
        KEEP="false"
        # Per-term record of whether the list query alone settled this PR, so the
        # escalation below can tell "already matched here" from "still unknown".
        MATCHED_HERE=()
        INDEX=0
        while [[ $INDEX -lt ${#RAW_TERMS[@]} ]]; do
            if term_matches "$INDEX" "$EXACT_BLOB" "$NAME_BLOB"; then
                KEEP="true"
                TERM_HIT[INDEX]="1"
                MATCHED_HERE+=("1")
            else
                MATCHED_HERE+=("0")
            fi
            INDEX=$((INDEX + 1))
        done

        # Escalate to this PR's commit authors while any free-text term is still
        # unsettled for it -- either it did not match here (so KEEP may be wrong)
        # or it has matched no PR at all yet (so its warning may be wrong). Commit
        # authors are the one thing the list query cannot answer, so ANY free-text
        # term -- login, email, or display name -- can cost one request per PR it
        # has not already matched; only @me and @org/team terms are always free.
        # That is the deliberate price of not missing a commit author whose name
        # differs from the PR author's profile name.
        NEED_COMMITS="false"
        if [[ "$HAS_FREE" == "true" ]]; then
            INDEX=0
            while [[ $INDEX -lt ${#RAW_TERMS[@]} ]]; do
                if [[ -n "${TERM_FREE[INDEX]}" ]] \
                   && { [[ "${MATCHED_HERE[INDEX]}" == "0" ]] \
                        || [[ "${TERM_HIT[INDEX]}" == "0" ]]; }; then
                    NEED_COMMITS="true"
                    break
                fi
                INDEX=$((INDEX + 1))
            done
        fi

        # </dev/null keeps gh off the loop's own stdin. The failure flag has to
        # live out here: the command substitution runs in a subshell, so a flag
        # set inside it would be discarded.
        if [[ "$NEED_COMMITS" == "true" ]]; then
            if ! COMMIT_ROW="$(commit_blobs "$NUMBER" </dev/null)"; then
                COMMIT_LOOKUP_FAILED="true"
                COMMIT_ROW=""
            fi
            if [[ -n "$COMMIT_ROW" ]]; then
                IFS=$'\t' read -r C_EXACT C_NAMES <<< "$COMMIT_ROW"
                INDEX=0
                while [[ $INDEX -lt ${#RAW_TERMS[@]} ]]; do
                    if term_matches "$INDEX" "${C_EXACT:-||}" "${C_NAMES:-||}"; then
                        KEEP="true"
                        TERM_HIT[INDEX]="1"
                    fi
                    INDEX=$((INDEX + 1))
                done
            fi
        fi

        [[ "$KEEP" == "true" ]] || continue
    fi

    MATCHES+=("$NUMBER")
    printf '%s\t%s\t%s\t%s\n' "$NUMBER" "$BRANCH" "${AUTHOR:-unknown}" "$TITLE" >&2
done <<< "$PR_ROWS"

if [[ ${#RAW_TERMS[@]} -gt 0 ]]; then
    TERM_LIST=""
    for RAW in "${RAW_TERMS[@]}"; do
        [[ -n "$TERM_LIST" ]] && TERM_LIST="${TERM_LIST}, "
        TERM_LIST="${TERM_LIST}${RAW}"
    done
    if [[ "$SEEN" -gt 0 ]]; then
        info "Author filter: ${TERM_LIST} — kept ${#MATCHES[@]} of ${SEEN} PR(s)"
    fi
    INDEX=0
    while [[ $INDEX -lt ${#RAW_TERMS[@]} ]]; do
        if [[ "${TERM_HIT[INDEX]}" == "0" ]]; then
            warn "no PRs awaiting your review match '${RAW_TERMS[$INDEX]}'"
        fi
        INDEX=$((INDEX + 1))
    done
    # The author filter runs after the query, so a truncated queue can hide
    # matching PRs entirely. Drafts count here: they still occupy a --limit slot.
    if [[ "$FETCHED" -ge "$LIMIT" ]]; then
        warn "your review queue hit the limit of ${LIMIT} before filtering; raise --limit to widen the search"
    fi
fi

# Reported last, after the table and every warning, so a partial result is still
# visible -- but non-zero, because a PR may have been dropped for want of data.
if [[ "$COMMIT_LOOKUP_FAILED" == "true" ]]; then
    error "commit-author lookup failed for one or more PRs; results are incomplete"
fi

if [[ ${#MATCHES[@]} -eq 0 ]]; then
    info "No open, non-draft PRs request your review in ${OWNER_REPO}"
    exit 0
fi

info "Matched ${#MATCHES[@]} PR(s)"
printf '%s\n' "${MATCHES[@]}"
