#!/usr/bin/env bash
# Linters must read the pinned head, not the checkout that invoked scan-pr.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1" >&2; FAIL=$((FAIL + 1)); }

ROOT=$(mktemp -d)
BIN=$(mktemp -d)
OUT=$(mktemp -d)
LINKED=$(mktemp -d)
SEEN="$OUT/ruff-seen.txt"
ESLINT_SEEN="$OUT/eslint-seen.txt"
trap 'rm -rf "$ROOT" "$BIN" "$OUT" "$LINKED"' EXIT

cat >"$BIN/ruff" <<EOF
#!/bin/bash
if [[ "\${1:-}" == "--version" ]]; then exit 0; fi
for arg in "\$@"; do
  case "\$arg" in
    *.py)
      if [[ -f "\$arg" ]]; then
        cat "\$arg" >>"$SEEN"
      else
        printf 'missing %s\n' "\$arg" >>"$SEEN"
      fi
      ;;
  esac
done
printf '[]\n'
EOF
cat >"$BIN/bandit" <<'EOF'
#!/bin/bash
[[ "${1:-}" == "--version" ]] && exit 0
printf '{"results":[]}\n'
EOF
cat >"$BIN/pylint" <<'EOF'
#!/bin/bash
[[ "${1:-}" == "--version" ]] && exit 0
printf '[]\n'
EOF
chmod +x "$BIN/ruff" "$BIN/bandit" "$BIN/pylint"

if command -v uv >/dev/null 2>&1; then
  real_uv=$(command -v uv)
  cat >"$BIN/uv" <<EOF
#!/bin/bash
if [[ "\${1:-}" == run && "\${2:-}" == ruff ]]; then exit 1; fi
if [[ "\${1:-}" == run && "\${2:-}" == bandit ]]; then exit 1; fi
if [[ "\${1:-}" == run && "\${2:-}" == pylint ]]; then exit 1; fi
exec "$real_uv" "\$@"
EOF
  chmod +x "$BIN/uv"
fi

git -C "$ROOT" init -q -b main
git -C "$ROOT" config user.email test@example.com
git -C "$ROOT" config user.name test
printf 'print("base")\n' >"$ROOT/keep.py"
git -C "$ROOT" add keep.py
git -C "$ROOT" commit -q -m base
BASE=$(git -C "$ROOT" rev-parse HEAD)
printf 'UNIQUE_HEAD_ONLY = 1\n' >"$ROOT/only_on_head.py"
mkdir -p "$ROOT/web"
printf 'export default [];\n' >"$ROOT/web/eslint.config.mjs"
printf 'export const value = 1;\n' >"$ROOT/web/app.ts"
git -C "$ROOT" add only_on_head.py web
git -C "$ROOT" commit -q -m head
HEAD_SHA=$(git -C "$ROOT" rev-parse HEAD)
git -C "$ROOT" checkout -q "$BASE"

# Installed deps are untracked, so only the caller's checkout has them.
mkdir -p "$ROOT/node_modules/.bin"
cat >"$ROOT/node_modules/.bin/eslint" <<EOF
#!/bin/bash
pwd >>"$ESLINT_SEEN"
printf '[]\n'
EOF
chmod +x "$ROOT/node_modules/.bin/eslint"

(
  cd "$ROOT"
  PATH="$BIN:$PATH" bash "$SCRIPT_DIR/scan-pr.sh" \
    --base "$BASE" --head "$HEAD_SHA" --repo acme/widgets --output "$OUT/scan"
)

if [[ ! -f "$ROOT/only_on_head.py" ]]; then
  pass "the caller checkout stays on the older commit"
else
  fail "the caller checkout gained only_on_head.py"
fi
if grep -q UNIQUE_HEAD_ONLY "$SEEN"; then
  pass "ruff read the file from the pinned head"
else
  fail "ruff did not see UNIQUE_HEAD_ONLY: $(cat "$SEEN" 2>/dev/null || echo missing)"
fi
if [[ -s "$ESLINT_SEEN" ]] && grep -q $'^eslint\tok$' "$OUT/scan/tools.tsv"; then
  pass "eslint ran from the caller's node_modules"
else
  fail "eslint did not run: $(grep eslint "$OUT/scan/tools.tsv" 2>/dev/null || echo 'no status')"
fi

# A fresh linked worktree has no node_modules, and --output is relative to it.
rm -f "$SEEN" "$ESLINT_SEEN"
git -C "$ROOT" worktree add -q --detach "$LINKED/caller" "$BASE"
(
  cd "$LINKED/caller"
  PATH="$BIN:$PATH" bash "$SCRIPT_DIR/scan-pr.sh" \
    --base "$BASE" --head "$HEAD_SHA" --repo acme/widgets --output relative-scan
)

if grep -q UNIQUE_HEAD_ONLY "$SEEN" && [[ -f "$LINKED/caller/relative-scan/report.md" ]]; then
  pass "a relative --output stays in the caller's directory"
else
  fail "relative --output lost the file lists: $(cat "$SEEN" 2>/dev/null || echo missing)"
fi
if [[ -s "$ESLINT_SEEN" ]]; then
  pass "eslint fell back to the main worktree's node_modules"
else
  fail "eslint did not run from the linked worktree"
fi

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]]
