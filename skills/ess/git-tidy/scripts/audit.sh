#!/usr/bin/env bash
#
# audit.sh
# Inventory a repo's local branches, remote branches, and worktrees, classify
# each one, and emit a report so cleanup decisions rest on evidence instead of
# on twenty ad-hoc git commands.
#
# Usage:
#   audit.sh [--base <ref>] [--remote <name>] [--output DIR]
#            [--fetch] [--no-gh] [--no-size] [--author <user>] [--pr-limit N]
#
#   --base <ref>     - Integration ref every branch is compared against
#                      (default: first of origin/main, origin/master, main, master)
#   --remote <name>  - Remote to check for live branches (default: origin)
#   --output DIR     - Output directory (default: /tmp/git-tidy-<repo>-<hash>)
#   --fetch          - Run `git fetch --prune <remote>` first (network write to
#                      remote-tracking refs; off by default so the audit is read-only)
#   --no-gh          - Skip all PR lookups; classification degrades conservatively
#   --no-size        - Skip `du` on worktrees (faster on large trees)
#   --author <user>  - Author for the batched PR query (default: @me)
#   --pr-limit N     - Max PRs in the batched query (default: 200)
#
# Environment:
#   GIT_TIDY_PR_FIXTURE - path to a prs.tsv that stands in for the gh queries,
#                         so test_audit.sh can exercise PR categories offline
#
# Writes into DIR:
#   prs.tsv           - batched PR metadata (headRefName, number, state, ...)
#   remote_heads.tsv  - live branches on the remote (from git ls-remote)
#   worktrees.tsv     - classified worktrees
#   branches.tsv      - classified local branches
#   report.json       - machine-readable classification
#   report.md         - human report, ending in ordered remediation commands
#
# This script only reads. It never deletes a branch or a worktree; it prints the
# commands that would. Portable to bash 3.2 (macOS): no associative arrays or
# mapfile. Depends on git, plus gh for PR state (optional).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${SCRIPT_DIR}/lib.sh"

# --- parse args ---------------------------------------------------------------
BASE=""; REMOTE="origin"; OUTPUT_DIR=""; DO_FETCH="false"
USE_GH="true"; DO_SIZE="true"; PR_AUTHOR="@me"; PR_LIMIT="200"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)      BASE="${2:-}"; shift 2 ;;
    --remote)    REMOTE="${2:-}"; shift 2 ;;
    --output)    OUTPUT_DIR="${2:-}"; shift 2 ;;
    --author)    PR_AUTHOR="${2:-}"; shift 2 ;;
    --pr-limit)  PR_LIMIT="${2:-}"; shift 2 ;;
    --fetch)     DO_FETCH="true"; shift ;;
    --no-gh)     USE_GH="false"; shift ;;
    --no-size)   DO_SIZE="false"; shift ;;
    -h|--help)   sed -n '2,37p' "$0"; exit 0 ;;
    *)           error "Unknown argument: $1" ;;
  esac
done

have git || error "git not found on PATH"
require_git_repo

REPO_ROOT="$(repo_root)"
CURRENT_TOPLEVEL="$REPO_ROOT"
cd "$REPO_ROOT"

if [[ "$DO_FETCH" == "true" ]]; then
  info "Fetching ${REMOTE} with --prune"
  git fetch --prune "$REMOTE" >/dev/null 2>&1 || warn "fetch failed; continuing with local refs"
fi

# --- resolve the base ref -----------------------------------------------------
if [[ -n "$BASE" ]]; then
  ref_exists "$BASE" || error "base ref not found: $BASE"
else
  BASE="$(first_existing_ref "${REMOTE}/main" "${REMOTE}/master" "main" "master")" \
    || error "could not resolve a base ref; pass --base <ref>"
fi
BASE_TIP="$(git rev-parse "$BASE")"
BASE_LOCAL="$(strip_remote_prefix "$BASE")"
info "Base ref: ${BASE} (${BASE_TIP:0:9})"

# --- output dir ---------------------------------------------------------------
if [[ -z "$OUTPUT_DIR" ]]; then
  # Only the derived directory is ours to wipe; a caller-supplied one is merely
  # written into, so `--output ~/notes` can never erase the caller's files.
  OUTPUT_DIR="/tmp/git-tidy-$(basename "$REPO_ROOT")-$(hash_str "$REPO_ROOT")"
  rm -rf "$OUTPUT_DIR"
fi
mkdir -p "$OUTPUT_DIR"

PRS_TSV="${OUTPUT_DIR}/prs.tsv"
HEADS_TSV="${OUTPUT_DIR}/remote_heads.tsv"
WORKTREES_TSV="${OUTPUT_DIR}/worktrees.tsv"
BRANCHES_TSV="${OUTPUT_DIR}/branches.tsv"
: > "$PRS_TSV"; : > "$HEADS_TSV"; : > "$WORKTREES_TSV"; : > "$BRANCHES_TSV"

# --- live remote branches (one round trip) ------------------------------------
# `[gone]` in `git for-each-ref` upstream:track is only as fresh as the last
# prune, so ask the remote directly rather than trusting the local marker.
REMOTE_KNOWN="false"
if git remote get-url "$REMOTE" >/dev/null 2>&1; then
  if git ls-remote --heads "$REMOTE" > "${OUTPUT_DIR}/.ls-remote.raw" 2>/dev/null; then
    awk '{ sub(/^refs\/heads\//, "", $2); print $2 "\t" $1 }' \
      "${OUTPUT_DIR}/.ls-remote.raw" > "$HEADS_TSV"
    REMOTE_KNOWN="true"
    info "Live branches on ${REMOTE}: $(wc -l < "$HEADS_TSV" | tr -d ' ')"
  else
    warn "could not reach ${REMOTE}; remote branch state will be reported as unknown"
  fi
  rm -f "${OUTPUT_DIR}/.ls-remote.raw"
else
  warn "remote '${REMOTE}' is not configured; skipping live remote check"
fi

# --- PR metadata (one batched query, targeted fallbacks) ----------------------
# One `gh pr list --author` call covers your own branches. Branches it misses
# (someone else's work you checked out) get a targeted --head lookup each, so
# the common case stays at a single round trip.
GH_OK="false"
PR_FIXTURE="${GIT_TIDY_PR_FIXTURE:-}"
if [[ -n "$PR_FIXTURE" ]]; then
  # Test seam: a pre-built prs.tsv stands in for gh so test_audit.sh can
  # exercise the PR-dependent categories offline.
  [[ -f "$PR_FIXTURE" ]] || error "GIT_TIDY_PR_FIXTURE not found: $PR_FIXTURE"
  cp "$PR_FIXTURE" "$PRS_TSV"
  GH_OK="true"
  info "PR fixture: ${PR_FIXTURE} ($(wc -l < "$PRS_TSV" | tr -d ' ') records)"
elif [[ "$USE_GH" == "true" ]] && have gh; then
  if gh pr list --author "$PR_AUTHOR" --state all --limit "$PR_LIMIT" \
      --json number,headRefName,headRefOid,state,mergedAt,url \
      --jq '.[] | [.headRefName, (.number|tostring), .state, (.mergedAt // "-"), .headRefOid, .url] | @tsv' \
      > "$PRS_TSV" 2>/dev/null; then
    GH_OK="true"
    info "Batched PR records: $(wc -l < "$PRS_TSV" | tr -d ' ')"
  else
    warn "gh PR query failed; continuing without PR state"
    : > "$PRS_TSV"
  fi
elif [[ "$USE_GH" == "true" ]]; then
  warn "gh not found on PATH; continuing without PR state"
fi

# Echo the best PR row for a branch: OPEN wins, else newest MERGED, else CLOSED.
pr_row_for_branch() {
  local branch="$1"
  awk -F'\t' -v b="$branch" '
    $1 == b {
      rank = ($3 == "OPEN") ? 3 : ($3 == "MERGED") ? 2 : 1
      key = rank "\t" $4
      if (rank > best_rank || (rank == best_rank && $4 > best_date)) {
        best_rank = rank; best_date = $4; best = $0
      }
    }
    END { if (best != "") print best }
  ' "$PRS_TSV"
}

# Echo the PR row whose head commit is <sha>, for detached worktrees.
pr_row_for_commit() {
  awk -F'\t' -v s="$1" '$5 == s { print; exit }' "$PRS_TSV"
}

# Resolve a bare commit to its PR. Detached worktrees left behind by review
# tooling usually sit on someone else's PR head, which the --author query never
# sees. The commits API answers "which PR contains this commit" directly, so the
# worktree is classified from the commit rather than from its directory name.
fill_pr_gap_for_commit() {
  local sha="$1" fields
  [[ -n "$(pr_row_for_commit "$sha")" ]] && return 0
  fields="$(gh api "repos/{owner}/{repo}/commits/${sha}/pulls" --jq '
    map(select(.number))
    | sort_by(if .state == "open" then 0 else 1 end)
    | if length > 0 then
        .[0] | [.head.ref, (.number|tostring),
                (if .merged_at then "MERGED" elif .state == "open" then "OPEN" else "CLOSED" end),
                (.merged_at // "-"), .html_url] | @tsv
      else empty end' 2>/dev/null)" || return 0
  [[ -n "$fields" ]] || return 0
  # Re-key on the commit we asked about: the PR head may have moved on since
  # this worktree was created, and the lookup matches on that exact sha.
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(echo "$fields" | cut -f1)" "$(echo "$fields" | cut -f2)" \
    "$(echo "$fields" | cut -f3)" "$(echo "$fields" | cut -f4)" \
    "$sha" "$(echo "$fields" | cut -f5)" >> "$PRS_TSV"
}

# Fill gaps in the batched query with one targeted lookup per unmatched branch.
fill_pr_gaps() {
  local branch row
  while IFS= read -r branch; do
    [[ -n "$branch" ]] || continue
    [[ "$branch" == "$BASE_LOCAL" ]] && continue
    row="$(pr_row_for_branch "$branch")"
    [[ -n "$row" ]] && continue
    gh pr list --head "$branch" --state all --limit 10 \
      --json number,headRefName,headRefOid,state,mergedAt,url \
      --jq '.[] | [.headRefName, (.number|tostring), .state, (.mergedAt // "-"), .headRefOid, .url] | @tsv' \
      >> "$PRS_TSV" 2>/dev/null || true
  done < <(git for-each-ref --format='%(refname:short)' refs/heads)
}
[[ "$GH_OK" == "true" && -z "$PR_FIXTURE" ]] && fill_pr_gaps

# --- worktree inventory -------------------------------------------------------
# Parse the porcelain records into: path, head, branch, detached, locked, prunable.
# The main working tree is always listed first.
# Every field is emitted non-empty ("-" when absent): with a tab IFS, bash
# collapses runs of whitespace delimiters, so an empty middle field would shift
# every later column left when the row is read back.
parse_worktrees() {
  local path="" head="" branch="" detached=0 locked=0 prunable=0 line
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      "worktree "*) path="${line#worktree }" ;;
      "HEAD "*)     head="${line#HEAD }" ;;
      "branch "*)   branch="${line#branch refs/heads/}" ;;
      "detached")   detached=1 ;;
      "locked"*)    locked=1 ;;
      "prunable"*)  prunable=1 ;;
      "")
        if [[ -n "$path" ]]; then
          printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$path" "${head:--}" "${branch:--}" "$detached" "$locked" "$prunable"
        fi
        path=""; head=""; branch=""; detached=0; locked=0; prunable=0
        ;;
    esac
  done
  if [[ -n "$path" ]]; then
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$path" "${head:--}" "${branch:--}" "$detached" "$locked" "$prunable"
  fi
}
git worktree list --porcelain | parse_worktrees > "${OUTPUT_DIR}/.worktrees.raw"

PRIMARY_WORKTREE="$(head -1 "${OUTPUT_DIR}/.worktrees.raw" | cut -f1)"

# Detached worktrees carry no branch name, so resolve their commits to PRs now,
# while the PR table is still being assembled.
if [[ "$GH_OK" == "true" && -z "$PR_FIXTURE" ]]; then
  while IFS= read -r wt_head; do
    [[ -n "$wt_head" ]] && fill_pr_gap_for_commit "$wt_head"
  done < <(awk -F'\t' '$3 == "-" && $2 != "-" && $6 == "0" { print $2 }' \
    "${OUTPUT_DIR}/.worktrees.raw")
fi

# Echo the worktree path holding <branch>, if any.
worktree_for_branch() {
  awk -F'\t' -v b="$1" '$3 == b { print $1; exit }' "${OUTPUT_DIR}/.worktrees.raw"
}

# --- classify branches --------------------------------------------------------
# Columns: name tip category disposition ahead behind remote pr_number pr_state
#          pr_match worktree superseded_by date notes
CURRENT_BRANCH="$(git symbolic-ref --short -q HEAD || echo "")"

classify_branches() {
  local name tip date subject
  local counts ahead behind remote_state pr_row pr_number pr_state
  local pr_head pr_match category disposition worktree superseded notes other

  while IFS=$'\t' read -r name tip date subject; do
    [[ -n "$name" ]] || continue

    counts="$(git rev-list --left-right --count "${BASE}...${name}")"
    behind="$(echo "$counts" | cut -f1)"
    ahead="$(echo "$counts" | cut -f2)"

    if [[ "$REMOTE_KNOWN" == "true" ]]; then
      if [[ -n "$(tsv_lookup "$HEADS_TSV" 1 "$name")" ]]; then
        remote_state="live"
      else
        remote_state="absent"
      fi
    else
      remote_state="unknown"
    fi

    pr_row="$(pr_row_for_branch "$name")"
    if [[ -n "$pr_row" ]]; then
      pr_number="$(tsv_field "$pr_row" 2)"
      pr_state="$(tsv_field "$pr_row" 3)"
      pr_head="$(tsv_field "$pr_row" 5)"
      if [[ "$pr_head" == "$tip" ]]; then pr_match="yes"; else pr_match="no"; fi
    else
      pr_number="-"; pr_state="-"; pr_head="-"; pr_match="-"
    fi

    worktree="$(worktree_for_branch "$name")"
    [[ -n "$worktree" ]] || worktree="-"
    superseded="-"
    notes=""

    # --- the decision -------------------------------------------------------
    if [[ "$name" == "$BASE_LOCAL" ]]; then
      category="base"; disposition="keep"
      notes="local base branch"
    elif [[ "$ahead" -eq 0 && "$behind" -eq 0 ]]; then
      # Identical to base: almost always a branch just created to start work.
      category="fresh-start"; disposition="ask"
      notes="identical to ${BASE}; likely new work not yet committed"
    elif [[ "$ahead" -eq 0 ]]; then
      category="merged-ancestor"; disposition="safe-d"
      notes="fully contained in ${BASE}"
    elif [[ "$pr_state" == "OPEN" ]]; then
      category="pr-open"; disposition="keep"
      notes="PR #${pr_number} is open"
    elif [[ "$pr_state" == "MERGED" && "$pr_match" == "yes" ]]; then
      category="pr-merged-verified"; disposition="safe-D"
      notes="tip matches merged PR #${pr_number} head; squashed into ${BASE}"
    elif [[ "$pr_state" == "MERGED" ]]; then
      category="pr-merged-diverged"; disposition="ask"
      notes="PR #${pr_number} merged but tip moved since; ${ahead} commit(s) not in ${BASE}"
    else
      # No PR, or a closed-unmerged one: the commits are not in base.
      category="unmerged-no-pr"; disposition="keep"
      if [[ "$pr_state" == "CLOSED" ]]; then
        notes="PR #${pr_number} closed without merging; ${ahead} commit(s) not in ${BASE}"
      else
        notes="${ahead} commit(s) not in ${BASE}, no PR found"
      fi
      # Only worth the O(n^2) ancestor scan for branches we would otherwise keep.
      while IFS= read -r other; do
        [[ -n "$other" && "$other" != "$name" ]] || continue
        if git merge-base --is-ancestor "$name" "$other" 2>/dev/null; then
          superseded="$other"
          category="superseded"; disposition="ask"
          notes="fully contained in local branch '${other}'"
          break
        fi
      done < <(git for-each-ref --format='%(refname:short)' refs/heads)
    fi

    if [[ "$name" == "$CURRENT_BRANCH" ]]; then
      notes="${notes}; current checkout"
    fi

    # `notes` is always non-empty and `subject` is last, so no field can collapse.
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$name" "$tip" "$category" "$disposition" "$ahead" "$behind" \
      "$remote_state" "$pr_number" "$pr_state" "$pr_match" "$worktree" \
      "$superseded" "$date" "$notes" "$subject"
  done < <(git for-each-ref --sort=refname \
    --format='%(refname:short)%09%(objectname)%09%(committerdate:short)%09%(subject)' \
    refs/heads)
}
classify_branches > "$BRANCHES_TSV"
info "Classified branches: $(wc -l < "$BRANCHES_TSV" | tr -d ' ')"

# Echo the disposition recorded for <branch>.
branch_disposition() {
  local row; row="$(tsv_lookup "$BRANCHES_TSV" 1 "$1")"
  [[ -n "$row" ]] && tsv_field "$row" 4 || echo "-"
}

# --- classify worktrees -------------------------------------------------------
# Columns: path head branch category disposition size_kb notes
classify_worktrees() {
  local path head branch detached locked prunable
  local category disposition size_kb notes dispo pr_row pr_state pr_number

  while IFS=$'\t' read -r path head branch detached locked prunable; do
    [[ -n "$path" ]] || continue
    size_kb=0; notes=""

    if [[ "$DO_SIZE" == "true" && -d "$path" ]]; then
      size_kb="$(du -sk "$path" 2>/dev/null | awk '{print $1}')"
      [[ -n "$size_kb" ]] || size_kb=0
    fi

    if [[ "$prunable" == "1" || ! -d "$path" ]]; then
      category="prunable"; disposition="safe-prune"
      notes="directory is gone; only the registration remains"
    elif [[ "$path" == "$PRIMARY_WORKTREE" ]]; then
      category="primary"; disposition="keep"
      notes="main working tree"
    elif [[ "$path" == "$CURRENT_TOPLEVEL" ]]; then
      category="current"; disposition="keep"
      notes="you are standing in this worktree"
    elif [[ "$locked" == "1" ]]; then
      category="locked"; disposition="keep"
      notes="locked; unlock deliberately before touching"
    elif [[ -n "$(git -C "$path" status --porcelain 2>/dev/null)" ]]; then
      category="dirty"; disposition="keep"
      notes="uncommitted changes; never remove automatically"
    elif [[ "$branch" != "-" ]]; then
      dispo="$(branch_disposition "$branch")"
      case "$dispo" in
        safe-d|safe-D)
          category="stale-merged"; disposition="safe-remove"
          notes="holds '${branch}', whose work is already in ${BASE}" ;;
        ask)
          category="ask"; disposition="ask"
          notes="holds '${branch}', which needs a decision first" ;;
        *)
          category="active"; disposition="keep"
          notes="holds '${branch}', still in use" ;;
      esac
    else
      # Detached: decide from the commit itself, not from the directory name.
      if git merge-base --is-ancestor "$head" "$BASE" 2>/dev/null; then
        category="stale-merged"; disposition="safe-remove"
        notes="detached at a commit already in ${BASE}"
      else
        pr_row="$(pr_row_for_commit "$head")"
        if [[ -n "$pr_row" ]]; then
          pr_number="$(tsv_field "$pr_row" 2)"
          pr_state="$(tsv_field "$pr_row" 3)"
          if [[ "$pr_state" == "OPEN" ]]; then
            category="active-open-pr"; disposition="ask"
            notes="detached at the head of open PR #${pr_number}"
          else
            category="stale-merged"; disposition="safe-remove"
            notes="detached at the head of ${pr_state} PR #${pr_number}"
          fi
        else
          category="unknown"; disposition="ask"
          notes="detached at a commit not in ${BASE} and not matched to a PR"
        fi
      fi
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$path" "${head:0:9}" "${branch:--}" "$category" "$disposition" "$size_kb" "$notes"
  done < "${OUTPUT_DIR}/.worktrees.raw"
}
classify_worktrees > "$WORKTREES_TSV"
info "Classified worktrees: $(wc -l < "$WORKTREES_TSV" | tr -d ' ')"

# --- helpers for reporting ----------------------------------------------------
count_branches() { awk -F'\t' -v d="$1" '$4 == d' "$BRANCHES_TSV" | wc -l | tr -d ' '; }
count_worktrees() { awk -F'\t' -v d="$1" '$5 == d' "$WORKTREES_TSV" | wc -l | tr -d ' '; }
branches_with() { awk -F'\t' -v d="$1" '$4 == d { print $1 }' "$BRANCHES_TSV"; }
worktrees_with() { awk -F'\t' -v d="$1" '$5 == d { print $1 }' "$WORKTREES_TSV"; }

RECLAIMABLE_KB="$(awk -F'\t' '$5 == "safe-remove" { s += $6 } END { print s + 0 }' "$WORKTREES_TSV")"
GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- report.md ----------------------------------------------------------------
{
  echo "# git-tidy report"
  echo
  echo "- Repo: \`${REPO_ROOT}\`"
  echo "- Base: \`${BASE}\` (\`${BASE_TIP:0:9}\`)"
  echo "- Remote: \`${REMOTE}\` (live check: ${REMOTE_KNOWN})"
  echo "- PR state: $([[ "$GH_OK" == "true" ]] && echo "from gh" || echo "unavailable - classification is conservative")"
  echo "- Generated: ${GENERATED_AT}"
  echo
  echo "## Summary"
  echo
  echo "| Bucket | Branches | Worktrees |"
  echo "| ------ | -------- | --------- |"
  echo "| Safe to remove | $(( $(count_branches safe-d) + $(count_branches safe-D) )) | $(( $(count_worktrees safe-remove) + $(count_worktrees safe-prune) )) |"
  echo "| Ask first | $(count_branches ask) | $(count_worktrees ask) |"
  echo "| Keep | $(count_branches keep) | $(count_worktrees keep) |"
  echo
  [[ "$RECLAIMABLE_KB" -gt 0 ]] && echo "Reclaimable worktree disk: **$(human_size "$RECLAIMABLE_KB")**" && echo

  echo "## Branches"
  echo
  echo "| Branch | Category | Disposition | Ahead | Behind | Remote | PR | Notes |"
  echo "| ------ | -------- | ----------- | ----- | ------ | ------ | -- | ----- |"
  while IFS=$'\t' read -r name tip category disposition ahead behind remote pr_number pr_state pr_match worktree superseded date notes subject; do
    [[ -n "$name" ]] || continue
    if [[ "$pr_number" == "-" ]]; then pr_cell="-"; else pr_cell="#${pr_number} ${pr_state}"; fi
    echo "| \`${name}\` | ${category} | ${disposition} | ${ahead} | ${behind} | ${remote} | ${pr_cell} | ${notes} |"
  done < "$BRANCHES_TSV"
  echo

  echo "## Worktrees"
  echo
  echo "| Path | Branch | Category | Disposition | Size | Notes |"
  echo "| ---- | ------ | -------- | ----------- | ---- | ----- |"
  while IFS=$'\t' read -r path head branch category disposition size_kb notes; do
    [[ -n "$path" ]] || continue
    echo "| \`${path}\` | ${branch} | ${category} | ${disposition} | $(human_size "$size_kb") | ${notes} |"
  done < "$WORKTREES_TSV"
  echo

  echo "## Remediation"
  echo
  echo "Run these in order. Worktrees must be released before the branches they"
  echo "hold can be deleted, and you cannot remove the worktree you are standing in."
  echo

  NEEDS_CHECKOUT="false"
  if [[ -n "$CURRENT_BRANCH" ]]; then
    cur_dispo="$(branch_disposition "$CURRENT_BRANCH")"
    [[ "$cur_dispo" == "safe-d" || "$cur_dispo" == "safe-D" ]] && NEEDS_CHECKOUT="true"
  fi

  echo "### Safe"
  echo
  if [[ "$(count_branches safe-d)" -eq 0 && "$(count_branches safe-D)" -eq 0 \
        && "$(count_worktrees safe-remove)" -eq 0 && "$(count_worktrees safe-prune)" -eq 0 ]]; then
    echo "Nothing to do."
    echo
  else
    echo '```bash'
    if [[ "$NEEDS_CHECKOUT" == "true" ]]; then
      printf 'git checkout %q   # release the branch you are on\n' "$BASE_LOCAL"
    fi
    worktrees_with safe-remove | while IFS= read -r p; do
      [[ -n "$p" ]] && echo "git worktree remove \"${p}\""
    done
    if [[ "$(count_worktrees safe-prune)" -gt 0 ]]; then
      echo "git worktree prune   # drops $(count_worktrees safe-prune) registration(s) whose directory is gone"
    fi
    branches_with safe-d | while IFS= read -r branch; do
      [[ -n "$branch" ]] || continue
      printf 'git branch -d -- %q\n' "$branch"
    done
    branches_with safe-D | while IFS= read -r branch; do
      [[ -n "$branch" ]] || continue
      printf 'git branch -D -- %q   # squash-merged: -d cannot verify these\n' "$branch"
    done
    echo '```'
    echo
  fi

  echo "### Ask first"
  echo
  if [[ "$(count_branches ask)" -eq 0 && "$(count_worktrees ask)" -eq 0 ]]; then
    echo "Nothing pending."
  else
    while IFS=$'\t' read -r name tip category disposition ahead behind remote pr_number pr_state pr_match worktree superseded date notes subject; do
      [[ "$disposition" == "ask" ]] || continue
      echo "- \`${name}\` (${category}) - ${notes}"
      echo "  - last commit: ${date} \"${subject}\""
      echo "  - inspect: \`git log --oneline ${BASE}..${name}\`"
      [[ "$worktree" != "-" ]] && echo "  - held by worktree: \`${worktree}\`"
    done < "$BRANCHES_TSV"
    while IFS=$'\t' read -r path head branch category disposition size_kb notes; do
      [[ "$disposition" == "ask" ]] || continue
      echo "- \`${path}\` (${category}) - ${notes}"
    done < "$WORKTREES_TSV"
  fi
  echo

  echo "### Keep"
  echo
  branches_with keep | while IFS= read -r b; do
    [[ -n "$b" ]] && echo "- \`${b}\`"
  done
  echo
  echo "---"
  echo
  echo "Deleting a local branch never deletes its remote counterpart. Remote"
  echo "deletion is a separate step and needs its own approval."
} > "${OUTPUT_DIR}/report.md"

# --- report.json --------------------------------------------------------------
{
  echo "{"
  echo "  \"generated_at\": \"${GENERATED_AT}\","
  echo "  \"repo_root\": \"$(json_escape "$REPO_ROOT")\","
  echo "  \"base\": \"$(json_escape "$BASE")\","
  echo "  \"base_tip\": \"${BASE_TIP}\","
  echo "  \"remote\": \"$(json_escape "$REMOTE")\","
  echo "  \"remote_checked\": ${REMOTE_KNOWN},"
  echo "  \"pr_data\": ${GH_OK},"
  echo "  \"current_branch\": \"$(json_escape "$CURRENT_BRANCH")\","
  echo "  \"reclaimable_kb\": ${RECLAIMABLE_KB},"
  echo "  \"branches\": ["
  first=1
  while IFS=$'\t' read -r name tip category disposition ahead behind remote pr_number pr_state pr_match worktree superseded date notes subject; do
    [[ -n "$name" ]] || continue
    [[ $first -eq 0 ]] && echo ","
    first=0
    printf '    {"name": "%s", "tip": "%s", "category": "%s", "disposition": "%s", "ahead": %s, "behind": %s, "remote": "%s", "pr_number": "%s", "pr_state": "%s", "pr_head_match": "%s", "worktree": "%s", "superseded_by": "%s", "last_commit": "%s", "notes": "%s", "subject": "%s"}' \
      "$(json_escape "$name")" "$tip" "$category" "$disposition" "$ahead" "$behind" \
      "$remote" "$pr_number" "$pr_state" "$pr_match" "$(json_escape "$worktree")" \
      "$(json_escape "$superseded")" "$date" "$(json_escape "$notes")" "$(json_escape "$subject")"
  done < "$BRANCHES_TSV"
  echo
  echo "  ],"
  echo "  \"worktrees\": ["
  first=1
  while IFS=$'\t' read -r path head branch category disposition size_kb notes; do
    [[ -n "$path" ]] || continue
    [[ $first -eq 0 ]] && echo ","
    first=0
    printf '    {"path": "%s", "head": "%s", "branch": "%s", "category": "%s", "disposition": "%s", "size_kb": %s, "notes": "%s"}' \
      "$(json_escape "$path")" "$head" "$(json_escape "$branch")" "$category" \
      "$disposition" "$size_kb" "$(json_escape "$notes")"
  done < "$WORKTREES_TSV"
  echo
  echo "  ]"
  echo "}"
} > "${OUTPUT_DIR}/report.json"

rm -f "${OUTPUT_DIR}/.worktrees.raw"

info "Report: ${OUTPUT_DIR}/report.md"
echo "${OUTPUT_DIR}"
