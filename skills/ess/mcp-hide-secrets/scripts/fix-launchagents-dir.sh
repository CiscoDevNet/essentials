#!/bin/bash
# Ensure ~/Library/LaunchAgents is owned by the current user (staff group).
# Required before install.sh can bootstrap the cursor-mcp-env LaunchAgent.
#
# Usage:
#   ./fix-launchagents-dir.sh
#
# Common case: directory exists but is owned by root (not writable). Runs:
#   sudo chown "$(whoami):staff" ~/Library/LaunchAgents
#
# See ../SKILL.md

set -euo pipefail

LAUNCH_AGENTS_DIR="${LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
CURRENT_USER="$(whoami)"
EXPECTED_GROUP="staff"

mkdir -p "$LAUNCH_AGENTS_DIR"

actual_owner="$(stat -f '%Su' "$LAUNCH_AGENTS_DIR")"
actual_group="$(stat -f '%Sg' "$LAUNCH_AGENTS_DIR")"

if [ -w "$LAUNCH_AGENTS_DIR" ] && [ "$actual_owner" = "$CURRENT_USER" ]; then
  echo "OK: $LAUNCH_AGENTS_DIR is writable by $CURRENT_USER."
  exit 0
fi

echo "LaunchAgents directory is not writable by $CURRENT_USER."
echo "  Path:  $LAUNCH_AGENTS_DIR"
echo "  Owner: ${actual_owner}:${actual_group}"
echo "  Fix:   sudo chown \"${CURRENT_USER}:${EXPECTED_GROUP}\" \"$LAUNCH_AGENTS_DIR\""
echo ""
echo "Running fix (sudo will prompt for your password)..."

sudo chown "${CURRENT_USER}:${EXPECTED_GROUP}" "$LAUNCH_AGENTS_DIR" || {
  echo ""
  echo "ERROR: sudo required — run this script in Terminal and approve the password prompt." >&2
  exit 2
}

if [ ! -w "$LAUNCH_AGENTS_DIR" ]; then
  echo "ERROR: $LAUNCH_AGENTS_DIR is still not writable after chown." >&2
  exit 1
fi

echo "OK: $LAUNCH_AGENTS_DIR is now owned by ${CURRENT_USER}:${EXPECTED_GROUP}."
