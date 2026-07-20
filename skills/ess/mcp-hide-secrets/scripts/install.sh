#!/bin/bash
# Install LaunchAgent + ~/.local/share/cursor-mcp/mcp.env for Cursor MCP secrets.
#
# Usage:
#   USERNAME=your-username ./install.sh              # fresh install from mcp.env.example
#   USERNAME=your-username ./install.sh --migrate-only [mcp.json]   # rewrite mcp.json + mcp.env only
#   USERNAME=your-username ./install.sh --migrate [mcp.json]        # alias for --migrate-only
#   ./install.sh --fix-launchagents
#
# --migrate / --migrate-only do NOT install the LaunchAgent; they exit after rewriting files.
# For migrate + LaunchAgent install, use scripts/run.sh (default or `migrate` / `install` modes).
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

MIGRATE=false
MIGRATE_ONLY=false
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
    --fix-launchagents)
      exec "$SCRIPT_DIR/fix-launchagents-dir.sh"
      ;;
    *)
      if [ -f "$1" ]; then
        MCP_JSON="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
      fi
      shift
      ;;
  esac
done

if [ "$MIGRATE" = true ]; then
  MIGRATE_ONLY=true
fi

USERNAME="${USERNAME:-}"
if [ -z "$USERNAME" ]; then
  echo "ERROR: set USERNAME (your macOS username, kebab-case if needed)." >&2
  echo "Example: USERNAME=\$(whoami) $0" >&2
  exit 1
fi

LABEL="local.${USERNAME}.cursor-mcp-env"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
MCP_ENV="$MCP_DATA_DIR/mcp.env"
LOADER_DEST="$MCP_DATA_DIR/load-mcp-env.sh"
LEGACY_MCP_ENV="$HOME/.cursor/mcp.env"
LEGACY_LOADER="$HOME/.cursor/load-mcp-env.sh"
GUI_DOMAIN="gui/$(id -u)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

migrate_mcp_json() {
  python3 - "$MCP_JSON" "$MCP_ENV" <<'PY'
import json
import re
import sys
from pathlib import Path

mcp_json_path = Path(sys.argv[1])
mcp_env_path = Path(sys.argv[2])
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


for server_name, server in servers.items():
    if server_name.lower() == "github":
        server.pop("headers", None)

    env_block = server.get("env")
    if isinstance(env_block, dict):
        for key, value in list(env_block.items()):
            if key in INLINE_KEYS or not is_secret_value(value):
                continue
            existing_env[key] = value
            env_block[key] = f"${{env:{key}}}"

    headers = server.get("headers")
    if isinstance(headers, dict):
        for key, value in list(headers.items()):
            if key in INLINE_KEYS or not is_secret_value(value):
                continue
            env_key = header_env_key(server_name, key)
            existing_env[env_key] = value
            headers[key] = f"${{env:{env_key}}}"

if existing_env:
    mcp_env_path.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(existing_env.items())) + "\n",
        encoding="utf-8",
    )

mcp_json_path.write_text(
    json.dumps(config, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY
  chmod 600 "$MCP_ENV"
  echo "Migrated: $MCP_JSON → $MCP_ENV"
}

mkdir -p "$HOME/.cursor" "$MCP_DATA_DIR" "$LAUNCH_AGENTS_DIR"

if [ -f "$LEGACY_MCP_ENV" ] && [ ! -f "$MCP_ENV" ]; then
  mv "$LEGACY_MCP_ENV" "$MCP_ENV"
  chmod 600 "$MCP_ENV"
  echo "Moved legacy secrets: $LEGACY_MCP_ENV → $MCP_ENV"
fi

if [ "$MIGRATE_ONLY" = true ]; then
  if [ ! -f "$MCP_JSON" ]; then
    echo "ERROR: --migrate-only requires an existing mcp.json." >&2
    echo "  Tried: $MCP_JSON" >&2
    exit 1
  fi
  backup_path="$MCP_JSON.bak.$(date +%Y%m%d%H%M%S)"
  cp "$MCP_JSON" "$backup_path"
  chmod 600 "$backup_path"
  migrate_mcp_json
  exit 0
fi

install -m 700 "$SCRIPT_DIR/load-mcp-env.sh" "$LOADER_DEST"

if [ -f "$LEGACY_LOADER" ] && [ "$LEGACY_LOADER" != "$LOADER_DEST" ]; then
  rm -f "$LEGACY_LOADER"
  echo "Removed legacy loader: $LEGACY_LOADER"
fi

if [ ! -f "$MCP_ENV" ]; then
  cp "$SCRIPT_DIR/mcp.env.example" "$MCP_ENV"
  chmod 600 "$MCP_ENV"
  echo "Created $MCP_ENV from example — fill in secret values before restarting Cursor."
elif [ -f "$MCP_ENV" ]; then
  echo "Keeping existing $MCP_ENV"
fi

if ! "$SCRIPT_DIR/fix-launchagents-dir.sh"; then
  echo "ERROR: fix LaunchAgents directory before installing plist." >&2
  exit 1
fi

sed "s/local.your-username.cursor-mcp-env/${LABEL}/g" \
  "$SCRIPT_DIR/local.your-username.cursor-mcp-env.plist" >"$PLIST_DEST"

if launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$GUI_DOMAIN/$LABEL" || true
fi

launchctl bootstrap "$GUI_DOMAIN" "$PLIST_DEST"
"$LOADER_DEST"

"$SCRIPT_DIR/verify.sh"

echo "Installed LaunchAgent: $LABEL"
echo "Loader: $LOADER_DEST"
echo "Secrets: $MCP_ENV"
echo "Reload after edits: launchctl kickstart -k $GUI_DOMAIN/$LABEL && restart Cursor (Cmd+Q)"
