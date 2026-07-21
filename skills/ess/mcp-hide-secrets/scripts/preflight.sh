#!/bin/bash
# Read-only preflight for mcp-hide-secrets. Never reads or prints secret values.
#
# Usage:
#   ./preflight.sh
#   PROJECT_MCP_JSON=/path/to/.cursor/mcp.json ./preflight.sh
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

issues=0

echo "== mcp-hide-secrets preflight =="

if [ "$(uname -s)" != "Darwin" ]; then
  echo "FAIL: macOS required (got $(uname -s))"
  exit 1
fi
echo "OK: macOS"

if [ -w "$LAUNCH_AGENTS_DIR" ] && [ "$(stat -f '%Su' "$LAUNCH_AGENTS_DIR")" = "$USERNAME" ]; then
  echo "OK: $LAUNCH_AGENTS_DIR writable by $USERNAME"
else
  owner="$(stat -f '%Su:%Sg' "$LAUNCH_AGENTS_DIR" 2>/dev/null || echo 'unknown')"
  echo "WARN: $LAUNCH_AGENTS_DIR not writable by $USERNAME (owner: $owner)"
  echo "      Run: $SCRIPT_DIR/fix-launchagents-dir.sh"
  issues=$((issues + 1))
fi

if [ -f "$MCP_ENV" ]; then
  key_count="$(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "$MCP_ENV" 2>/dev/null || echo 0)"
  echo "OK: $MCP_ENV exists ($key_count keys)"
else
  echo "WARN: $MCP_ENV missing"
  issues=$((issues + 1))
fi

mcp_json_found=false
for path in "$GLOBAL_MCP_JSON" ${PROJECT_MCP_JSON:+"$PROJECT_MCP_JSON"}; do
  [ -n "$path" ] || continue
  if [ ! -f "$path" ]; then
    echo "SKIP: $path (not found)"
    continue
  fi
  mcp_json_found=true
  while IFS= read -r line; do
    echo "mcp.json: $line"
    if [[ "$line" == *":inline=yes"* ]]; then
      issues=$((issues + 1))
    fi
  done < <(python3 "$CHECK_INLINE_SECRETS" "$path" || true)
done

if [ "$mcp_json_found" = false ]; then
  echo "FAIL: no mcp.json found (configure ~/.cursor/mcp.json first)"
  exit 1
fi

echo "== preflight done (issues: $issues) =="
exit 0
