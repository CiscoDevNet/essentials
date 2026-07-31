# Skills

[Agent Skills](https://agentskills.io) — portable `SKILL.md` workflows that work across Cursor, Claude Code, Codex, and other compatible agents.

The skills live under [`ess/`](ess/). Each is self-contained (`SKILL.md` plus optional `scripts/`, `references/`, and a `LICENSE`) and host-neutral: no IDE-specific frontmatter committed.

## Install

Install with the standard agent-skills CLI ([skills.sh](https://skills.sh)). It auto-detects your agent and places files in the right directory.

From a local clone (run in the repo root):

```bash
npx skills add ./skills --skill '*' --full-depth                 # all skills
npx skills add ./skills --skill mcp-hide-secrets --full-depth    # a single skill
npx skills add ./skills --list --full-depth                      # list without installing
```

`--full-depth` is required so the CLI discovers skills under nested paths like `skills/ess/` (not just top-level directories).

The CLI writes project skills to `.agents/skills/<name>/` (which Cursor reads natively, alongside `.cursor/skills/`). These are gitignored install output — the source of truth stays in `skills/`.

Or straight from GitHub:

```bash
npx skills add CiscoDevNet/essentials --skill '*' --full-depth
```

### Install matrix

| Agent | Project path | Global (`-g`) |
| ----- | ------------ | ------------- |
| Cursor | `.agents/skills/<name>/` (also reads `.cursor/skills/<name>/`) | `~/.cursor/skills/<name>/` |
| Claude Code | `.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| Codex | `.agents/skills/<name>/` | `~/.agents/skills/<name>/` |

## Skills

| Skill | What it does |
| ----- | ------------ |
| [`ess/pr-address-comments`](ess/pr-address-comments/) | Read a remote GitHub PR's review comments, implement fixes, then reply to and resolve the addressed threads. |
| [`ess/pr-address-comments-all`](ess/pr-address-comments-all/) | Address review comments across one or more PRs in parallel, each in its own git worktree on the PR's branch. |
| [`ess/mcp-hide-secrets`](ess/mcp-hide-secrets/) | Move Cursor MCP credentials out of `mcp.json` into a login-loaded `mcp.env` (macOS LaunchAgent). |
| [`ess/summarize-change-log`](ess/summarize-change-log/) | Condense a long git log or squash message into 1–5 Conventional-Commit bullets. |
| [`ess/essentials-sync`](ess/essentials-sync/) | Extract a jargon-free `ess-*` package out of a private tool and sync it to the open-source essentials repo. |

## Notes

- Cursor-only behavior such as `disable-model-invocation: true` (slash-command-only activation) is kept out of the committed `SKILL.md`. To enable it locally, see [`ess/mcp-hide-secrets/references/install-cursor.md`](ess/mcp-hide-secrets/references/install-cursor.md).
- `pr-address-comments-all` invokes its scripts from their committed location (`skills/ess/pr-address-comments-all/scripts/`), so they are present in every checkout and worktree of a repo that vendors these skills.

## License

[Apache 2.0](../LICENSE) — each skill also carries its own `LICENSE`.
