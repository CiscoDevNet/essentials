# Shared paths for ess-mcp-hide-secrets scripts. From sibling scripts:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=lib.sh
#   source "$SCRIPT_DIR/lib.sh"

MCP_HIDE_SECRETS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prints an XDG base directory: $1 when it is an absolute path, else the default $2.
# The XDG Base Directory spec says relative values are invalid and must be ignored.
xdg_base_dir() {
  case "${1:-}" in
    /*) echo "$1" ;;
    *) echo "$2" ;;
  esac
}

USERNAME="${USERNAME:-$(whoami)}"
LABEL="local.${USERNAME}.cursor-mcp-env"
GLOBAL_MCP_JSON="${GLOBAL_MCP_JSON:-$HOME/.cursor/mcp.json}"
PROJECT_MCP_JSON="${PROJECT_MCP_JSON:-}"
MCP_DATA_DIR="${MCP_DATA_DIR:-$(xdg_base_dir "${XDG_DATA_HOME:-}" "$HOME/.local/share")/cursor-mcp}"
MCP_STATE_DIR="${MCP_STATE_DIR:-$(xdg_base_dir "${XDG_STATE_HOME:-}" "$HOME/.local/state")/cursor-mcp}"
MCP_ENV="$MCP_DATA_DIR/mcp.env"
# The path install used before XDG_DATA_HOME, plus the pre-XDG file under ~/.cursor.
DEFAULT_MCP_ENV="$HOME/.local/share/cursor-mcp/mcp.env"
LEGACY_MCP_ENV="$HOME/.cursor/mcp.env"
LOADER_DEST="$MCP_DATA_DIR/load-mcp-env.sh"
LOG_FILE="$MCP_STATE_DIR/load-mcp-env.log"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
GUI_DOMAIN="gui/$(id -u)"
CHECK_INLINE_SECRETS="$MCP_HIDE_SECRETS_LIB_DIR/check-inline-secrets.py"

# Prints one existing secrets file to copy when $MCP_ENV is missing.
# Prints nothing when there is nothing to copy. Returns 1 when the default and
# legacy files both exist and differ, so the caller does not guess.
mcp_env_migration_source() {
  if [ -f "$MCP_ENV" ]; then
    return 0
  fi
  local -a candidates=()
  local candidate
  for candidate in "$DEFAULT_MCP_ENV" "$LEGACY_MCP_ENV"; do
    if [ -f "$candidate" ] && [ "$candidate" != "$MCP_ENV" ]; then
      candidates+=("$candidate")
    fi
  done
  if [ "${#candidates[@]}" -eq 0 ]; then
    return 0
  fi
  if [ "${#candidates[@]}" -eq 1 ] || cmp -s "${candidates[0]}" "${candidates[1]}"; then
    printf '%s\n' "${candidates[0]}"
    return 0
  fi
  echo "ERROR: $MCP_ENV is missing, but ${candidates[0]} and ${candidates[1]} both exist and differ." >&2
  echo "Copy the credentials you want to keep to $MCP_ENV, then rerun install." >&2
  return 1
}

# Copy an existing secrets file to $MCP_ENV. Does not overwrite $MCP_ENV.
preserve_mcp_env() {
  local source=""
  if ! source="$(mcp_env_migration_source)"; then
    return 1
  fi
  if [ -z "$source" ]; then
    return 0
  fi
  if [ "${DRY_RUN:-false}" = true ]; then
    echo "Would copy secrets: $source → $MCP_ENV"
    return 0
  fi
  mkdir -p "$(dirname "$MCP_ENV")"
  (umask 077 && cp "$source" "$MCP_ENV")
  chmod 600 "$MCP_ENV"
  echo "Copied secrets: $source → $MCP_ENV"
}
