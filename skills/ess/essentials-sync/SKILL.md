---
name: essentials-sync
description: >-
  Extract a jargon-free ess-* shared package out of a team- or account-specific
  tool in a private repo and sync it to the open-source essentials repo, with
  deterministic scanners and an adversarial LLM reviewer in between. Use when
  the user runs /essentials-sync, asks to open-source a package, extract an
  ess-* package, move or sync a tool into essentials, or scrub a package of
  company jargon before publishing. Requires the essentials-sync CLI and a
  CURSOR_API_KEY.
metadata:
  version: "1.0"
---

# Essentials Sync

Driver for the `essentials-sync` CLI. The CLI does the work — extraction, scanning (TruffleHog, secretlint, jargon, PII), the adversarial review loop, and all writes. This skill only resolves the binary and holds the approval gate, because a real run writes to **two** working trees.

## Agent workflow (required)

**Run only `scripts/run.sh`.** Do not invoke `essentials-sync` directly, do not hand-edit what it writes, and do not commit for the user.

### 1. Preflight

```bash
chmod +x scripts/run.sh
scripts/run.sh preflight
```

Stop and report if it fails. It checks Node >= 22, that the CLI resolves, and that `CURSOR_API_KEY` is set (or a `.env` is present for the CLI to load). A missing `trufflehog` is a warning, not a failure — that scanner is simply skipped.

### 2. Resolve the arguments

| Argument | Rule |
| --- | --- |
| `--source` | Absolute path. In default (extract) mode it must be a `tools/python/<name>/` directory inside the source repo. Ask if the user did not give one. |
| `--target-repo` | Absolute path to the essentials clone. Must be a git working tree. Ask if missing. |
| `--target-path` | Relative to `--target-repo`. Optional in extract mode (defaults to `packages/python/<package-name>`), **required** with `--no-extract`. |

If the source is already generic and needs no extraction, add `--no-extract` — and then `--target-path` is mandatory.

### 3. Dry run

```bash
scripts/run.sh dry-run --source <abs> --target-repo <abs> [...]
```

The CLI stages everything into a temp directory instead of the real target.

### 4. GATE — wait for approval

Show the user the resolved command, the CLI's `[plan]`, `[source-scan]`, and `[models]` lines, and the dry-run outcome. **Do not proceed until they explicitly approve.**

### 5. Sync

```bash
scripts/run.sh sync --source <abs> --target-repo <abs> [...]
```

### 6. Report

State the exit code and run `git status` in both repos (the CLI prints the exact commands on success). Both trees are left dirty on purpose — the user reviews and commits.

Never echo scanner findings that quote a secret value; report the file and rule instead.

## Options worth knowing

| Option | Use it when |
| --- | --- |
| `--no-extract` | The source is already generic; runs the sync phase only. Pair with `--target-path`. |
| `--no-fast-copy` | Force the agent to author the sync even when a clean source would qualify for a verbatim copy. |
| `--package-name <ess-name>` | The derived `ess-<basename>` name is wrong. Must be kebab-case and start with `ess-`. |
| `--max-revisions <n>` | Default 3 scan-and-revise iterations per phase. |
| `--no-adversarial-review` | Deterministic scanners only; skips the LLM reviewer. |
| `--model` / `--review-model` | Override the `opus` / `codex` family sentinels. |
| `--list-models` | Print the model IDs available to the current API key. |

Full option table, jargon wordlist customization (`.essentials-sync-jargon.json`), and install troubleshooting: [tools/typescript/essentials-sync/README.md](https://github.com/CiscoDevNet/essentials/blob/main/tools/typescript/essentials-sync/README.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Both phases clean. Tell the user to review and commit. |
| 1 | Could not start — bad args, missing `CURSOR_API_KEY`, or agent startup error. |
| 2 | Critical findings remain after `--max-revisions`. Trees left dirty; surface the findings. |
| 3 | The agent ran but failed mid-execution. Report the logged `agent` and `run` IDs. |

## Finding the CLI

`scripts/run.sh` resolves in this order, first hit wins:

1. `$ESSENTIALS_SYNC_BIN`
2. `essentials-sync` on `$PATH` (the `npm link` case)
3. `$ESSENTIALS_REPO/tools/typescript/essentials-sync/dist/cli.js`
4. The same path relative to this skill, when it still lives inside an essentials checkout

If none resolve, the script prints the build-and-link steps and exits 1. Set `ESSENTIALS_REPO` to use a clone without linking.
