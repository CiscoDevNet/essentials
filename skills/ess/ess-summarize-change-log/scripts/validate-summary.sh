#!/usr/bin/env bash
# Validate ess-summarize-change-log markdown bullets (wrapper for validate_summary.py).
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "validate-summary: uv not found on PATH (required for validation)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# --no-project: the validator needs only the standard library, so do not sync
# (or create a .venv for) whatever project the caller is in.
exec uv run --no-project python "$SCRIPT_DIR/validate_summary.py" "$@"
