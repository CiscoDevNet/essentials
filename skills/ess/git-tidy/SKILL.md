---
name: git-tidy
description: >-
  Audit and clean up a repo's local branches, remote branches, and git
  worktrees. Classifies every branch and worktree into safe-to-delete,
  ask-first, or keep by joining git ancestry with PR state, then executes only
  what you approve at a single gate. Branches identical to main are treated as
  fresh work starts and are never auto-deleted. Use for /git-tidy, "clean up my
  branches", "which worktrees are stale", "what can I delete before I start", or
  a branch/worktree status review. Requires git; gh adds PR state.
compatibility: >-
  Any git repo, macOS or Linux, bash 3.2+. GitHub PR state needs gh
  authenticated against the repo's remote; without it the audit still runs and
  degrades conservatively.
metadata:
  version: "1.0"
---

# Git Tidy

Cleaning up branches by hand means running twenty git commands and holding the
answers in your head. This skill puts the inventory and the classification in a
script, so the only thing left is judgment: which of the ask-first items you
actually want gone.

## Quick start

```bash
skills/ess/git-tidy/scripts/audit.sh          # read-only; writes a report
```

Then read `report.md` from the printed directory, present it, and act on what
the user approves.

## What it decides

Every local branch lands in exactly one category. The disposition column is what
you may act on without asking.

| Category | Meaning | Disposition |
| -------- | ------- | ----------- |
| `base` | The local integration branch itself | keep |
| `fresh-start` | Tip is identical to base: work just begun | **ask** |
| `merged-ancestor` | Fully contained in base | safe, `git branch -d` |
| `pr-merged-verified` | Tip matches a merged PR's head commit | safe, `git branch -D` |
| `pr-merged-diverged` | PR merged, then commits were added | **ask** |
| `pr-open` | PR still open | keep |
| `unmerged-no-pr` | Work in progress, nothing upstream | keep |
| `superseded` | Contained in another local branch | **ask** |

Worktrees: `primary`, `current`, `locked`, `dirty`, `active` and `active-open-pr`
are kept or asked about; `prunable` (directory gone) and `stale-merged` (clean,
work already in base) are safe.

`fresh-start` is the one that most tools get wrong. A branch sitting exactly on
`main` looks empty and disposable, but it is almost always someone who just ran
`git checkout -b` and has not committed yet. Deleting it destroys intent, not
code, which is why it never enters the safe set.

## Workflow

### 1. Audit

Run from inside the target repo. The script only reads; it deletes nothing.

```bash
skills/ess/git-tidy/scripts/audit.sh [--base origin/main] [--remote origin]
```

| Flag | Use it when |
| ---- | ----------- |
| `--fetch` | Remote-tracking refs may be stale |
| `--no-gh` | Offline, or the repo is not on GitHub |
| `--no-size` | Worktrees are large and `du` is slow |
| `--base <ref>` | The integration branch is not `main`/`master` |
| `--output DIR` | You want the report somewhere specific |

It writes `report.md`, `report.json`, `branches.tsv`, and `worktrees.tsv`, and
prints the output directory as its last line.

### 2. Present

Show the summary counts and the branch table from `report.md`. Lead with the
numbers: how many are safe, how many need a decision, how much disk the stale
worktrees hold. Then walk through each ask-first item individually with the
evidence the report already gathered — the extra commits on a diverged branch,
the branch that supersedes another, the fresh start that may be today's work.

Do not paste the whole report. Summarize, and link to the file.

### 3. Gate

Ask once, and get scope in the same question:

- **Conservative** — safe items only: prunable worktrees, merged ancestors,
  verified squash merges.
- **Conservative plus specific ask-first items** — name them.
- **Nothing** — report only.

Nothing destructive runs before this answer. Never widen the scope the user
gave, and never fold remote branch deletion into a local cleanup: that is a
separate question, asked separately.

### 4. Execute

Run the commands from the `### Safe` block in `report.md` **in the order they
appear**. The script has already ordered them correctly. Add approved ask-first
items to the same run, using the same ordering rules.

Verify afterward with a second audit and report what changed.

## Safety rules

These are ordering and correctness constraints, not preferences. Details and
failure modes are in [references/safety.md](references/safety.md).

1. **Release a worktree before deleting its branch.** `git branch -d` refuses
   while a worktree holds the ref.
2. **Never remove the worktree you are standing in.** Check out the base branch
   in the primary tree first.
3. **Never remove a worktree with uncommitted changes.** The report marks these
   `dirty` and keeps them; do not override.
4. **`-D` only against a verified PR head.** Squash-merged branches are never
   ancestors of `main`, so `-d` refuses and `-D` is required. That capital `D`
   skips git's safety check, so it is justified only by the tip matching the
   merged PR's `headRefOid` — which the audit checks for you.
5. **Deleting a local branch never deletes the remote.** Remote deletion is a
   separate step and needs its own approval.
6. **Do not trust `[gone]`.** The upstream marker is only as fresh as the last
   prune; the audit asks the remote directly with `git ls-remote`.

## When PR state is unavailable

Without `gh`, branches that would be `pr-merged-verified` fall back to
`unmerged-no-pr` and are kept. That is the intended failure direction: the
audit's answer gets less useful, never less safe. Say so when presenting, so the
user knows the safe set is incomplete rather than empty.

## Validation

```bash
skills/ess/git-tidy/scripts/test_audit.sh
```

Builds a throwaway repo exhibiting every category, runs the audit against it,
and asserts the classification, the remediation ordering, and that the audit
mutated nothing. Fully offline: the remote is a local bare repo and PR state
comes from a fixture.

## References

- [references/classification.md](references/classification.md) — the decision
  matrix and the git plumbing behind each signal
- [references/safety.md](references/safety.md) — ordering constraints, failure
  modes, and recovery
