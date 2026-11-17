---
name: essentials-sync
description: >-
  Extract a jargon-free ess-* shared package out of a team- or account-specific
  tool in a private repo and sync it to the open-source essentials repo, with
  deterministic scanners and an adversarial LLM reviewer in between. Use when
  the user runs /essentials-sync, asks to open-source a package, extract an
  ess-* package, move or sync a tool into essentials, or scrub a package of
  company jargon before publishing.
license: Apache-2.0
compatibility: >-
  Requires Node.js 24 or later, git, and npm. Sync also requires the Cursor SDK
  (@cursor/sdk, installed into the user cache on the first sync) and a
  CURSOR_API_KEY. Needs network access on the first scan (secretlint, via npx)
  and the first sync (the SDK). trufflehog is optional.
metadata:
  version: "2.0"
---

# Essentials Sync

Sync needs the Cursor SDK and a Cursor API key; see
[references/cursor-sdk.md](references/cursor-sdk.md). `scan` and `status` need
neither.

The CLI does the work: extraction, scanning (TruffleHog, secretlint, jargon, PII),
the adversarial review loop, and all writes. This skill holds the approval gate,
because a real sync writes to **two** working trees.

`SKILL_DIR` below is the absolute path of the directory containing this `SKILL.md`.
Do not use a repo-relative path; the skill may be installed outside the repo.

```bash
node "$SKILL_DIR/scripts/src/cli.ts" <command> [options]
```

There is nothing to install or build. Node runs the TypeScript directly, and the
SDK installs itself into the user cache on the first `sync` or `models`.

## Agent workflow (required)

Run only the CLI above. Do not hand-edit what it writes, and do not commit for the
user.

### 1. Check Node

```bash
node --version
```

Stop if it is older than 24: the CLI will not start. Ask the user to switch (for
example `nvm use 24`).

### 2. Preflight

```bash
node "$SKILL_DIR/scripts/src/cli.ts" preflight
```

Stop and report any `FAIL` line. It checks Node, git, npm, and `CURSOR_API_KEY`
(exported, or in a `.env` the CLI loads). A missing trufflehog is a `WARN`; that
scanner is skipped.

### 3. Resolve the arguments

| Argument | Rule |
| --- | --- |
| `--source` | Absolute path. In default (extract) mode it must be a `tools/python/<name>/` directory in the source repo. With `--no-extract` it may be a directory or one file, such as `instructions/ess/ess-<name>.instructions.md`. Ask if the user did not give one. |
| `--target-repo` | Absolute path to the target repo. Must be a git work tree. Ask if missing. |
| `--target-path` | Relative to `--target-repo`. Optional in extract mode (defaults to `packages/python/<package-name>`), **required** with `--no-extract`. |

If the source is already generic and needs no extraction, add `--no-extract`, and
then `--target-path` is mandatory.

Extract mode assumes a uv workspace: the tool lives in `tools/python/<name>/`,
and the extracted package goes to `packages/python/ess-<name>/`. Use
`--no-extract` for anything else.

### 4. Dry run

```bash
node "$SKILL_DIR/scripts/src/cli.ts" sync --dry-run --source <abs> --target-repo <abs> [...]
```

The whole run happens against staging repos in the temp directory; the real repos
are not touched.

### 5. GATE: wait for approval

Show the user the CLI's `[plan]`, `[source-scan]`, and `[models]` lines and the
dry-run outcome. **Do not proceed until they explicitly approve.**

### 6. Sync

```bash
node "$SKILL_DIR/scripts/src/cli.ts" sync --yes --source <abs> --target-repo <abs> [...]
```

Your shell has no terminal, so without `--yes` the CLI refuses to write and exits 1.
Pass `--yes` only after the gate.

### 7. Report

State the exit code and run `git status` in both repos (the CLI prints the exact
commands on success). Both trees are left dirty on purpose; the user reviews and
commits.

Never echo scanner findings that quote a secret value; report the file and rule
instead.

## Options worth knowing

| Option | Use it when |
| --- | --- |
| `--no-extract` | The source is already generic; runs the sync phase only. Pair with `--target-path`. |
| `--no-fast-copy` | Force the agent to author the sync even when a clean source would qualify for a verbatim copy. |
| `--package-name <ess-name>` | The derived `ess-<basename>` name is wrong. Must be kebab-case and start with `ess-`. |
| `--max-revisions <n>` | Default 3 scan-and-revise iterations per phase. |
| `--no-adversarial-review` | Deterministic scanners only; skips the LLM reviewer. |
| `--model` / `--review-model` | Override the `opus` / `codex` family sentinels. |

Read [references/cli.md](references/cli.md) for every command and option, the
fast-path copy, and the jargon wordlist. Read
[references/hooks.md](references/hooks.md) only when wiring the scanners into git
hooks, and [references/install.md](references/install.md) only when the SDK
install fails.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Both phases clean. Tell the user to review and commit. |
| 1 | Could not start: bad arguments, missing `CURSOR_API_KEY`, no `--yes` without a terminal, or an agent startup error. |
| 2 | Critical findings remain after `--max-revisions`. Trees left dirty; surface the findings. |
| 3 | The agent ran but failed mid-execution. Report the logged `agent` and `run` IDs. |
