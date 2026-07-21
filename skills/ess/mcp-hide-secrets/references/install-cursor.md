# Cursor installation (optional)

This skill is portable per [agentskills.io](https://agentskills.io/specification). The committed `SKILL.md` stays host-neutral; apply these steps when installing under **Cursor** locally or in a team monorepo fork.

## Slash command only (`/mcp-hide-secrets`)

Cursor can load a skill for explicit slash invocation without auto-attaching it to every agent turn. Add this line to the **top-level** YAML frontmatter in your local copy of `SKILL.md` (not under `metadata` — Cursor reads the top-level key):

```yaml
disable-model-invocation: true
```

Example (after `description`, before `compatibility`):

```yaml
---
name: mcp-hide-secrets
description: >-
  ...
disable-model-invocation: true
compatibility: >-
  macOS only. ...
---
```

**Why not in the published skill?** That key is Cursor-specific and not part of the agentskills.io spec. Keeping it out of the committed skill lets `skills-ref validate` pass and lets Claude Code / other hosts use the same files without host-only frontmatter.

**Team monorepo forks:** A Cursor-first monorepo may commit `disable-model-invocation: true` directly in `SKILL.md`. For a portable publish copy, leave it out and document this file instead.

## Run the skill

After optional frontmatter edits:

```
/mcp-hide-secrets
```

Or from the skill root:

```bash
USERNAME=$(whoami) PROJECT_MCP_JSON="<repo>/.cursor/mcp.json" scripts/run.sh
```

See [launchctl.md](launchctl.md) for manual install, migration, and ongoing ops.
