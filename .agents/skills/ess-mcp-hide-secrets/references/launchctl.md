# MCP hide secrets — LaunchAgent + .env

Move credentials out of `~/.cursor/mcp.json` and/or a project `.cursor/mcp.json` into `~/.local/share/cursor-mcp/mcp.env`, loaded at login by a macOS LaunchAgent via `launchctl setenv`. Cursor interpolates `${env:VAR}` in MCP `env` and `headers` blocks. Secrets and the loader live outside `~/.cursor/`.

Paths on this page are the defaults. Setting `XDG_DATA_HOME` moves `~/.local/share/`, and `XDG_STATE_HOME` moves `~/.local/state/`; rerun `install` after changing either, since the LaunchAgent stores the paths resolved at install time.

**Recommended:** run the skill in Cursor (`/ess-mcp-hide-secrets`). Optional Cursor-only setup (slash-only loading): [install-cursor.md](install-cursor.md).

## Manual install

From the repo whose `.cursor/mcp.json` you want to include, where `SKILL_DIR` is the directory that contains `SKILL.md`:

```bash
USERNAME=$(whoami) PROJECT_MCP_JSON=.cursor/mcp.json bash "$SKILL_DIR/scripts/run.sh" --dry-run   # preview
USERNAME=$(whoami) PROJECT_MCP_JSON=.cursor/mcp.json bash "$SKILL_DIR/scripts/run.sh"             # prompts, then writes
# Or step by step (each write mode prompts; add --yes to skip the prompt):
# bash "$SKILL_DIR/scripts/run.sh" preflight
# bash "$SKILL_DIR/scripts/run.sh" fix-launchagents
# USERNAME=$(whoami) bash "$SKILL_DIR/scripts/run.sh" migrate
# USERNAME=$(whoami) bash "$SKILL_DIR/scripts/run.sh" install
# bash "$SKILL_DIR/scripts/run.sh" status
```

This will:

1. Back up the target `mcp.json` (global or project path you pass)
2. Extract secrets into `~/.local/share/cursor-mcp/mcp.env` (chmod 600)
3. Rewrite `mcp.json` with `${env:VAR}` references
4. Fix `~/Library/LaunchAgents` ownership if needed (`scripts/fix-launchagents-dir.sh` — may prompt for sudo)
5. Install `~/.local/share/cursor-mcp/load-mcp-env.sh` and a LaunchAgent plist that passes it the `mcp.env` and log paths
6. Bootstrap the agent and load env vars into the GUI session

If you previously used `~/.cursor/mcp.env`, install moves it to the new location automatically.

### LaunchAgents ownership (step 4)

On some Macs `~/Library/LaunchAgents` is owned by `root` and not writable. This is expected; install fixes it automatically:

```bash
bash "$SKILL_DIR/scripts/fix-launchagents-dir.sh"
# runs: sudo chown "$(whoami):staff" ~/Library/LaunchAgents
```

Run that script alone in Terminal if you need to approve sudo before rerunning install.

## Fresh install

```bash
USERNAME=$(whoami) bash "$SKILL_DIR/scripts/run.sh" install
```

Edit `~/.local/share/cursor-mcp/mcp.env` with your values, then:

```bash
launchctl kickstart -k gui/$(id -u)/local.$(whoami).cursor-mcp-env
```

Quit Cursor completely (Cmd+Q) and reopen from Dock.

## Migration rules

`scripts/run.sh migrate` (via `install.sh --migrate-only`) scans every entry in `mcpServers`:

| Source | Stored in `mcp.env` as | Rewritten in `mcp.json` |
| ------ | ------------------------ | ----------------------- |
| `env` block | same key | `${env:KEY}` |
| `headers` block | `MCP_<SERVER>_<HEADER>` | `${env:MCP_…}` |

User identifiers (`X-User-ID`, `ATLASSIAN_USER_EMAIL`, …) stay inline — they are not secrets.

A server named `github` (any case) drops its `headers` block so Cursor can use OAuth.

After migrate, list keys with:

```bash
grep -E '^[A-Za-z_]' ~/.local/share/cursor-mcp/mcp.env
```

## LaunchAgent label

Use `local.<your-username>.cursor-mcp-env`. See [launchagent-naming.md](launchagent-naming.md).

## Ongoing workflow

- **Rotate a secret:** edit `~/.local/share/cursor-mcp/mcp.env` → `launchctl kickstart -k gui/$(id -u)/local.<username>.cursor-mcp-env` → restart Cursor
- **Debug:** `tail ~/.local/state/cursor-mcp/load-mcp-env.log`, then `launchctl getenv <KEY>` for any key from `mcp.env`
- **Never commit** `~/.local/share/cursor-mcp/mcp.env`

## Files

| Path | Purpose |
| ---- | ------- |
| `~/.local/share/cursor-mcp/mcp.env` | Secret values (chmod 600) |
| `~/.local/share/cursor-mcp/load-mcp-env.sh` | Parser + `launchctl setenv` |
| `~/.local/state/cursor-mcp/load-mcp-env.log` | Loader log (key names and counts, never values) |
| `~/Library/LaunchAgents/local.<username>.cursor-mcp-env.plist` | Login hook |
| `~/.cursor/mcp.json` and/or `<repo>/.cursor/mcp.json` | Credential-free MCP config |

Skill scripts: [../scripts/](../scripts/)

Further reading: [rationale.md](rationale.md) — why this skill uses session env instead of per-server `envFile`.
