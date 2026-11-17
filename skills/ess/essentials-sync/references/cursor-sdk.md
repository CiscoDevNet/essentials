# Cursor SDK dependency

`sync` (including `--dry-run`) and `models` require the
[Cursor SDK](https://www.npmjs.com/package/@cursor/sdk) and a Cursor API key.
`preflight`, `scan`, `status`, and the git hooks need neither, and never load the
SDK.

## What it is used for

| SDK call | Role |
| --- | --- |
| `Agent.create` | The primary agent. It extracts the generic package, writes the sync, and revises both until the scanners are clean. |
| `Agent.prompt` | The adversarial reviewer: a one-shot pass on a different model family that reports findings as JSON. |
| `Cursor.models.list` | Lists the models on the account, to resolve the `opus` and `codex` sentinels. |

Both agents run locally, with the source or target repo as their working
directory, and load no user or project Cursor settings.

## The API key

Create one at [cursor.com/dashboard](https://cursor.com/dashboard), under
**Integrations**, **API Keys**. Team service-account keys are under **Team
settings**, **Service Accounts** (Enterprise plans).

The CLI reads `CURSOR_API_KEY` from, in order, the environment, `./.env` in the
current directory, and `${XDG_CONFIG_HOME:-~/.config}/essentials-sync/.env`. A
variable already in the environment always wins. Keep the key in the config
directory, not in a repo:

```bash
mkdir -p ~/.config/essentials-sync
printf 'CURSOR_API_KEY=%s\n' "<key>" > ~/.config/essentials-sync/.env
chmod 600 ~/.config/essentials-sync/.env
```

The same files may set `CURSOR_MODEL` and `CURSOR_REVIEW_MODEL`, the defaults for
`--model` and `--review-model`.

## Pinned version

The SDK version is pinned in `scripts/sdk/package.json`, with a lockfile beside
it. The first `sync` or `models` installs it into the user cache (see
[install.md](install.md)). To bump it:

1. Change the version in `scripts/sdk/package.json` and in the essentials repo's
   root `package.json` (which uses it for type checking only).
2. In `scripts/sdk/`, run `npm install --package-lock-only` to refresh the lock
   without creating `node_modules`.
3. Update the `sqlite3` entry in `allowScripts` if the lock moved it.
4. Run the tests and a `sync --dry-run`.

## Data sent to Cursor

The agents' model calls go through Cursor's API. Everything the agents read is
sent to Cursor as part of those calls: the source item, files around it in the
source repo, and the target repo, private code included. The prompts also carry
the jargon wordlist. Use this skill only on code your organization allows to be
sent to Cursor.
