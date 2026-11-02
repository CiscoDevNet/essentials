#!/bin/bash
# Install LaunchAgent + mcp.env for Cursor MCP secrets.
#
# Files go under the XDG data directory (${XDG_DATA_HOME:-~/.local/share}/cursor-mcp/)
# and the loader logs to the XDG state directory (${XDG_STATE_HOME:-~/.local/state}/cursor-mcp/).
# Both are resolved now and written into the LaunchAgent plist.
#
# Usage:
#   USERNAME=your-username ./install.sh              # fresh install from mcp.env.example
#   USERNAME=your-username ./install.sh --migrate-only [mcp.json]   # rewrite mcp.json + mcp.env only
#   USERNAME=your-username ./install.sh --migrate [mcp.json]        # alias for --migrate-only
#   USERNAME=your-username ./install.sh --dry-run [...]             # print planned changes only
#   ./install.sh --fix-launchagents
#
# --migrate / --migrate-only do NOT install the LaunchAgent; they exit after rewriting files.
# For migrate + LaunchAgent install, use scripts/run.sh (default or `migrate` / `install` modes),
# which confirms before writing.
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

MIGRATE=false
MIGRATE_ONLY=false
DRY_RUN=false
FIX_LAUNCHAGENTS=false
MCP_JSON="${MCP_JSON:-$GLOBAL_MCP_JSON}"

while [ $# -gt 0 ]; do
  case "$1" in
    --migrate)
      MIGRATE=true
      shift
      ;;
    --migrate-only)
      MIGRATE_ONLY=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --fix-launchagents)
      FIX_LAUNCHAGENTS=true
      shift
      ;;
    *)
      if [ -f "$1" ]; then
        MCP_JSON="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
      fi
      shift
      ;;
  esac
done

if [ "$FIX_LAUNCHAGENTS" = true ]; then
  if [ "$DRY_RUN" = true ]; then
    exec bash "$SCRIPT_DIR/fix-launchagents-dir.sh" --dry-run
  fi
  exec bash "$SCRIPT_DIR/fix-launchagents-dir.sh"
fi

if [ "$MIGRATE" = true ]; then
  MIGRATE_ONLY=true
fi

USERNAME="${USERNAME:-}"
if [ -z "$USERNAME" ]; then
  echo "ERROR: set USERNAME (your macOS username, kebab-case if needed)." >&2
  echo "Example: USERNAME=\$(whoami) $0" >&2
  exit 1
fi

LEGACY_LOADER="$HOME/.cursor/load-mcp-env.sh"

# Moves inline secrets from $MCP_JSON into $MCP_ENV. Prints key names, never values.
# Writes nothing when there is nothing to change, or when $DRY_RUN is true.
migrate_mcp_json() {
  python3 - "$MCP_JSON" "$MCP_ENV" "$DRY_RUN" <<'PY'
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

mcp_json_path = Path(sys.argv[1])
mcp_env_path = Path(sys.argv[2])
dry_run = sys.argv[3] == "true"

# Files this creates (mcp.env, the backup) must never be readable by others.
os.umask(0o077)

config = json.loads(mcp_json_path.read_text(encoding="utf-8"))
servers = config.get("mcpServers", {})

existing_env: dict[str, str] = {}
if mcp_env_path.is_file():
    for line in mcp_env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            existing_env[key] = value

# Env/header keys that identify the user but are not secrets — leave inline in mcp.json.
INLINE_KEYS = frozenset(
    {
        "X-User-ID",
        "X-User-Id",
        "ATLASSIAN_USER_EMAIL",
    }
)


def is_secret_value(value: str | None) -> bool:
    if not value:
        return False
    return not (value.startswith("${env:") and value.endswith("}"))


def normalize_token(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()


def header_env_key(server_name: str, header_name: str) -> str:
    return f"MCP_{normalize_token(server_name)}_{normalize_token(header_name)}"


moved_keys: list[str] = []
dropped_headers: list[str] = []

for server_name, server in servers.items():
    if server_name.lower() == "github" and "headers" in server:
        server.pop("headers")
        dropped_headers.append(server_name)

    env_block = server.get("env")
    if isinstance(env_block, dict):
        for key, value in list(env_block.items()):
            if key in INLINE_KEYS or not is_secret_value(value):
                continue
            existing_env[key] = value
            env_block[key] = f"${{env:{key}}}"
            moved_keys.append(key)

    headers = server.get("headers")
    if isinstance(headers, dict):
        for key, value in list(headers.items()):
            if key in INLINE_KEYS or not is_secret_value(value):
                continue
            env_key = header_env_key(server_name, key)
            existing_env[env_key] = value
            headers[key] = f"${{env:{env_key}}}"
            moved_keys.append(env_key)

if not moved_keys and not dropped_headers:
    print(f"No inline secrets in {mcp_json_path}; nothing to migrate.")
    raise SystemExit(0)

backup_path = mcp_json_path.with_name(f"{mcp_json_path.name}.bak.{time.strftime('%Y%m%d%H%M%S')}")
moved_summary = f"{len(moved_keys)} secret(s) into {mcp_env_path}: {', '.join(moved_keys)}"

if dry_run:
    print(f"Would back up {mcp_json_path} to {backup_path}")
    if moved_keys:
        print(f"Would move {moved_summary}")
    for server_name in dropped_headers:
        print(f"Would drop the headers of server '{server_name}' so it can use OAuth")
    print(f"Would rewrite {mcp_json_path} with ${{env:...}} references")
    raise SystemExit(0)

shutil.copyfile(mcp_json_path, backup_path)
os.chmod(backup_path, 0o600)
print(f"Backed up {mcp_json_path} to {backup_path}")
if moved_keys:
    mcp_env_path.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(existing_env.items())) + "\n",
        encoding="utf-8",
    )
    os.chmod(mcp_env_path, 0o600)
    print(f"Moved {moved_summary}")
for server_name in dropped_headers:
    print(f"Dropped the headers of server '{server_name}' so it can use OAuth")
mcp_json_path.write_text(
    json.dumps(config, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(f"Rewrote {mcp_json_path} with ${{env:...}} references")
PY
}

if [ "$DRY_RUN" = false ]; then
  mkdir -p "$HOME/.cursor" "$MCP_DATA_DIR" "$MCP_STATE_DIR" "$LAUNCH_AGENTS_DIR"
fi

if ! preserve_mcp_env; then
  exit 1
fi

if [ "$MIGRATE_ONLY" = true ]; then
  if [ ! -f "$MCP_JSON" ]; then
    echo "ERROR: --migrate-only requires an existing mcp.json." >&2
    echo "  Tried: $MCP_JSON" >&2
    exit 1
  fi
  migrate_mcp_json
  exit 0
fi

if [ "$DRY_RUN" = true ]; then
  echo "Would install loader: $LOADER_DEST"
  if [ -f "$LEGACY_LOADER" ] && [ "$LEGACY_LOADER" != "$LOADER_DEST" ]; then
    echo "Would remove legacy loader: $LEGACY_LOADER"
  fi
  if [ -f "$MCP_ENV" ]; then
    echo "Would keep existing $MCP_ENV"
  elif [ -n "$(mcp_env_migration_source)" ]; then
    echo "Would keep the copied $MCP_ENV"
  else
    echo "Would create $MCP_ENV from mcp.env.example unless a migration above creates it"
  fi
  "$SCRIPT_DIR/fix-launchagents-dir.sh" --dry-run
  echo "Would write LaunchAgent plist: $PLIST_DEST"
  echo "  runs:    $LOADER_DEST"
  echo "  loads:   $MCP_ENV"
  echo "  logs to: $LOG_FILE"
  if launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
    echo "Would reload LaunchAgent $LABEL and load $MCP_ENV into the GUI session"
  else
    echo "Would load LaunchAgent $LABEL and load $MCP_ENV into the GUI session"
  fi
  exit 0
fi

install -m 700 "$SCRIPT_DIR/load-mcp-env.sh" "$LOADER_DEST"

if [ -f "$LEGACY_LOADER" ] && [ "$LEGACY_LOADER" != "$LOADER_DEST" ]; then
  rm -f "$LEGACY_LOADER"
  echo "Removed legacy loader: $LEGACY_LOADER"
fi

if [ ! -f "$MCP_ENV" ]; then
  (umask 077 && cp "$SCRIPT_DIR/mcp.env.example" "$MCP_ENV")
  chmod 600 "$MCP_ENV"
  echo "Created $MCP_ENV from example — fill in secret values before restarting Cursor."
else
  echo "Keeping existing $MCP_ENV"
fi

if ! "$SCRIPT_DIR/fix-launchagents-dir.sh"; then
  echo "ERROR: fix LaunchAgents directory before installing plist." >&2
  exit 1
fi

python3 "$SCRIPT_DIR/render-plist.py" "$SCRIPT_DIR/local.your-username.cursor-mcp-env.plist" \
  "$PLIST_DEST" "$LABEL" "$LOADER_DEST" "$MCP_ENV" "$LOG_FILE"

if launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$GUI_DOMAIN/$LABEL" || true
fi

launchctl bootstrap "$GUI_DOMAIN" "$PLIST_DEST"
"$LOADER_DEST" "$MCP_ENV" "$LOG_FILE"

"$SCRIPT_DIR/verify.sh"

echo "Installed LaunchAgent: $LABEL"
echo "Loader: $LOADER_DEST"
echo "Secrets: $MCP_ENV"
echo "Log: $LOG_FILE"
echo "Reload after edits: launchctl kickstart -k $GUI_DOMAIN/$LABEL && restart Cursor (Cmd+Q)"
