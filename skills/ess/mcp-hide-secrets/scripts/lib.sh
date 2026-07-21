# Shared paths for mcp-hide-secrets scripts. From sibling scripts:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=lib.sh
#   source "$SCRIPT_DIR/lib.sh"

MCP_HIDE_SECRETS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

USERNAME="${USERNAME:-$(whoami)}"
LABEL="local.${USERNAME}.cursor-mcp-env"
GLOBAL_MCP_JSON="${GLOBAL_MCP_JSON:-$HOME/.cursor/mcp.json}"
PROJECT_MCP_JSON="${PROJECT_MCP_JSON:-}"
MCP_DATA_DIR="${MCP_DATA_DIR:-$HOME/.local/share/cursor-mcp}"
MCP_ENV="$MCP_DATA_DIR/mcp.env"
LOADER_DEST="$MCP_DATA_DIR/load-mcp-env.sh"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
GUI_DOMAIN="gui/$(id -u)"
LOG_FILE="/tmp/cursor-mcp-env.log"
CHECK_INLINE_SECRETS="$MCP_HIDE_SECRETS_LIB_DIR/check-inline-secrets.py"
