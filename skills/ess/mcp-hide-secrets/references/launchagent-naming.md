# LaunchAgent label for this skill

This skill installs one LaunchAgent. Keep the **filename** and plist **`Label`** identical.

| Item | Value |
| ---- | ----- |
| Label | `local.<your-username>.cursor-mcp-env` |
| Plist path | `~/Library/LaunchAgents/local.<your-username>.cursor-mcp-env.plist` |
| Bootstrap domain | `gui/$(id -u)` |

Replace `<your-username>` with your macOS username (`whoami`). Use kebab-case if the username contains underscores.

## Why `local.<username>.…`

- **`local.`** — personal namespace, not a vendor domain (avoids squatting `com.*` for one-off scripts).
- **`<username>`** — collision-safe within shared machines; matches `USERNAME` passed to `scripts/run.sh`.
- **`cursor-mcp-env`** — service purpose, kebab-case.

`launchd` only requires the label be unique in your user domain; the shape above is convention for scanability in `launchctl list` and logs.

## Managing the agent

```bash
# Load (install.sh does this)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.$(whoami).cursor-mcp-env.plist

# Re-run loader after editing mcp.env
launchctl kickstart -k gui/$(id -u)/local.$(whoami).cursor-mcp-env

# Inspect
launchctl print gui/$(id -u)/local.$(whoami).cursor-mcp-env

# Remove
launchctl bootout gui/$(id -u)/local.$(whoami).cursor-mcp-env
```

Commands use the **Label**, not the `.plist` filename — keeping them in sync avoids copy-paste mistakes.
