#!/bin/bash
# Read-only status for mcp-hide-secrets. Never reads or prints secret values.
#
# Usage:
#   ./status.sh
#   PROJECT_MCP_JSON=/path/to/.cursor/mcp.json ./status.sh
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

"$SCRIPT_DIR/preflight.sh"

echo ""
echo "== LaunchAgent =="

if [ -f "$PLIST_DEST" ]; then
  echo "OK: plist $PLIST_DEST"
else
  echo "WARN: plist missing ($PLIST_DEST)"
fi

if launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
  echo "OK: agent loaded ($LABEL)"
  launchctl print "$GUI_DOMAIN/$LABEL" 2>/dev/null | head -5 || true
else
  echo "WARN: agent not loaded ($GUI_DOMAIN/$LABEL)"
fi

echo ""
echo "== Session env (key names only) =="

if [ ! -f "$MCP_ENV" ]; then
  echo "WARN: no $MCP_ENV"
  exit 0
fi

while IFS= read -r key; do
  [ -n "$key" ] || continue
  value="$(launchctl getenv "$key" 2>/dev/null || true)"
  if [ -n "$value" ]; then
    echo "OK: $key is set in GUI session"
  else
    echo "WARN: $key is empty in GUI session"
  fi
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$MCP_ENV" | cut -d= -f1)

echo ""
echo "== Loader log (last 5 lines) =="
if [ -f "$LOG_FILE" ]; then
  tail -5 "$LOG_FILE"
else
  echo "(no $LOG_FILE yet)"
fi
