#!/usr/bin/env bash
# Filenames with spaces or characters Git quotes must stay whole paths.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1" >&2; FAIL=$((FAIL + 1)); }

ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
git -C "$ROOT" init -q -b main
git -C "$ROOT" config user.email test@example.com
git -C "$ROOT" config user.name test
git -C "$ROOT" commit -q --allow-empty -m base
BASE=$(git -C "$ROOT" rev-parse HEAD)

mkdir -p "$ROOT/src"
printf 'x = 1  # noqa\n' >"$ROOT/src/my module.py"
printf 'y = 1  # noqa\n' >"$ROOT/src/quote\"file.py"
git -C "$ROOT" add -- "src/my module.py" "src/quote\"file.py"
git -C "$ROOT" commit -q -m add
HEAD_SHA=$(git -C "$ROOT" rev-parse HEAD)

OUT=$(mktemp -d)
git -C "$ROOT" config core.quotePath true
(
  cd "$ROOT"
  bash "$SCRIPT_DIR/scan-disables.sh" "$OUT" "$BASE" "$HEAD_SHA"
)

python3 - "$OUT/disables.json" <<'PY'
import json
import sys

found = {(item["path"], item["text"]) for item in json.load(open(sys.argv[1], encoding="utf-8"))}
expected = {
    ("src/my module.py", "x = 1  # noqa"),
    ('src/quote"file.py', "y = 1  # noqa"),
}
missing = expected - found
if missing:
    raise SystemExit(f"missing {missing}; got {found}")
PY
pass "spaced and quoted paths stay intact"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]]
