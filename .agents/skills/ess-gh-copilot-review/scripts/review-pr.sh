#!/usr/bin/env bash
set -euo pipefail

# Prints the remote to compare against: origin if it exists, else the only remote.
get_review_remote() {
  local remotes
  remotes=$(git remote)
  if grep -qx origin <<<"$remotes"; then
    echo origin
    return 0
  fi
  if [[ -n "$remotes" && $(grep -c . <<<"$remotes") -eq 1 ]]; then
    echo "$remotes"
    return 0
  fi
  return 1
}

# Prints the remote's default branch as "<remote>/<branch>", from its HEAD ref
# when the clone recorded one, else main or master.
get_default_base() {
  local remote="$1"
  local head_ref
  if head_ref=$(git symbolic-ref --quiet --short "refs/remotes/${remote}/HEAD" 2>/dev/null); then
    echo "$head_ref"
    return 0
  fi
  local candidate
  for candidate in main master; do
    if git rev-parse --verify --quiet "refs/remotes/${remote}/${candidate}" >/dev/null; then
      echo "${remote}/${candidate}"
      return 0
    fi
  done
  return 1
}

review_pr() {
  if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "Error: not inside a git repository." >&2
    return 1
  fi

  local branch_name
  branch_name=$(git rev-parse --abbrev-ref HEAD)
  local safe_branch="${branch_name//\//-}"
  # Named branches share one marker. Detached checkouts all report HEAD, so each
  # keeps its marker in that worktree's git directory instead of the common one.
  local git_dir_flag="--git-common-dir"
  if [[ "$branch_name" == "HEAD" ]]; then
    git_dir_flag="--git-dir"
  fi
  local marker_dir
  marker_dir="$(git rev-parse --path-format=absolute "$git_dir_flag")/.ess-gh-copilot-review"
  local state_file="${marker_dir}/${safe_branch}"

  local use_since_last="false"
  local manual_since=""
  local manual_range=""
  local manual_base=""
  local reset_last="false"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --since-last)
        use_since_last="true"
        shift
        ;;
      --since)
        if [[ $# -lt 2 ]]; then
          echo "Error: --since requires a git revision." >&2
          return 1
        fi
        manual_since="$2"
        shift 2
        ;;
      --range)
        if [[ $# -lt 2 ]]; then
          echo "Error: --range requires a git revision range." >&2
          return 1
        fi
        manual_range="$2"
        shift 2
        ;;
      --base)
        if [[ $# -lt 2 ]]; then
          echo "Error: --base requires a git ref." >&2
          return 1
        fi
        manual_base="$2"
        shift 2
        ;;
      --reset-last)
        reset_last="true"
        shift
        ;;
      *)
        echo "Error: Unknown argument: $1" >&2
        return 1
        ;;
    esac
  done

  if ! command -v copilot >/dev/null 2>&1; then
    cat >&2 <<'ERR'
Error: GitHub Copilot CLI is not installed.

Install it using one of:
  brew install copilot-cli          # macOS/Linux (Homebrew)
  npm install -g @github/copilot    # Cross-platform (Node.js 22+)
  winget install GitHub.Copilot     # Windows (WinGet)

See: https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-getting-started
ERR
    return 1
  fi

  local reviewed_sha
  reviewed_sha=$(git rev-parse HEAD)

  local diff_range
  local prompt_scope
  local needs_base="false"

  if [[ -n "$manual_range" ]]; then
    diff_range="$manual_range"
    prompt_scope="the range ${manual_range}"
  elif [[ -n "$manual_since" ]]; then
    if ! git rev-parse --verify "$manual_since" >/dev/null 2>&1; then
      echo "Error: revision '$manual_since' not found." >&2
      return 1
    fi
    diff_range="${manual_since}..${reviewed_sha}"
    prompt_scope="changes since ${manual_since}"
  elif [[ "$use_since_last" == "true" && "$reset_last" != "true" ]]; then
    if [[ -f "$state_file" ]]; then
      local last_sha
      last_sha=$(cat "$state_file")
      if git rev-parse --verify "$last_sha" >/dev/null 2>&1; then
        diff_range="${last_sha}..${reviewed_sha}"
        prompt_scope="changes since ${last_sha}"
      else
        echo "Warning: last-reviewed commit '$last_sha' not found. Falling back to the default branch." >&2
        needs_base="true"
      fi
    else
      needs_base="true"
    fi
  else
    needs_base="true"
  fi

  if [[ "$needs_base" == "true" ]]; then
    local remote=""
    local base
    if [[ -n "$manual_base" ]]; then
      base="$manual_base"
      # Fetch only when the base is a remote-tracking ref. Accept both
      # upstream/develop and refs/remotes/upstream/develop.
      local remote_base="${manual_base#refs/remotes/}"
      if git remote | grep -qx "${remote_base%%/*}"; then
        remote="${remote_base%%/*}"
      fi
    else
      if ! remote=$(get_review_remote); then
        echo "Error: no single remote to compare against; pass --base <ref>." >&2
        return 1
      fi
    fi

    if [[ -n "$remote" ]]; then
      git fetch "$remote" 2>&1 || return 1
    fi

    if [[ -z "$manual_base" ]] && ! base=$(get_default_base "$remote"); then
      echo "Error: cannot find the default branch of '${remote}'; pass --base <ref>." >&2
      return 1
    fi
    if ! git rev-parse --verify --quiet "$base" >/dev/null; then
      echo "Error: base '${base}' not found." >&2
      return 1
    fi
    diff_range="${base}...${reviewed_sha}"
    prompt_scope="current branch against ${base}"
  fi

  git diff --stat "$diff_range"

  local prompt
  prompt="/review Review the ${prompt_scope}.
Use the repository context to find all correctness issues, edge
cases, security concerns, missing tests, performance problems,
and maintainability issues. Be exhaustive and do not stop at the
first few findings."

  if ! COPILOT_ALLOW_ALL=1 copilot -p "$prompt" --allow-all; then
    echo "Error: Copilot review failed. Review marker not updated." >&2
    return 1
  fi

  if [[ "${reset_last}" == "true" ]]; then
    rm -f "$state_file"
  fi
  mkdir -p "$marker_dir"
  echo "$reviewed_sha" >"$state_file"
}

# Run only when executed directly. Sourcing just loads the function.
# This is the "main guard" pattern.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  review_pr "$@"
fi
