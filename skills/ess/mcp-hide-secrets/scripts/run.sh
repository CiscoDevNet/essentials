#!/bin/bash
# Entry point for /mcp-hide-secrets — run this script only; do not improvise checks in the agent.
#
# Usage:
#   USERNAME=$(whoami) ./run.sh                    # install (migrate if needed, then LaunchAgent)
#   USERNAME=$(whoami) ./run.sh migrate            # ~/.cursor/mcp.json
#   USERNAME=$(whoami) ./run.sh migrate .cursor/mcp.json
#   USERNAME=$(whoami) ./run.sh status
#   USERNAME=$(whoami) ./run.sh preflight
#   ./run.sh fix-launchagents
#
# Optional:
#   PROJECT_MCP_JSON=/path/to/repo/.cursor/mcp.json ./run.sh
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR/check-inline-secrets.py" 2>/dev/null || true

if [ -z "${USERNAME:-}" ]; then
  echo "ERROR: set USERNAME (your macOS username)." >&2
  echo "Example: USERNAME=\$(whoami) $0" >&2
  exit 1
fi

MODE="${1:-default}"
shift || true

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

case "$MODE" in
  status)
    exec "$SCRIPT_DIR/status.sh"
    ;;
  preflight)
    exec "$SCRIPT_DIR/preflight.sh"
    ;;
  fix-launchagents)
    exec "$SCRIPT_DIR/fix-launchagents-dir.sh"
    ;;
  migrate)
    MCP_JSON="${1:-$GLOBAL_MCP_JSON}"
    "$SCRIPT_DIR/preflight.sh"
    "$SCRIPT_DIR/install.sh" --migrate-only "$MCP_JSON"
    if ! "$SCRIPT_DIR/fix-launchagents-dir.sh"; then
      echo ""
      echo "Next: run $SCRIPT_DIR/fix-launchagents-dir.sh in Terminal (sudo), then:"
      echo "  USERNAME=$USERNAME $SCRIPT_DIR/run.sh install"
      exit 1
    fi
    "$SCRIPT_DIR/install.sh"
    "$SCRIPT_DIR/verify.sh"
    ;;
  install)
    "$SCRIPT_DIR/preflight.sh"
    if ! "$SCRIPT_DIR/fix-launchagents-dir.sh"; then
      echo ""
      echo "Next: run $SCRIPT_DIR/fix-launchagents-dir.sh in Terminal (sudo), then:"
      echo "  USERNAME=$USERNAME $SCRIPT_DIR/run.sh install"
      exit 1
    fi
    "$SCRIPT_DIR/install.sh"
    "$SCRIPT_DIR/verify.sh"
    ;;
  default)
    "$SCRIPT_DIR/preflight.sh"

    paths=("$GLOBAL_MCP_JSON")
    if [ -n "$PROJECT_MCP_JSON" ] && [ -f "$PROJECT_MCP_JSON" ]; then
      paths+=("$PROJECT_MCP_JSON")
    fi

    while IFS= read -r dirty_path; do
      [ -n "$dirty_path" ] || continue
      echo ""
      echo "== migrate $dirty_path =="
      "$SCRIPT_DIR/install.sh" --migrate-only "$dirty_path"
    done < <(mcp_json_paths_need_migrate "${paths[@]}")

    if ! "$SCRIPT_DIR/fix-launchagents-dir.sh"; then
      echo ""
      echo "Secrets migrated (if any). LaunchAgent step needs sudo in Terminal:"
      echo "  $SCRIPT_DIR/fix-launchagents-dir.sh"
      echo "  USERNAME=$USERNAME $SCRIPT_DIR/run.sh install"
      "$SCRIPT_DIR/status.sh"
      exit 1
    fi

    echo ""
    echo "== install LaunchAgent =="
    "$SCRIPT_DIR/install.sh"
    "$SCRIPT_DIR/verify.sh"
    "$SCRIPT_DIR/status.sh"
    ;;
  *)
    echo "ERROR: unknown mode: $MODE" >&2
    echo "Usage: $0 [default|migrate|install|status|preflight|fix-launchagents] [mcp.json]" >&2
    exit 1
    ;;
esac
