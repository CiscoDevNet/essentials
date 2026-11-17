# Git hooks

The scanners run as [pre-commit](https://pre-commit.com) hooks with no install: Node
24 runs the TypeScript directly, and secretlint comes from `npx`.

## Guarding ess-* items in any repo

A repo that keeps `ess-*` items to publish can scan every changed item on commit
with the `ess-scan` hook from the essentials repo's `.pre-commit-hooks.yaml`:

```yaml
- repo: https://github.com/CiscoDevNet/essentials
  rev: <tag or sha>
  hooks:
    - id: ess-scan
```

It runs `scan` on each changed item and fails on critical findings. The jargon
terms come from `jargon.json` at the repo root (and at each item); with no terms
the hook fails. To use another file name, pass it through `args`:

```yaml
    - id: ess-scan
      args: [--jargon-file, company-jargon.json]
```

It needs Node 24 or later and npm on `PATH`; trufflehog is used when installed.

## Jargon in commit messages and pushes

The essentials repo also guards its own history with `scripts/src/jargon-check.ts`,
as two local hooks:

| Hook | Stage | Checks |
| --- | --- | --- |
| `jargon-commit-msg` | `commit-msg` | The message being committed, ignoring git comment lines. |
| `jargon-push` | `pre-push` | Every commit not yet on a remote: its message and the lines it adds. |

The pre-push hook is the backstop: it also catches commits that skipped the
commit-msg hook (`git commit --no-verify`, `git commit-tree`). It only scans what a
push would publish, so existing history never blocks a push.

Run the check by hand from the repo root:

```bash
node "$SKILL_DIR/scripts/src/jargon-check.ts"                 # unpublished commits
node "$SKILL_DIR/scripts/src/jargon-check.ts" --to-ref <sha>  # a commit and its unpublished ancestors
```

The terms and their exceptions live in `jargon.json` at the repo root (pass
`--jargon-file <name>` for another name). With no terms, the check exits 1. The
jargon file itself is never flagged. `allow.paths` are repo-relative globs (`*`,
`**`, `?`) whose added lines are never flagged; `allow.text` entries are literal
strings, in exact case, removed from a line before matching, so a forbidden term
elsewhere on the same line is still caught:

```json
{
  "terms": ["internal-codename"],
  "allow": {
    "paths": ["docs/examples/**"],
    "text": ["docs.example.com"]
  }
}
```

`allow.text` also applies to `sync` and `scan`, and is listed for the agent and the
reviewer, so a public name that contains a term can stay. `allow.paths` applies to
the hooks only.
