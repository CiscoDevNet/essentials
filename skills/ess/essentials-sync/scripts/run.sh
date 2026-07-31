#!/bin/bash
# Entry point for /essentials-sync — run this script only; do not invoke the CLI directly.
#
# Usage:
#   ./run.sh preflight
#   ./run.sh dry-run --source <abs> --target-repo <abs> [...]   # adds --dry-run
#   ./run.sh sync    --source <abs> --target-repo <abs> [...]
#
# Every argument after the mode is forwarded to essentials-sync verbatim.
#
# Optional:
#   ESSENTIALS_SYNC_BIN=/path/to/cli.js   explicit binary, wins over everything
#   ESSENTIALS_REPO=/path/to/essentials   clone to resolve the built CLI from
#
# See ../SKILL.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_REL="tools/typescript/essentials-sync"
CLI_REL="$PACKAGE_REL/dist/cli.js"
MIN_NODE_MAJOR=22

CLI=()
CLI_SOURCE=""
CLI_PACKAGE_DIR=""

die() {
  echo "ERROR: $*" >&2
  exit 1
}

install_hint() {
  cat >&2 <<'EOF'

Could not find the essentials-sync CLI. Build and link it once:

  cd <essentials>/tools/typescript/essentials-sync
  nvm use && npm install && npm run build
  npm link                    # puts `essentials-sync` on $PATH
  brew install trufflehog

Or point this skill at a clone without linking:

  export ESSENTIALS_REPO=/path/to/essentials
EOF
  exit 1
}

# Turn a resolved path into a runnable command. A .js entry point needs node;
# anything else (an npm-link shim) is executed directly.
set_cli_from_path() {
  local target="$1"
  if [[ "$target" == *.js ]]; then
    CLI=(node "$target")
  else
    CLI=("$target")
  fi
}

try_repo_root() {
  local root="$1"
  local cli="$root/$CLI_REL"
  [ -d "$root/$PACKAGE_REL" ] || return 1
  CLI_PACKAGE_DIR="$root/$PACKAGE_REL"
  [ -f "$cli" ] || return 1
  set_cli_from_path "$cli"
  return 0
}

resolve_cli() {
  if [ -n "${ESSENTIALS_SYNC_BIN:-}" ]; then
    [ -f "$ESSENTIALS_SYNC_BIN" ] || die "ESSENTIALS_SYNC_BIN is set but not a file: $ESSENTIALS_SYNC_BIN"
    set_cli_from_path "$ESSENTIALS_SYNC_BIN"
    CLI_SOURCE="ESSENTIALS_SYNC_BIN"
    return 0
  fi

  if command -v essentials-sync >/dev/null 2>&1; then
    CLI=(essentials-sync)
    CLI_SOURCE="PATH ($(command -v essentials-sync))"
    return 0
  fi

  if [ -n "${ESSENTIALS_REPO:-}" ] && try_repo_root "$ESSENTIALS_REPO"; then
    CLI_SOURCE="ESSENTIALS_REPO ($ESSENTIALS_REPO)"
    return 0
  fi

  # Still living inside the essentials checkout: skills/ess/<name>/scripts/
  local in_repo_root
  in_repo_root="$(cd "$SCRIPT_DIR/../../../.." 2>/dev/null && pwd || true)"
  if [ -n "$in_repo_root" ] && try_repo_root "$in_repo_root"; then
    CLI_SOURCE="in-repo ($in_repo_root)"
    return 0
  fi

  if [ -n "$CLI_PACKAGE_DIR" ]; then
    echo "ERROR: found $CLI_PACKAGE_DIR but it has no dist/cli.js — the package is not built." >&2
  fi
  install_hint
}

preflight() {
  local status=0

  if ! command -v node >/dev/null 2>&1; then
    echo "FAIL  node is not installed (need >= $MIN_NODE_MAJOR)"
    status=1
  else
    local major
    major="$(node -p 'process.versions.node.split(".")[0]')"
    if [ "$major" -lt "$MIN_NODE_MAJOR" ]; then
      echo "FAIL  node $(node -v) is too old (need >= $MIN_NODE_MAJOR)"
      status=1
    else
      echo "ok    node $(node -v)"
    fi
  fi

  resolve_cli
  echo "ok    cli via $CLI_SOURCE"

  # The CLI loads .env from the working directory and from its own package root.
  if [ -n "${CURSOR_API_KEY:-}" ]; then
    echo "ok    CURSOR_API_KEY is set"
  elif [ -f "$PWD/.env" ] || { [ -n "$CLI_PACKAGE_DIR" ] && [ -f "$CLI_PACKAGE_DIR/.env" ]; }; then
    echo "ok    CURSOR_API_KEY not exported, but a .env is present for the CLI to load"
  else
    echo "FAIL  CURSOR_API_KEY is not set and no .env was found"
    status=1
  fi

  if command -v trufflehog >/dev/null 2>&1; then
    echo "ok    trufflehog $(trufflehog --version 2>&1 | head -n1)"
  else
    echo "WARN  trufflehog is not installed — that scanner will be skipped (brew install trufflehog)"
  fi

  return "$status"
}

MODE="${1:-}"
shift || true

case "$MODE" in
  preflight)
    preflight
    ;;
  dry-run)
    resolve_cli
    echo "[skill] cli via $CLI_SOURCE" >&2
    exec "${CLI[@]}" --dry-run "$@"
    ;;
  sync)
    resolve_cli
    echo "[skill] cli via $CLI_SOURCE" >&2
    exec "${CLI[@]}" "$@"
    ;;
  *)
    if [ -n "$MODE" ]; then
      echo "ERROR: unknown mode: $MODE" >&2
    fi
    echo "Usage: $0 [preflight|dry-run|sync] [essentials-sync args...]" >&2
    exit 1
    ;;
esac
