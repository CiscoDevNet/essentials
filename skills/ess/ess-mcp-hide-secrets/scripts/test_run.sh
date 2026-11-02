#!/usr/bin/env bash
# Self-test for run.sh write safety and install.sh migration.
# Each case runs against a temporary HOME with stub launchctl and sudo, so it
# never touches your real mcp.json, mcp.env, LaunchAgents, or GUI session.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAKE_SECRET="not-a-real-secret"
PASSED=0
FAILED=0

pass() {
  echo "  PASS: $1"
  PASSED=$((PASSED + 1))
}
fail() {
  echo "  FAIL: $1" >&2
  FAILED=$((FAILED + 1))
}
check() {
  local description="$1"
  shift
  if "$@"; then pass "$description"; else fail "$description"; fi
}

# Creates a temporary HOME holding an mcp.json with inline secrets, a writable
# LaunchAgents directory, and stubs that log every launchctl or sudo call.
# Prints the HOME path.
#   $1  "dirty" (default) or "clean" mcp.json
setup_home() {
  local kind="${1:-dirty}"
  local home
  home=$(mktemp -d)
  mkdir -p "$home/.cursor" "$home/Library/LaunchAgents" "$home/bin"
  if [ "$kind" = dirty ]; then
    cat >"$home/.cursor/mcp.json" <<EOF
{
  "mcpServers": {
    "my-api": {
      "command": "my-api",
      "env": {"MY_API_KEY": "$FAKE_SECRET", "ATLASSIAN_USER_EMAIL": "me@example.com"}
    },
    "github": {
      "url": "https://mcp.example.com/mcp",
      "headers": {"Authorization": "Bearer $FAKE_SECRET"}
    }
  }
}
EOF
  else
    cat >"$home/.cursor/mcp.json" <<'EOF'
{
  "mcpServers": {
    "my-api": {"command": "my-api", "env": {"MY_API_KEY": "${env:MY_API_KEY}"}}
  }
}
EOF
  fi
  cp "$home/.cursor/mcp.json" "$home/mcp.json.orig"
  for stub in launchctl sudo; do
    cat >"$home/bin/$stub" <<EOF
#!/bin/bash
echo "$stub \$*" >>"$home/stub.log"
[ "$stub" = launchctl ] && [ "\${1:-}" = print ] && exit 1
exit 0
EOF
    chmod +x "$home/bin/$stub"
  done
  touch "$home/stub.log"
  echo "$home"
}

# Runs a skill script with the temporary HOME and stubs. Prints combined output.
# Set TEST_XDG_DATA_HOME or TEST_XDG_STATE_HOME to pass XDG variables through.
#   $1  HOME from setup_home; $2  script name; remaining args go to the script
run_in() {
  local home="$1" script="$2"
  shift 2
  env -u MCP_DATA_DIR -u MCP_STATE_DIR -u GLOBAL_MCP_JSON -u PROJECT_MCP_JSON -u MCP_JSON \
    -u XDG_DATA_HOME -u XDG_STATE_HOME \
    ${TEST_XDG_DATA_HOME:+"XDG_DATA_HOME=$TEST_XDG_DATA_HOME"} \
    ${TEST_XDG_STATE_HOME:+"XDG_STATE_HOME=$TEST_XDG_STATE_HOME"} \
    HOME="$home" USERNAME="$(whoami)" PATH="$home/bin:$PATH" \
    bash "$SCRIPT_DIR/$script" "$@" </dev/null 2>&1
}

mcp_json_unchanged() { cmp -s "$1/.cursor/mcp.json" "$1/mcp.json.orig"; }
no_mcp_env() { [ ! -e "$1/.local/share/cursor-mcp/mcp.env" ]; }
no_backup() { ! compgen -G "$1/.cursor/mcp.json.bak.*" >/dev/null; }
no_plist() { [ -z "$(ls -A "$1/Library/LaunchAgents")" ]; }
no_launchctl_writes() { ! grep -qE '^(launchctl (bootstrap|bootout|setenv|kickstart)|sudo)' "$1/stub.log"; }
nothing_written() {
  mcp_json_unchanged "$1" && no_mcp_env "$1" && no_backup "$1" && no_plist "$1" && no_launchctl_writes "$1"
}
contains() { grep -qF -- "$2" <<<"$1"; }
lacks() { ! grep -qF -- "$2" <<<"$1"; }
mode_of() { stat -f '%Lp' "$1"; }

echo "=== run.sh / install.sh self-tests ==="

# ---------------------------------------------------------------------------
echo "-- --dry-run prints the plan and writes nothing --"
home=$(setup_home)
status=0
output=$(run_in "$home" run.sh --dry-run) || status=$?
check "exits 0" [ "$status" -eq 0 ]
check "names the key it would move" contains "$output" "Would move 1 secret(s)"
check "lists the key name" contains "$output" "MY_API_KEY"
check "reports the github headers it would drop" contains "$output" "drop the headers of server 'github'"
check "never prints the secret value" lacks "$output" "$FAKE_SECRET"
check "writes nothing" nothing_written "$home"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- --dry-run wins over --yes --"
home=$(setup_home)
status=0
output=$(run_in "$home" run.sh migrate --dry-run --yes) || status=$?
check "exits 0" [ "$status" -eq 0 ]
check "writes nothing" nothing_written "$home"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- a real write without a terminal requires --yes --"
home=$(setup_home)
status=0
output=$(run_in "$home" run.sh) || status=$?
check "exits non-zero" [ "$status" -ne 0 ]
check "tells the operator to pass --yes" contains "$output" "--yes"
check "writes nothing" nothing_written "$home"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- --yes skips the prompt --"
home=$(setup_home)
status=0
output=$(run_in "$home" run.sh fix-launchagents --yes) || status=$?
check "exits 0 with no stdin" [ "$status" -eq 0 ]
check "runs the step" contains "$output" "is writable by"
check "prints no plan" lacks "$output" "== plan"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- read-only modes reject write flags --"
home=$(setup_home)
for mode in status preflight; do
  status=0
  output=$(run_in "$home" run.sh "$mode" --dry-run) || status=$?
  check "$mode --dry-run exits non-zero" [ "$status" -ne 0 ]
done
status=0
output=$(run_in "$home" run.sh --bogus) || status=$?
check "unknown option exits non-zero" [ "$status" -ne 0 ]
check "unknown option writes nothing" nothing_written "$home"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- migrate creates owner-only files under a permissive umask --"
home=$(setup_home)
status=0
output=$(umask 022 && run_in "$home" install.sh --migrate-only "$home/.cursor/mcp.json") || status=$?
mcp_env="$home/.local/share/cursor-mcp/mcp.env"
backup=$(compgen -G "$home/.cursor/mcp.json.bak.*" | head -1 || true)
check "exits 0" [ "$status" -eq 0 ]
check "mcp.env is mode 600" [ "$(mode_of "$mcp_env")" = 600 ]
check "backup is mode 600" [ "$(mode_of "${backup:-/nonexistent}" 2>/dev/null)" = 600 ]
check "mcp.env holds the secret" grep -qx "MY_API_KEY=$FAKE_SECRET" "$mcp_env"
check "mcp.json references it" grep -qF '"MY_API_KEY": "${env:MY_API_KEY}"' "$home/.cursor/mcp.json"
check "mcp.json no longer holds the secret" lacks "$(cat "$home/.cursor/mcp.json")" "$FAKE_SECRET"
check "identifiers stay inline" grep -qF '"ATLASSIAN_USER_EMAIL": "me@example.com"' "$home/.cursor/mcp.json"
check "never prints the secret value" lacks "$output" "$FAKE_SECRET"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- migrate on a clean mcp.json with no mcp.env --"
home=$(setup_home clean)
status=0
output=$(run_in "$home" install.sh --migrate-only "$home/.cursor/mcp.json") || status=$?
check "exits 0" [ "$status" -eq 0 ]
check "says there is nothing to migrate" contains "$output" "nothing to migrate"
check "leaves mcp.json unchanged" mcp_json_unchanged "$home"
check "makes no backup" no_backup "$home"
check "creates no mcp.env" no_mcp_env "$home"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- an absolute XDG_DATA_HOME moves mcp.env --"
home=$(setup_home)
status=0
output=$(TEST_XDG_DATA_HOME="$home/xdg-data" run_in "$home" install.sh --migrate-only "$home/.cursor/mcp.json") || status=$?
check "exits 0" [ "$status" -eq 0 ]
check "writes mcp.env under XDG_DATA_HOME" [ -f "$home/xdg-data/cursor-mcp/mcp.env" ]
check "writes nothing under the default directory" no_mcp_env "$home"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- a relative XDG_DATA_HOME is ignored --"
home=$(setup_home)
status=0
output=$(cd "$home" && TEST_XDG_DATA_HOME="relative-data" run_in "$home" install.sh --migrate-only "$home/.cursor/mcp.json") || status=$?
check "exits 0" [ "$status" -eq 0 ]
check "writes mcp.env under the default directory" [ -f "$home/.local/share/cursor-mcp/mcp.env" ]
check "creates nothing under the relative path" [ ! -e "$home/relative-data" ]
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- the install plan shows the resolved XDG paths --"
home=$(setup_home)
status=0
output=$(TEST_XDG_DATA_HOME="$home/xdg-data" TEST_XDG_STATE_HOME="$home/xdg-state" \
  run_in "$home" run.sh install --dry-run) || status=$?
check "exits 0" [ "$status" -eq 0 ]
check "loader under XDG_DATA_HOME" contains "$output" "runs:    $home/xdg-data/cursor-mcp/load-mcp-env.sh"
check "mcp.env under XDG_DATA_HOME" contains "$output" "loads:   $home/xdg-data/cursor-mcp/mcp.env"
check "log under XDG_STATE_HOME" contains "$output" "logs to: $home/xdg-state/cursor-mcp/load-mcp-env.log"
check "writes nothing" nothing_written "$home"
check "creates no XDG data directory" [ ! -e "$home/xdg-data" ]
check "creates no XDG state directory" [ ! -e "$home/xdg-state" ]
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- render-plist.py writes absolute paths into a valid plist --"
tmp=$(mktemp -d)
odd_dir="$tmp/a & b <c>"
status=0
python3 "$SCRIPT_DIR/render-plist.py" "$SCRIPT_DIR/local.your-username.cursor-mcp-env.plist" \
  "$tmp/agent.plist" "local.tester.cursor-mcp-env" \
  "$odd_dir/load-mcp-env.sh" "$odd_dir/mcp.env" "$tmp/state/load-mcp-env.log" || status=$?
check "exits 0" [ "$status" -eq 0 ]
check "plist passes plutil -lint" plutil -lint -s "$tmp/agent.plist"
check "sets the label" [ "$(plutil -extract Label raw "$tmp/agent.plist")" = "local.tester.cursor-mcp-env" ]
check "runs the loader with bash" [ "$(plutil -extract ProgramArguments.0 raw "$tmp/agent.plist")" = "/bin/bash" ]
check "passes the loader path, escaped" [ "$(plutil -extract ProgramArguments.1 raw "$tmp/agent.plist")" = "$odd_dir/load-mcp-env.sh" ]
check "passes the mcp.env path" [ "$(plutil -extract ProgramArguments.2 raw "$tmp/agent.plist")" = "$odd_dir/mcp.env" ]
check "passes the log path" [ "$(plutil -extract ProgramArguments.3 raw "$tmp/agent.plist")" = "$tmp/state/load-mcp-env.log" ]
check "routes stderr to the log" [ "$(plutil -extract StandardErrorPath raw "$tmp/agent.plist")" = "$tmp/state/load-mcp-env.log" ]
check "no longer logs to /tmp" lacks "$(cat "$tmp/agent.plist")" "/tmp/cursor-mcp-env.log"
status=0
python3 "$SCRIPT_DIR/render-plist.py" "$SCRIPT_DIR/local.your-username.cursor-mcp-env.plist" \
  "$tmp/relative.plist" "local.tester.cursor-mcp-env" \
  "relative/load-mcp-env.sh" "$odd_dir/mcp.env" "$tmp/log" 2>/dev/null || status=$?
check "rejects a relative path" [ "$status" -ne 0 ]
check "writes no plist for it" [ ! -e "$tmp/relative.plist" ]
rm -rf "$tmp"

# ---------------------------------------------------------------------------
echo "-- the loader takes its paths as arguments, else XDG defaults --"
home=$(setup_home)
status=0
run_in "$home" load-mcp-env.sh "$home/none/mcp.env" "$home/logs/loader.log" >/dev/null || status=$?
check "exits 0 when mcp.env is missing" [ "$status" -eq 0 ]
check "creates the log directory and logs there" grep -qF "missing $home/none/mcp.env" "$home/logs/loader.log"
TEST_XDG_DATA_HOME="$home/xdg-data" TEST_XDG_STATE_HOME="$home/xdg-state" \
  run_in "$home" load-mcp-env.sh >/dev/null || true
check "defaults the log to XDG_STATE_HOME" grep -qF "missing $home/xdg-data/cursor-mcp/mcp.env" \
  "$home/xdg-state/cursor-mcp/load-mcp-env.log"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- invalid env lines are written to the log --"
home=$(setup_home)
printf 'not a valid line\n' >"$home/mcp.env"
status=0
run_in "$home" load-mcp-env.sh "$home/mcp.env" "$home/logs/loader.log" >/dev/null || status=$?
check "exits non-zero" [ "$status" -ne 0 ]
check "records the invalid line" grep -q "skip invalid line" "$home/logs/loader.log"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- --dry-run --fix-launchagents does not create LaunchAgents --"
home=$(setup_home)
rm -rf "$home/Library"
status=0
output=$(run_in "$home" install.sh --dry-run --fix-launchagents) || status=$?
check "exits 0 with --dry-run first" [ "$status" -eq 0 ]
check "does not create LaunchAgents with --dry-run first" [ ! -e "$home/Library/LaunchAgents" ]
check "previews the create with --dry-run first" contains "$output" "Would create $home/Library/LaunchAgents"
rm -rf "$home"
home=$(setup_home)
rm -rf "$home/Library"
status=0
output=$(run_in "$home" install.sh --fix-launchagents --dry-run) || status=$?
check "exits 0 with --dry-run last" [ "$status" -eq 0 ]
check "does not create LaunchAgents with --dry-run last" [ ! -e "$home/Library/LaunchAgents" ]
check "previews the create with --dry-run last" contains "$output" "Would create $home/Library/LaunchAgents"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- dry-run and a rejected mode leave helper modes unchanged --"
home=$(setup_home)
helper="$SCRIPT_DIR/preflight.sh"
original_mode=$(mode_of "$helper")
chmod 644 "$helper"
status=0
run_in "$home" run.sh --dry-run >/dev/null || status=$?
check "dry-run exits 0" [ "$status" -eq 0 ]
check "dry-run leaves the helper at 644" [ "$(mode_of "$helper")" = 644 ]
status=0
run_in "$home" run.sh not-a-mode >/dev/null || status=$?
check "unknown mode exits non-zero" [ "$status" -ne 0 ]
check "unknown mode leaves the helper at 644" [ "$(mode_of "$helper")" = 644 ]
chmod "$original_mode" "$helper"
rm -rf "$home"

# ---------------------------------------------------------------------------
echo "-- a different XDG_DATA_HOME keeps the previous default secrets --"
home=$(setup_home)
mkdir -p "$home/.local/share/cursor-mcp"
printf 'MY_API_KEY=kept-secret\n' >"$home/.local/share/cursor-mcp/mcp.env"
chmod 600 "$home/.local/share/cursor-mcp/mcp.env"
status=0
output=$(TEST_XDG_DATA_HOME="$home/xdg-data" run_in "$home" install.sh) || status=$?
check "install exits 0" [ "$status" -eq 0 ]
check "copies the previous secret" grep -qx 'MY_API_KEY=kept-secret' "$home/xdg-data/cursor-mcp/mcp.env"
check "leaves the previous file in place" grep -qx 'MY_API_KEY=kept-secret' "$home/.local/share/cursor-mcp/mcp.env"
check "does not install the example over it" lacks "$(cat "$home/xdg-data/cursor-mcp/mcp.env")" "Populated by install.sh"
rm -rf "$home"

echo "-- differing default and legacy files are refused --"
home=$(setup_home)
mkdir -p "$home/.local/share/cursor-mcp" "$home/.cursor"
printf 'MY_API_KEY=from-default\n' >"$home/.local/share/cursor-mcp/mcp.env"
printf 'MY_API_KEY=from-legacy\n' >"$home/.cursor/mcp.env"
status=0
output=$(TEST_XDG_DATA_HOME="$home/xdg-data" run_in "$home" install.sh) || status=$?
check "refuses to guess" [ "$status" -ne 0 ]
check "names both files" contains "$output" "both exist and differ"
check "does not create the new mcp.env" [ ! -e "$home/xdg-data/cursor-mcp/mcp.env" ]
rm -rf "$home"

echo ""
echo "=== Results: ${PASSED} passed, ${FAILED} failed ==="
[ "$FAILED" -eq 0 ]
