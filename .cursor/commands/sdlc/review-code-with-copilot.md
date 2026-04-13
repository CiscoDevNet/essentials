# /review-code-with-copilot

Review the current branch against `origin/main` using GitHub Copilot CLI.

**Phase**: Review

---

## Usage

```
/review-code-with-copilot
```

Iterative review (only changes since the last review on this branch):

```
/review-code-with-copilot --since-last
```

Manual override (no remote fetch needed):

```
/review-code-with-copilot --since HEAD~1
/review-code-with-copilot --range HEAD~3..HEAD
```

Reset the last-reviewed marker for the current branch:

```
/review-code-with-copilot --reset-last
```

---

## Prerequisites

- **GitHub Copilot CLI** installed (`copilot` on `$PATH`).
  See [Getting started with GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-getting-started) for install instructions.

---

## Instructions

Run the review script **outside the sandbox** (`required_permissions: ["all"]`).
Copilot CLI spawns subprocesses that need PTY access, which the Cursor sandbox
blocks.

```bash
bash tools/shell/github-copilot/review-pr.sh
```

The script runs `copilot -p ... --allow-all` (non-interactive, all tools
auto-approved) so no manual confirmation is needed. Only use this in trusted
repositories -- `--allow-all` permits Copilot to run shell commands and modify
files without confirmation.

This will:

1. Verify Copilot CLI is installed (exits with install instructions if not).
2. Fetch `origin` (only for the default full-branch review) and show a diff stat for the selected range.
3. Run a non-interactive Copilot CLI review that checks for correctness issues, edge cases, security concerns, missing tests, performance problems, and maintainability issues.

After every successful run the script records the current `HEAD` SHA in a
per-branch marker file under `.cursor/.review-code-with-copilot/`. When you pass
`--since-last`, it reviews only changes since that marker. Use `--reset-last`
to clear it and fall back to the full `origin/main` diff.

---

## Related Commands

- `/review-code` - Cursor-native code review with confidence scoring
- `/review-pr` - Full PR review with GitHub MCP integration
- `/create-pr` - Create PR after review passes
