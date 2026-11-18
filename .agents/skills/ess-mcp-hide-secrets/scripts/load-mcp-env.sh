#!/bin/bash
# Load mcp.env into the macOS GUI session via launchctl setenv.
# Parses line-by-line without sourcing (no shell expansion on values).
#
# Usage:
#   load-mcp-env.sh [mcp.env] [log file]
#
# The LaunchAgent passes both paths, resolved at install time, because it runs at
# login without your shell's XDG variables. Without arguments, the defaults follow
# the XDG Base Directory spec like lib.sh does (this file is installed on its own,
# so it cannot source lib.sh).

set -u

case "${XDG_DATA_HOME:-}" in
  /*) data_home="$XDG_DATA_HOME" ;;
  *) data_home="$HOME/.local/share" ;;
esac
case "${XDG_STATE_HOME:-}" in
  /*) state_home="$XDG_STATE_HOME" ;;
  *) state_home="$HOME/.local/state" ;;
esac

ENV_FILE="${1:-$data_home/cursor-mcp/mcp.env}"
LOG="${2:-$state_home/cursor-mcp/load-mcp-env.log}"
mkdir -p "$(dirname "$LOG")"

log() {
  printf '%s [load-mcp-env] %s\n' "$(date -Iseconds)" "$*" >>"$LOG"
}

log_err() {
  local message
  message="$(printf '%s [load-mcp-env] %s\n' "$(date -Iseconds)" "$*")"
  printf '%s' "$message" >>"$LOG"
  printf '%s' "$message" >&2
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
