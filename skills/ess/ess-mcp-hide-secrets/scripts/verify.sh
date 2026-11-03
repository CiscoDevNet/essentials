#!/bin/bash
# Post-install verification. Never prints secret values.
#
# Usage:
#   ./verify.sh
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

sample_key=""
if [ -f "$MCP_ENV" ]; then
  sample_key="$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$MCP_ENV" | head -1 | cut -d= -f1 || true)"
fi

if [ -n "$sample_key" ]; then
  value="$(launchctl getenv "$sample_key" 2>/dev/null || true)"
  if [ -n "$value" ]; then
    echo "OK: $sample_key is set in the GUI session."
  else
    echo "WARN: $sample_key is empty — check $MCP_ENV and $LOG_FILE"
  fi
elif [ -f "$MCP_ENV" ]; then
  echo "WARN: no keys in $MCP_ENV — add secrets before restarting Cursor."
else
  echo "WARN: $MCP_ENV missing"
fi

if launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
  echo "OK: LaunchAgent $LABEL is loaded."
else
  echo "WARN: LaunchAgent $LABEL is not loaded."
fi
