---
name: mcp-hide-secrets
description: >-
  Secure Cursor MCP credentials on macOS by moving secrets from ~/.cursor/mcp.json
  or a project .cursor/mcp.json into ~/.local/share/cursor-mcp/mcp.env and loading
  them via a LaunchAgent at login. Use when the user runs /mcp-hide-secrets, asks to
  secure MCP config, externalize MCP secrets, set up mcp.env, or fix MCP auth after
  cleaning up mcp.json. macOS only — do not use on Windows or Linux.
compatibility: >-
  macOS only. Requires bash, python3, launchctl, and write access to
  ~/Library/LaunchAgents. Windows support is planned via scripts/windows/ (not yet
  implemented).
metadata:
  version: "1.0"
  supported_os: macos
---

# MCP Hide Secrets (macOS — LaunchAgent + .env)

Move live credentials out of `~/.cursor/mcp.json` and/or a project `.cursor/mcp.json` into `~/.local/share/cursor-mcp/mcp.env`, loaded at login by a macOS LaunchAgent via `launchctl setenv`. Cursor interpolates `${env:VAR}` in MCP `env` and `headers` blocks.

## Agent workflow (required)

**Run only `scripts/run.sh`.** Do not write ad-hoc preflight, migrate, or verify commands.

```bash
# From this skill root (set PROJECT_MCP_JSON when a repo .cursor/mcp.json should be included):
chmod +x scripts/run.sh
USERNAME="$(whoami)" PROJECT_MCP_JSON="<repo>/.cursor/mcp.json" scripts/run.sh
USERNAME="$(whoami)" scripts/run.sh migrate
USERNAME="$(whoami)" scripts/run.sh status
scripts/run.sh fix-launchagents   # sudo in Terminal when agent cannot prompt
```

Never read or display secret values from `mcp.json` or `mcp.env`. Report script output only.

| User says | Script |
| --------- | ------ |
| `/mcp-hide-secrets` | `scripts/run.sh` (default) |
| `/mcp-hide-secrets migrate` | `scripts/run.sh migrate` [optional `mcp.json` path] |
| `/mcp-hide-secrets status` | `scripts/run.sh status` |
| `/mcp-hide-secrets install` | `scripts/run.sh install` (after `fix-launchagents`) |

If sudo fails in a non-interactive shell, ask the user to run `scripts/fix-launchagents-dir.sh` in Terminal, then `USERNAME="$(whoami)" scripts/run.sh install`.

After success: user quits Cursor (Cmd+Q) and reopens from Dock.

## MCP config targets

| Location | Path |
| -------- | ---- |
| Global | `~/.cursor/mcp.json` |
| Project | `<repo>/.cursor/mcp.json` |

Both merge into `~/.local/share/cursor-mcp/mcp.env`. Default `run.sh` migrates global first, then project when `PROJECT_MCP_JSON` is set. Migrate dirty files separately with `scripts/run.sh migrate <path>`.

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

| Script | Role |
| ------ | ---- |
| `run.sh` | Orchestrator — **only agent entry point** |
| `preflight.sh` | Read-only checks |
| `status.sh` | Read-only report |
| `check-inline-secrets.py` | Scan `mcp.json` without printing values |
| `install.sh` | Migrate-only or LaunchAgent install (called by `run.sh`) |
| `fix-launchagents-dir.sh` | `sudo chown "$(whoami):staff" ~/Library/LaunchAgents` |
| `verify.sh` | Post-install session env check |

## Files on the user's Mac

| Path | Purpose |
| ---- | ------- |
| `~/.local/share/cursor-mcp/mcp.env` | Secrets (chmod 600, never commit) |
| `~/.local/share/cursor-mcp/load-mcp-env.sh` | Parser + `launchctl setenv` |
| `~/Library/LaunchAgents/local.<username>.cursor-mcp-env.plist` | Login hook |
| `~/.cursor/mcp.json` and/or project `.cursor/mcp.json` | Sanitized MCP config |

Rotate credentials that were ever committed or pasted into chat before or after migration.
