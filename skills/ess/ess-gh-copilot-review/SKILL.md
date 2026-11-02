---
name: ess-gh-copilot-review
description: >-
  Review the current git branch with GitHub Copilot CLI: the full branch against
  the remote's default branch, only the changes since the last Copilot review, or
  an explicit revision or range. Use when asked to "review this branch with Copilot", "get a
  Copilot review", "Copilot review since last time", or "have Copilot check
  HEAD~3..HEAD".
compatibility: >-
  Requires bash, git, and GitHub Copilot CLI (`copilot` on PATH). Must run outside
  any agent sandbox, because Copilot CLI spawns subprocesses that need PTY access.
---

# Review a Branch with GitHub Copilot CLI

Review the current branch against the remote's default branch using GitHub
Copilot CLI.

## Usage

Pass at most one scope option to the review script:

| Option | Reviews |
| ------ | ------- |
| _(none)_ | The whole branch against the remote's default branch |
| `--since-last` | Only changes since the last successful review on this branch |
| `--since <rev>` | Changes from `<rev>` to `HEAD`, e.g. `--since HEAD~1` |
| `--range <range>` | An explicit range, e.g. `--range HEAD~3..HEAD` |
| `--reset-last` | The whole branch, after clearing the last-reviewed marker |

`--since` and `--range` need no remote fetch.

The remote is `origin`, or the only remote when there is no `origin`. Its default
branch comes from `refs/remotes/<remote>/HEAD` (set by `git clone`), falling back
to `main`, then `master`. Pass `--base <ref>` (e.g. `--base upstream/develop`) when
there are several remotes and none is `origin`, or the base is some other branch.
`--base` applies to the whole-branch review, including `--since-last` without a
marker.

## Prerequisites

- **GitHub Copilot CLI** installed (`copilot` on `$PATH`).
  See [Getting started with GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-getting-started) for install instructions.

## Instructions

Run the bundled review script from inside the repository to review, **outside any
agent sandbox**. Copilot CLI spawns subprocesses that need PTY access, which
sandboxes block. `SKILL_DIR` is the absolute path of the directory that contains
this `SKILL.md`; the script reviews whichever repo the current directory is in.

```bash
bash "$SKILL_DIR/scripts/review-pr.sh" [option]
```

The script runs `copilot -p ... --allow-all` (non-interactive, all tools
auto-approved) so no manual confirmation is needed. Only use this in trusted
repositories -- `--allow-all` permits Copilot to run shell commands and modify
files without confirmation.

This will:

1. Verify Copilot CLI is installed (exits with install instructions if not).
2. Fetch the remote (only for the whole-branch review) and show a diff stat for the selected range.
3. Run a non-interactive Copilot CLI review that checks for correctness issues, edge cases, security concerns, missing tests, performance problems, and maintainability issues.

After every successful run the script records the current `HEAD` SHA in a
per-branch marker file under `.ess-gh-copilot-review/` inside the git directory.
Named branches use the common git directory, so every worktree of that branch
shares one marker. A detached checkout uses that worktree's own git directory,
so two detached checkouts do not share a `--since-last` marker. Markers are
never tracked. When you pass `--since-last`, it reviews only changes since that
marker. Use `--reset-last` to clear it and fall back to the whole-branch diff.

Relay Copilot's findings to the user.

## Validation

```bash
bash "$SKILL_DIR/scripts/test_review_pr.sh"
```

Runs the script against throwaway repos with a local bare remote and Copilot
stubbed out, and checks argument parsing, base detection, and the per-branch
marker.
