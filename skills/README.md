# Skills

[Agent Skills](https://agentskills.io) — portable `SKILL.md` workflows that work across Cursor, Claude Code, Codex, and other compatible agents.

The skills live under [`ess/`](ess/). Each is self-contained (`SKILL.md` plus optional `scripts/`, `references/`, and a `LICENSE`) and host-neutral: no IDE-specific frontmatter committed.

## Install

Install with the standard agent-skills CLI ([skills.sh](https://skills.sh)). It auto-detects your agent and places files in the right directory.

From a local clone (run in the repo root):

```bash
npx skills add ./skills --skill '*' --full-depth                 # all skills
npx skills add ./skills --skill ess-mcp-hide-secrets --full-depth  # a single skill
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
| [`ess/ess-pr-address-comments`](ess/ess-pr-address-comments/) | Address review comments on one or more PRs, each in its own git worktree on the PR's branch, then reply to and resolve the addressed threads. |
| [`ess/ess-pr-review`](ess/ess-pr-review/) | Review one or more PRs: repo linters run the deterministic checks, the agent adds judgment, and findings post after one approval. |
| [`ess/ess-gh-copilot-review`](ess/ess-gh-copilot-review/) | Review the current branch with GitHub Copilot CLI: the whole branch, only what changed since the last Copilot review, or a given range. |
| [`ess/ess-mcp-hide-secrets`](ess/ess-mcp-hide-secrets/) | Move Cursor MCP credentials out of `mcp.json` into a login-loaded `mcp.env` (macOS LaunchAgent). |
| [`ess/ess-summarize-change-log`](ess/ess-summarize-change-log/) | Condense a long git log or squash message into 1–5 Conventional-Commit bullets. |
| [`ess/ess-git-tidy`](ess/ess-git-tidy/) | Audit local branches, remote branches, and worktrees, then delete only what you approve at a single gate. |
| [`ess/ess-my-groups`](ess/ess-my-groups/) | Resolve nicknames and group names, which may overlap and nest, to people with emails and service handles, and maintain those groups. |
| [`ess/ess-git-commits`](ess/ess-git-commits/) | Commit and open PRs as an agent without agent attribution, using a commit-msg hook that strips the injected trailer. |
| [`ess/ess-gh-repo-mirror`](ess/ess-gh-repo-mirror/) | Mirror a GitHub repo or Action, including its tags, into another owner or org, or sync an existing mirror. |
| [`ess/ess-env-credentials`](ess/ess-env-credentials/) | Recover from missing environment variables or credentials by asking to source the project's `.env`, never reading it. |
| [`ess/ess-shell-flags-literal`](ess/ess-shell-flags-literal/) | Write command-line flags out literally instead of packing them into one shell variable. |
| [`ess/ess-django-docs`](ess/ess-django-docs/) | Answer Django questions from current documentation through the Context7 MCP. |
| [`ess/ess-postgres-docs`](ess/ess-postgres-docs/) | Answer PostgreSQL and `psql` questions from current documentation through the Context7 MCP. |
| [`ess/essentials-sync`](ess/essentials-sync/) | Extract a jargon-free `ess-*` package out of a private tool and sync it to the open-source essentials repo. |

## Notes

- Cursor-only behavior such as `disable-model-invocation: true` (slash-command-only activation) is kept out of the committed `SKILL.md`. To enable it locally, see [`ess/ess-mcp-hide-secrets/references/install-cursor.md`](ess/ess-mcp-hide-secrets/references/install-cursor.md).

## License

[Apache 2.0](../LICENSE) — each skill also carries its own `LICENSE`.
