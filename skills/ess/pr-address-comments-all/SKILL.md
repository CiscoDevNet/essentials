---
name: pr-address-comments-all
description: Address GitHub PR review comments on one or more PRs in parallel, each in its own git worktree on the PR's branch, reusing the pr-address-comments procedure. Auto-starts (look up PRs, create worktrees, fetch comments), then pauses to show a per-PR addressing plan for approval; after approval each PR is handled by a background subagent that implements, commits, pushes to the PR branch, and resolves threads. With no PR given, it discovers your own open PRs on the current repo's remote that have changes-requested or unresolved review comments and runs the same workflow. Use when the user gives one or more PR URLs/numbers, or asks to address/fix review comments on their own open PRs on this repo without naming them, especially in parallel or batch.
---

# PR Address Comments — All (parallel, one worktree per PR)

Address review comments across **one or more** GitHub PRs at the same time. Each PR is
isolated in its own git worktree checked out **on the PR's branch**, so work commits
locally and pushes straight back to the PR. This skill orchestrates the existing single-PR
procedure in [pr-address-comments/SKILL.md](../pr-address-comments/SKILL.md) — it does
not re-document its `gh`/GraphQL/commit steps; helper scripts and reference docs hold the
mechanics.

## Quick start

```
You: address the review comments on my open PRs
You: fix my PRs that need changes
You: address the review comments on PRs 103 and 110
You: fix the comments on https://github.com/<owner>/<repo>/pull/103
You: address comments on PR 103, 110, 121 in parallel
```

Phases with **one human checkpoint** between analysis and code:

```
Phase 0 (auto)  -> if no PR given, discover my open PRs that need attention (current repo)
Phase 1 (auto)  -> look up each PR, create a worktree on its branch, fetch comments
Phase 2 (auto)  -> draft a concrete fix-per-thread plan per PR (read-only)
GATE            -> show the plans, wait for your approval
Phase 3 (auto)  -> per PR: implement, commit, push to branch, reply + resolve threads
```

Phases 0–2 just start. Phase 3 never begins until you approve the plans, because a per-PR
subagent may not understand the whole-repo context.

## Inputs

- **Zero** or more PR references, each a **full URL**
  (`https://github.com/<owner>/<repo>/pull/<N>`) or a **bare number** (`103`).
- Bare numbers resolve against the current repo's remote.
- With **no** reference, Phase 0 discovers your open PRs on the current repo's remote that
  have changes-requested or >=1 unresolved review comment.

## Prerequisites

- `gh` CLI authenticated with access to each PR's repository.
- Inside a git repo; `git worktree` and `openssl` available.
- Write access to each PR's branch for pushing (`git_write`).

## Limitations

- **Same-repo PRs only.** The workflow fetches and pushes the PR head branch through the
  local repo's `origin` remote (`git fetch origin -- <branch>` / `git push origin <branch>`).
  **Fork-based PRs** — whose head branch lives in a fork or another remote — are not
  supported, because `origin` does not have that branch.

## Scripts

Invoke by workspace-relative path. Each takes `--help`.

| Script | Purpose |
|--------|---------|
| [`scripts/find_my_prs.sh`](scripts/find_my_prs.sh) | Discover my open PRs on the current repo with changes-requested or unresolved comments |
| [`scripts/fetch_pr.sh`](scripts/fetch_pr.sh) | Look up ONE PR ref -> `meta.env` + `comments.json` + `threads.json` |
| [`scripts/create_pr_worktree.sh`](scripts/create_pr_worktree.sh) | Create a worktree on the PR branch (`-B`) + run repo setup |
| [`scripts/safe_push.sh`](scripts/safe_push.sh) | Push HEAD to the PR branch without hanging — auto-rebases if the branch moved, fails cleanly on conflict |
| [`scripts/reply_and_resolve.sh`](scripts/reply_and_resolve.sh) | Reply to a comment (REST `in_reply_to`) + resolve its thread (GraphQL) |

---

## Phase 0 — Discover my PRs (when no PR given)

If the user named no PR, find their own open PRs on the **current repo's remote** that need
attention (review decision `CHANGES_REQUESTED`, or >=1 unresolved review thread):

```bash
SKILL=skills/ess/pr-address-comments-all
mapfile -t PRS < <("$SKILL/scripts/find_my_prs.sh")   # current repo, my open PRs
```

The script prints a table to stderr and the matching PR numbers to stdout. If `PRS` is
empty, report "no open PRs need attention" and stop. Otherwise **auto-proceed** to Phase 1
for each number in `PRS` (in parallel) — no extra confirmation; the per-PR plan GATE before
any code still applies. Discovery is scoped to the current repo only; for other repos, pass
explicit PR URLs.

## Phase 1 — Look up PRs and create worktrees (auto-start)

"Look up" = parse each input into `owner/repo/number` + head branch. This is distinct from
"resolve threads" (the GraphQL `resolveReviewThread` step in Phase 3).

Pre-flight once: `gh auth status` and `git rev-parse --show-toplevel` must both succeed.

Then, **for each PR in parallel**:

```bash
SKILL=skills/ess/pr-address-comments-all

# 1) Look up the PR -> writes meta.env + comments.json + threads.json
"$SKILL/scripts/fetch_pr.sh" <pr-ref>            # add --repo owner/repo for a bare number

# 2) Create a worktree checked out on the PR's branch + run worktrees.json setup
"$SKILL/scripts/create_pr_worktree.sh" --pr <N> --repo <owner>/<repo>
```

Record each PR's `meta.env` values plus the printed `WORKTREE_ID` / `WORKTREE_PATH`.
Skip any PR whose `threads.json` is empty (no unresolved comments) and note it in the
summary. Worktree internals and edge cases:
[references/worktree-mechanics.md](references/worktree-mechanics.md).

## Phase 2 — Draft a per-PR addressing plan (parallel, read-only)

For each PR, launch one read-only `explore` subagent pointed at its `WORKTREE_PATH` using
the analysis template in
[references/subagent-prompts.md](references/subagent-prompts.md). It reads the code behind
each thread and returns a concrete fix-per-thread table (or "skip" with a reason). No edits.

Run all analysis subagents concurrently.

## GATE — Approve the plan (required)

Compile every PR's returned plan into one view and **stop for the user**:

```markdown
## Plan to address comments

### PR #<N> — <title>  (branch `<BRANCH>`, <count> comments, worktree `<WORKTREE_ID>`)
| # | File:Line | Reviewer ask | Proposed fix | Action |
|---|-----------|--------------|--------------|--------|
| 1 | path:42   | ...          | ...          | fix    |
| 2 | path:17   | ...          | ...          | skip — needs discussion |
```

The `File:Line` column comes straight from each thread's `path` and `line` in
`threads.json` (see [`scripts/fetch_pr.sh`](scripts/fetch_pr.sh)).

Wait for explicit approval. Allow the user to edit, drop, or skip items per PR. Do not
start Phase 3 until approved; if changes are requested, revise and re-present.

## Phase 3 — Implement, commit, push, resolve (parallel)

For each approved PR, launch one background `generalPurpose` subagent using the
implementation template in
[references/subagent-prompts.md](references/subagent-prompts.md). Each subagent works
entirely inside its `WORKTREE_PATH`, follows
[pr-address-comments/SKILL.md](../pr-address-comments/SKILL.md) Steps 6–8
(implement -> verify -> **non-interactive** conventional commit), pushes with
`"$SKILL/scripts/safe_push.sh" --branch <BRANCH>` (with `SKILL=skills/ess/pr-address-comments-all`), then calls
`"$SKILL/scripts/reply_and_resolve.sh"` for each ADDRESSED thread (never for "skip" threads).

Run all implementation subagents concurrently; each pushes to its own branch.

> **Background subagents have no TTY.** Any command that waits for input (interactive
> `cz c`, `git pull --rebase` that stops on a conflict, a pager, a credential prompt)
> hangs that subagent forever. Subagents MUST use non-interactive git and push via
> `safe_push.sh` — see [Resilience](#resilience--moving-branches--stuck-subagents).

## Resilience — moving branches & stuck subagents

The branch can move **while** a subagent is working (you push to it, CI amends it, or a
human reviewer pushes). A raw `git push` then fails non-fast-forward, and the classic
follow-up — interactive `git pull --rebase` — drops a TTY-less subagent into a conflict
prompt it can never answer, so it hangs indefinitely. Guard against this on both sides:

**Subagent side (built into the template):**

- Push only via `"$SKILL/scripts/safe_push.sh" --branch <BRANCH>`. It forces non-interactive git,
  retries the push, auto-rebases when the remote moved with non-conflicting changes, and
  on a real conflict **aborts the rebase** (leaving a clean tree) and exits `3` instead of
  blocking. Never run a bare `git push`/`git pull --rebase` in a subagent.
- Commit non-interactively (manual `git commit -m`, never `cz c`).
- If anything can't be finished autonomously, **stop and report the exact state** — never
  leave a rebase/merge in progress.

**Orchestrator side (watchdog):** after dispatching the background subagents, do not block
on them indefinitely. If a subagent runs far past its expected time with no result, or
returns a `SAFE_PUSH_CONFLICT` / non-zero push, **finish that PR inline** instead of
waiting or re-dispatching: in its worktree, `git fetch origin -- <BRANCH>` then rebase the
subagent's fix commit onto `origin/<BRANCH>` (or `git reset --hard origin/<BRANCH>` and
re-apply the approved fixes), `"$SKILL/scripts/safe_push.sh" --branch <BRANCH>` (with
`SKILL=skills/ess/pr-address-comments-all`), and `"$SKILL/scripts/reply_and_resolve.sh"`.
Never run two agents
against the same branch at once — if a tick/retry finds a PR already has an in-flight fix,
skip it.

## Aggregate summary

After all subagents finish, present one combined table:

```markdown
## Done — <K> PRs

| PR | Branch | Addressed | Skipped | Resolved threads | Commit | Pushed |
|----|--------|-----------|---------|------------------|--------|--------|
| #103 | feat/x | 3 | 1 | 3/4 | abc1234 | yes |
| #110 | fix/y  | 2 | 0 | 2/2 | def5678 | yes |
```

Call out any PR that failed to push, had no comments, or needs follow-up discussion.

## Cleanup

Each worktree is on the PR branch and has already pushed — nothing to merge back. Remove
each when done (`git worktree remove "$WORKTREE_PATH" && git worktree prune`, or
`/delete-worktree <WORKTREE_ID>`). Details:
[references/worktree-mechanics.md](references/worktree-mechanics.md). Confirm before
removing any worktree whose push failed.

## Progressive disclosure

- Worktree-on-branch rationale, layout, cleanup, edge cases ->
  [references/worktree-mechanics.md](references/worktree-mechanics.md).
- Phase 2 / Phase 3 subagent prompt templates ->
  [references/subagent-prompts.md](references/subagent-prompts.md).
- Script flags -> run any script with `--help`.
- The per-PR commit / reply / resolve specifics ->
  [pr-address-comments/SKILL.md](../pr-address-comments/SKILL.md) Steps 6–9.

## Anti-patterns

- Starting Phase 3 before the user approves the GATE — never touch code first.
- Resolving "skip" threads — only reply + resolve threads actually addressed in code.
- Fabricating comments/threads when `gh` fails — surface the failure instead.
- Detached worktrees for this flow — use `-B` so commits land on the PR branch (see
  worktree-mechanics.md for the one exception).
- Duplicating the command's Steps 6–9 in subagent prompts — reference them, don't copy.
- Stacking multiple PRs in one worktree — one worktree per PR, always.
- Running discovery against a repo you didn't intend — Phase 0 always uses the current
  remote; pass explicit PR URLs for any other repo.
- Interactive commands in a background subagent (`cz c`, `git pull --rebase` on a conflict,
  a pager) — they have no TTY and will hang forever. Commit with `git commit -m` and push
  via `safe_push.sh`.
- A bare `git push` in a subagent with no recovery — use `safe_push.sh` so a moved branch
  rebases or fails cleanly instead of stalling.
- Leaving a rebase/merge in progress when a subagent gives up — always abort to a clean
  tree and report, so the orchestrator can finish inline.
- Blocking forever on a stalled subagent, or dispatching a second agent for the same PR —
  watchdog the run and finish inline instead.
