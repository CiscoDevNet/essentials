#!/bin/bash
# Entry point for /ess-mcp-hide-secrets — run this script only; do not improvise checks in the agent.
#
# Usage:
#   USERNAME=$(whoami) ./run.sh                    # install (migrate if needed, then LaunchAgent)
#   USERNAME=$(whoami) ./run.sh migrate            # ~/.cursor/mcp.json
#   USERNAME=$(whoami) ./run.sh migrate .cursor/mcp.json
#   USERNAME=$(whoami) ./run.sh status
#   USERNAME=$(whoami) ./run.sh preflight
#   ./run.sh fix-launchagents
#
# Write modes (default, migrate, install, fix-launchagents) print the planned
# changes and prompt before writing:
#   --dry-run   print the planned changes and exit without writing
#   --yes, -y   skip the prompt (required when stdin is not a terminal)
#
# Optional:
#   PROJECT_MCP_JSON=/path/to/repo/.cursor/mcp.json ./run.sh
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

if [ -z "${USERNAME:-}" ]; then
  echo "ERROR: set USERNAME (your macOS username)." >&2
  echo "Example: USERNAME=\$(whoami) $0" >&2
  exit 1
fi

DRY_RUN=false
ASSUME_YES=false
MODE=""
MCP_JSON_ARG=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --yes | -y) ASSUME_YES=true ;;
    -*)
      echo "ERROR: unknown option: $arg" >&2
      exit 1
      ;;
    *)
      if [ -z "$MODE" ]; then
        MODE="$arg"
      else
        MCP_JSON_ARG="$arg"
      fi
      ;;
  esac
done
MODE="${MODE:-default}"

# Set by execute: true while building the plan, false while applying it.
PLANNING=false
PREFLIGHT_DONE=false

# Runs a script that writes, adding --dry-run while planning.
# bash so a preview does not need the helper to be executable.
step() {
  if [ "$PLANNING" = true ]; then
    bash "$@" --dry-run
  else
    bash "$@"
  fi
}

preflight_once() {
  if [ "$PREFLIGHT_DONE" = false ]; then
    bash "$SCRIPT_DIR/preflight.sh"
    PREFLIGHT_DONE=true
  fi
}

# Read-only checks that only make sense after a real write.
after_write() {
  if [ "$PLANNING" = false ]; then
    bash "$@"
  fi
}

fix_launchagents_or_exit() {
  if step "$SCRIPT_DIR/fix-launchagents-dir.sh"; then
    return 0
  fi
  echo ""
  echo "Secrets migrated (if any). LaunchAgent step needs sudo in Terminal:"
  echo "  $SCRIPT_DIR/run.sh fix-launchagents"
  echo "  USERNAME=$USERNAME $SCRIPT_DIR/run.sh install"
  after_write "$SCRIPT_DIR/status.sh"
  exit 1
}

mcp_json_paths_need_migrate() {
  local path
  for path in "$@"; do
    [ -f "$path" ] || continue
    if python3 "$CHECK_INLINE_SECRETS" "$path" >/dev/null 2>&1; then
      continue
    fi
    echo "$path"
  done
}

execute() {
  case "$MODE" in
    fix-launchagents)
      step "$SCRIPT_DIR/fix-launchagents-dir.sh"
      ;;
    migrate)
      preflight_once
      step "$SCRIPT_DIR/install.sh" --migrate-only "${MCP_JSON_ARG:-$GLOBAL_MCP_JSON}"
      fix_launchagents_or_exit
      step "$SCRIPT_DIR/install.sh"
      after_write "$SCRIPT_DIR/verify.sh"
      ;;
    install)
      preflight_once
      fix_launchagents_or_exit
      step "$SCRIPT_DIR/install.sh"
      after_write "$SCRIPT_DIR/verify.sh"
      ;;
    default)
      preflight_once

      local paths=("$GLOBAL_MCP_JSON")
      if [ -n "$PROJECT_MCP_JSON" ] && [ -f "$PROJECT_MCP_JSON" ]; then
        paths+=("$PROJECT_MCP_JSON")
      fi

      local dirty_path
      while IFS= read -r dirty_path; do
        [ -n "$dirty_path" ] || continue
        echo ""
        echo "== migrate $dirty_path =="
        step "$SCRIPT_DIR/install.sh" --migrate-only "$dirty_path"
      done < <(mcp_json_paths_need_migrate "${paths[@]}")

      fix_launchagents_or_exit

      echo ""
      echo "== install LaunchAgent =="
      step "$SCRIPT_DIR/install.sh"
      after_write "$SCRIPT_DIR/verify.sh"
      after_write "$SCRIPT_DIR/status.sh"
      ;;
  esac
}

confirm_or_abort() {
  if [ "$ASSUME_YES" = true ]; then
    return 0
  fi
  if [ ! -t 0 ]; then
    echo "ERROR: stdin is not a terminal; review the plan with --dry-run, then rerun with --yes." >&2
    exit 1
  fi
  local answer
  printf '\nApply these changes for %s (LaunchAgent %s)? [y/N] ' "$USERNAME" "$LABEL" >&2
  read -r answer
  case "$answer" in
    y | Y | yes | YES) return 0 ;;
    *)
      echo "Aborted; nothing was written." >&2
      exit 1
      ;;
  esac
}

case "$MODE" in
  status | preflight)
    if [ "$DRY_RUN" = true ] || [ "$ASSUME_YES" = true ]; then
      echo "ERROR: $MODE is read-only; --dry-run and --yes do not apply." >&2
      exit 1
    fi
    exec bash "$SCRIPT_DIR/$MODE.sh"
    ;;
  default | migrate | install | fix-launchagents) ;;
  *)
    echo "ERROR: unknown mode: $MODE" >&2
    echo "Usage: $0 [default|migrate|install|status|preflight|fix-launchagents] [mcp.json] [--dry-run] [--yes]" >&2
    exit 1
    ;;
esac

if [ "$DRY_RUN" = true ] || [ "$ASSUME_YES" = false ]; then
  echo "== plan: $MODE (nothing is written) =="
  PLANNING=true
  execute
  PLANNING=false
  if [ "$DRY_RUN" = true ]; then
    exit 0
  fi
  confirm_or_abort
  echo ""
  echo "== apply: $MODE =="
fi

execute
