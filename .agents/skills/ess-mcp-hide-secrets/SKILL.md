---
name: ess-mcp-hide-secrets
description: >-
  Secure Cursor MCP credentials on macOS by moving secrets from ~/.cursor/mcp.json
  or a project .cursor/mcp.json into an mcp.env under the XDG data directory
  (~/.local/share/cursor-mcp/ by default) and loading them via a LaunchAgent at login. Use when the user runs /ess-mcp-hide-secrets, asks to
  secure MCP config, externalize MCP secrets, set up mcp.env, or fix MCP auth after
  cleaning up mcp.json. macOS only — do not use on Windows or Linux.
license: Apache-2.0
compatibility: >-
  macOS only. Requires bash, python3, launchctl, and write access to
  ~/Library/LaunchAgents. Windows support is planned via scripts/windows/ (not yet
  implemented).
metadata:
  version: "1.0"
  supported_os: macos
---

# MCP Hide Secrets (macOS — LaunchAgent + .env)

Move live credentials out of `~/.cursor/mcp.json` and/or a project `.cursor/mcp.json` into `mcp.env`, loaded at login by a macOS LaunchAgent via `launchctl setenv`. Cursor interpolates `${env:VAR}` in MCP `env` and `headers` blocks.

Paths follow the XDG Base Directory spec. `mcp.env` and the loader live in `$XDG_DATA_HOME/cursor-mcp/` and the loader's log in `$XDG_STATE_HOME/cursor-mcp/`. When those variables are unset or relative, the defaults are `~/.local/share/` and `~/.local/state/`. Install resolves both and writes them into the LaunchAgent, which runs at login without your shell's variables; after changing either variable, run `install` again.

## Agent workflow (required)

**Run only `scripts/run.sh`.** Do not write ad-hoc preflight, migrate, or verify commands.

Run it as `"$SKILL_DIR/scripts/run.sh"`, where `SKILL_DIR` is the absolute path of the directory that contains this `SKILL.md`. Do not use a repo-relative path or `cd` into the skill; the skill may be installed outside the repo you are working in, and `mcp.json` paths you pass resolve from the current directory.

```bash
SKILL_DIR=<absolute path of the directory containing this SKILL.md>
# Set PROJECT_MCP_JSON when a repo .cursor/mcp.json should be included:
USERNAME="$(whoami)" PROJECT_MCP_JSON="<repo>/.cursor/mcp.json" bash "$SKILL_DIR/scripts/run.sh" --dry-run
USERNAME="$(whoami)" bash "$SKILL_DIR/scripts/run.sh" migrate --dry-run
USERNAME="$(whoami)" bash "$SKILL_DIR/scripts/run.sh" status
bash "$SKILL_DIR/scripts/run.sh" fix-launchagents --dry-run   # sudo in Terminal when agent cannot prompt
```

Every mode except `status` and `preflight` writes: it rewrites `mcp.json`, writes `mcp.env`, installs the LaunchAgent, or runs `sudo chown`. For those modes:

1. Run with `--dry-run` and show the user the planned changes. Nothing is written.
2. Ask the user to approve.
3. Only after approval, rerun the same command with `--yes` instead of `--dry-run`.

Without `--yes`, a write mode prompts in a terminal and refuses in an agent shell. `status` and `preflight` are read-only and take neither flag.

Never read or display secret values from `mcp.json` or `mcp.env`. Report script output only; it prints key names, never values.

| User says | Script |
| --------- | ------ |
| `/ess-mcp-hide-secrets` | `scripts/run.sh` (default) |
| `/ess-mcp-hide-secrets migrate` | `scripts/run.sh migrate` [optional `mcp.json` path] |
| `/ess-mcp-hide-secrets status` | `scripts/run.sh status` |
| `/ess-mcp-hide-secrets install` | `scripts/run.sh install` (after `fix-launchagents`) |

If sudo fails in a non-interactive shell, ask the user to run `bash "$SKILL_DIR/scripts/run.sh" fix-launchagents` in Terminal (substitute the absolute path), which prompts before running sudo, then dry-run and approve `install` as above.

After success: user quits Cursor (Cmd+Q) and reopens from Dock.

## MCP config targets

| Location | Path |
| -------- | ---- |
| Global | `~/.cursor/mcp.json` |
| Project | `<repo>/.cursor/mcp.json` |

Both merge into one `mcp.env`. Default `run.sh` migrates global first, then project when `PROJECT_MCP_JSON` is set. Migrate dirty files separately with `"$SKILL_DIR/scripts/run.sh" migrate <path>`.

## Gotchas (keep in SKILL.md)

- Dock-launched Cursor does **not** see `~/.zshrc` exports — session env via LaunchAgent is required.
- `~/Library/LaunchAgents` is sometimes owned by `root`; `fix-launchagents-dir.sh` is a normal step, not a one-off fix.
- Migrate runs **before** LaunchAgent install so secrets move even when sudo is pending.
- A server named `github` (any case) drops `headers` on migrate so OAuth can run.

## Migration rules (summary)

| Source in `mcpServers` | In `mcp.env` | In `mcp.json` |
| ---------------------- | ------------ | ------------- |
| `env` literals | same key | `${env:KEY}` |
| `headers` literals | `MCP_<SERVER>_<HEADER>` | `${env:MCP_…}` |

Identifiers (`X-User-ID`, `ATLASSIAN_USER_EMAIL`, …) stay inline. Details: [references/launchctl.md](references/launchctl.md).

## References (read when needed)

| File | When |
| ---- | ---- |
| [references/install-cursor.md](references/install-cursor.md) | Cursor-only optional steps (slash command, `disable-model-invocation`) |
| [references/launchctl.md](references/launchctl.md) | Manual install, migration tables, ongoing ops |
| [references/rationale.md](references/rationale.md) | Why session env instead of per-server `envFile` |
| [references/launchagent-naming.md](references/launchagent-naming.md) | Label `local.<username>.cursor-mcp-env`, launchctl commands |

## Scripts

All under `$SKILL_DIR/scripts/`.

| Script | Role |
| ------ | ---- |
| `run.sh` | Orchestrator — **only agent entry point**; `--dry-run` previews, `--yes` skips the prompt |
| `preflight.sh` | Read-only checks |
| `status.sh` | Read-only report |
| `check-inline-secrets.py` | Scan `mcp.json` without printing values |
| `install.sh` | Migrate-only or LaunchAgent install (called by `run.sh`) |
| `render-plist.py` | Write the LaunchAgent plist with the resolved paths (called by `install.sh`) |
| `fix-launchagents-dir.sh` | `sudo chown "$(whoami):staff" ~/Library/LaunchAgents` |
| `verify.sh` | Post-install session env check |
| `test_run.sh` | Self-test for the write guard and migration; uses a temporary `HOME` and stub `launchctl` |

## Files on the user's Mac

Default locations; `XDG_DATA_HOME` and `XDG_STATE_HOME` move the first three.

| Path | Purpose |
| ---- | ------- |
| `~/.local/share/cursor-mcp/mcp.env` | Secrets (chmod 600, never commit) |
| `~/.local/share/cursor-mcp/load-mcp-env.sh` | Parser + `launchctl setenv` |
| `~/.local/state/cursor-mcp/load-mcp-env.log` | Loader log (key names and counts, never values) |
| `~/Library/LaunchAgents/local.<username>.cursor-mcp-env.plist` | Login hook |
| `~/.cursor/mcp.json` and/or project `.cursor/mcp.json` | Sanitized MCP config |

Rotate credentials that were ever committed or pasted into chat before or after migration.
