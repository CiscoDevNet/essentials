#!/usr/bin/env bash
set -euo pipefail

review_pr() {
  local repo_root
  if ! repo_root=$(git rev-parse --show-toplevel 2>/dev/null); then
    echo "Error: not inside a git repository." >&2
    return 1
  fi

  local branch_name
  branch_name=$(git rev-parse --abbrev-ref HEAD)
  local safe_branch="${branch_name//\//-}"
  local marker_dir="${repo_root}/.cursor/.review-code-with-copilot"
  local state_file="${marker_dir}/${safe_branch}"

  local use_since_last="false"
  local manual_since=""
  local manual_range=""
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
  local needs_fetch="false"

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
        echo "Warning: last-reviewed commit '$last_sha' not found. Falling back to origin/main." >&2
        needs_fetch="true"
      fi
    else
      needs_fetch="true"
    fi
  else
    needs_fetch="true"
  fi

  if [[ "$needs_fetch" == "true" ]]; then
    git fetch origin 2>&1 || return 1
  fi

  if [[ -z "${diff_range:-}" ]]; then
    if ! git rev-parse --verify origin/main >/dev/null 2>&1; then
      echo "Error: origin/main not found. Is the remote configured?" >&2
      return 1
    fi
    diff_range="origin/main...${reviewed_sha}"
    prompt_scope="this branch against origin/main"
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
