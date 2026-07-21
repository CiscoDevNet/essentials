# Rationale: LaunchAgent + session env (not per-server `envFile`)

For install steps see [launchctl.md](launchctl.md).

This document records **why** this skill uses a macOS LaunchAgent (`launchctl setenv` → `${env:VAR}` in `mcp.json`) instead of Cursor’s per-server `envFile` option. It follows a lightweight [Architecture Decision Record](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) shape: context, decision, consequences.

## Status

**Accepted** — LaunchAgent + session env is what this skill implements.

## Context

Cursor MCP config lives at `~/.cursor/mcp.json` (global) and/or `<repo>/.cursor/mcp.json` (project). We want secrets out of those files while keeping a single shared env file (`~/.local/share/cursor-mcp/mcp.env`).

Cursor supports two main secret patterns ([MCP docs](https://cursor.com/docs/mcp)):

1. **`${env:VAR}`** — Cursor resolves values from the **environment of the process that launched Cursor** (on macOS, the GUI login session when opened from Dock/Spotlight).
2. **`envFile`** — Per **stdio** server only: path to a dotenv file loaded into **that MCP child process** when Cursor spawns it.

Our typical global config mixes **stdio** servers (`command` + `npx` …) and **remote** servers (`url` + `headers` with `${env:…}`). Remote entries do not support `envFile`.

On macOS, Dock-launched Cursor does **not** inherit exports from `~/.zshrc`. Shell profile env is insufficient without extra machinery.

## Decision

Use a LaunchAgent at login to run `load-mcp-env.sh`, which reads `~/.local/share/cursor-mcp/mcp.env` and calls `launchctl setenv` for each key. Rewrite `mcp.json` to reference secrets only via `${env:VAR}`.

Secrets and the loader live under `~/.local/share/cursor-mcp/`, not `~/.cursor/`, so Cursor’s config directory stays limited to Cursor-owned files (principally `mcp.json`).

## Why not `envFile`?

`envFile` is a **good, standard** pattern — the same idea as VS Code `launch.json` / `tasks.json` `envFile`, scoped to the process being started. We do not use it as the primary approach here because of **scope**, not quality.

| Concern | `envFile` (per stdio server) | Session env (`launchctl setenv`) |
| -------- | ------------------------------ | ------------------------------------- |
| Who sees the vars | Only that MCP server’s child process | macOS GUI session → Cursor and all `${env:…}` resolution |
| Remote MCP (`url` + `headers`) | **Not supported** — no `envFile` field | `${env:…}` in headers works |
| `${env:VAR}` in `mcp.json` | Cursor does **not** read the child’s `envFile` for interpolation | Works for stdio `env` and remote `headers` |
| Least privilege | Stronger — secret only in one child | Broader — vars in GUI session (still better than plaintext in `mcp.json`) |
| Portability | stdio-only; `${userHome}/…` paths work cross-OS | macOS-specific (launchd) |
| Moving parts | One `envFile` path per server (or repeated path) | One env file + one LaunchAgent |

### Mental model

**`envFile`:**

```
Cursor (no API_KEY in its env)
  └── spawns npx/mcp-server
        └── envFile loaded here only
```

**Session env (this skill):**

```
LaunchAgent → launchctl setenv → GUI session has API_KEY
  └── Cursor starts (inherits session)
        ├── resolves ${env:API_KEY} for remote headers
        └── spawns stdio MCPs with session env available
```

If the config were **stdio-only**, `envFile` on each server (or a shared file referenced per server) would often be the simpler choice. Our config is not stdio-only.

## Alternatives considered

| Approach | Verdict |
| -------- | ------- |
| **Per-server `envFile`** for stdio + **LaunchAgent only for remote keys** | Valid hybrid; more complex (two mechanisms, two docs paths). Rejected for this skill in favor of one env file + one loader. |
| **Secrets only in `~/.zshrc`** | Fails for Dock-launched Cursor on macOS. |
| **Inline secrets in `mcp.json`** | Easy but unsafe to share or commit. |
| **`envFile` in project `.cursor/mcp.json`** | Helps per-repo stdio servers; does not fix global remote MCPs or GUI session. |

## Consequences

**Positive**

- One `mcp.env` feeds every `${env:…}` reference (stdio and remote).
- `mcp.json` is safe to inspect and share; secrets stay in `~/.local/share/cursor-mcp/`.
- Matches Cursor’s documented interpolation model for remote MCP auth.

**Negative**

- macOS-only until a Windows/Linux equivalent exists in this skill.
- Requires LaunchAgent + writable `~/Library/LaunchAgents`.
- Session-wide env is wider exposure than per-process `envFile` (mitigated by file permissions and not committing secrets).

**Neutral**

- Users who expect VS Code–style `envFile` for every server should read this doc — remote MCPs force session env or another Cursor-side mechanism.

## When `envFile` *is* appropriate

Use per-server `envFile` when:

- The server is **stdio** (`command` + `args`).
- Secrets are needed **only** inside that server process.
- You do not rely on `${env:…}` in `mcp.json` for **remote** servers in the same config.

Example (stdio only):

```json
{
  "mcpServers": {
    "example-search": {
      "command": "npx",
      "args": ["-y", "some-mcp-package"],
      "envFile": "${userHome}/.local/share/cursor-mcp/mcp.env"
    }
  }
}
```

That does **not** supply **remote** MCP `headers` — those still need session env (this skill) or a different pattern.

## References

- [Cursor MCP — config interpolation and `envFile`](https://cursor.com/docs/mcp)
- [Cursor forum — secure MCP secrets (`${env:…}` vs `envFile`)](https://forum.cursor.com/t/secure-secret-handing-for-mcps/155638)
- Install and operations: [launchctl.md](launchctl.md)
