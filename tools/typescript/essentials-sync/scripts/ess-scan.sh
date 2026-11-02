#!/usr/bin/env bash
# Runs `essentials-sync scan` on the given paths, installing and building the
# tool first if this checkout has not been built yet. Used as the ess-scan
# pre-commit hook, whose clone of this repo starts with no node_modules or dist.
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${TOOL_DIR}/dist/cli.js" ]]; then
  echo "ess-scan: building essentials-sync (first run only)" >&2
  (
    cd "${TOOL_DIR}"
    npm ci --no-audit --no-fund --loglevel=error >&2
    npm run --silent build >&2
  )
fi

exec node "${TOOL_DIR}/dist/cli.js" scan "$@"
