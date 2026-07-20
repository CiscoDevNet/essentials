#!/bin/bash
# Load ~/.local/share/cursor-mcp/mcp.env into the macOS GUI session via launchctl setenv.
# Parses line-by-line without sourcing (no shell expansion on values).

set -u

ENV_FILE="${MCP_ENV_FILE:-$HOME/.local/share/cursor-mcp/mcp.env}"
LOG="${MCP_ENV_LOG:-/tmp/cursor-mcp-env.log}"

log() {
  printf '%s [load-mcp-env] %s\n' "$(date -Iseconds)" "$*" >>"$LOG"
}

log_err() {
  printf '%s [load-mcp-env] %s\n' "$(date -Iseconds)" "$*" >>"$LOG" >&2
}

is_valid_key() {
  case "$1" in
    [A-Za-z_]*)
      case "$1" in
        *[!A-Za-z0-9_]*) return 1 ;;
        *) return 0 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}

[ -f "$ENV_FILE" ] || {
  log "missing $ENV_FILE; nothing to do"
  exit 0
}

failures=0
loaded=0

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    '' | \#*) continue ;;
  esac
  case "$line" in
    *=*) ;;
    *)
      log_err "skip invalid line (missing =)"
      failures=$((failures + 1))
      continue
      ;;
  esac
  key="${line%%=*}"
  value="${line#*=}"
  if [ -z "$key" ] || ! is_valid_key "$key"; then
    log_err "skip invalid key name"
    failures=$((failures + 1))
    continue
  fi
  if ! /bin/launchctl setenv "$key" "$value"; then
    log_err "failed to set $key"
    failures=$((failures + 1))
    continue
  fi
  loaded=$((loaded + 1))
done <"$ENV_FILE"

if [ "$loaded" -gt 0 ]; then
  log "loaded $loaded keys from $ENV_FILE"
fi
if [ "$failures" -gt 0 ]; then
  log_err "$failures line(s) skipped or failed from $ENV_FILE"
  exit 1
fi
