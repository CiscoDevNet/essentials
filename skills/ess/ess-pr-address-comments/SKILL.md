---
name: ess-pr-address-comments
description: Address GitHub PR review comments, implement fixes on the PR branch, push, then reply to and resolve the addressed threads. Handles one PR or many in parallel, each in its own git worktree on the PR's branch. Auto-starts (look up PRs, create worktrees, fetch comments), then pauses to show a per-PR addressing plan for approval; after approval each PR is handled by a background subagent that implements, commits, pushes to the PR branch, and resolves threads. With no PR given, it discovers your own open PRs on the current repo's remote that have changes-requested or unresolved review comments and runs the same workflow. Use for /ess-pr-address-comments, when the user gives one or more PR URLs or numbers, or asks to address/fix review comments on their own open PRs on this repo without naming them.
---

# PR Address Comments

Address review comments on **one or more** GitHub PRs, in parallel when there are several.
Each PR is isolated in its own git worktree checked out **on the PR's branch**, so work
commits locally and pushes straight back to the PR. Helper scripts and reference docs hold
the `gh`/GraphQL/commit mechanics.

## Quick start

```
/ess-pr-address-comments                     # discover my open PRs that need attention
/ess-pr-address-comments 103
/ess-pr-address-comments https://github.com/<owner>/<repo>/pull/103
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

Every phase runs these from `SKILL_DIR`: the absolute path of the directory that
contains this `SKILL.md`. Resolve it once, before Phase 0, and reuse it. Do not use a
repo-relative path; the skill may be installed outside the repo you are working in.
Each script takes `--help`.

| Script | Purpose |
|--------|---------|
| [`scripts/find-my-prs.sh`](scripts/find-my-prs.sh) | Discover my open PRs on the current repo with changes-requested or unresolved comments |
| [`scripts/fetch-pr.sh`](scripts/fetch-pr.sh) | Look up ONE PR ref -> `meta.env` + `comments.json` + `threads.json` |
| [`scripts/create-pr-worktree.sh`](scripts/create-pr-worktree.sh) | Create a worktree on the PR branch (`-B`) + run repo setup |
| [`scripts/safe-push.sh`](scripts/safe-push.sh) | Push HEAD to the PR branch without hanging — auto-rebases if the branch moved, fails cleanly on conflict |
| [`scripts/reply-and-resolve.sh`](scripts/reply-and-resolve.sh) | Reply to a comment (REST `in_reply_to`) + resolve its thread (GraphQL) |

---

## Phase 0 — Discover my PRs (when no PR given)

If the user named no PR, find their own open PRs on the **current repo's remote** that need
attention (review decision `CHANGES_REQUESTED`, or >=1 unresolved review thread):

```bash
SKILL_DIR=<absolute path of the directory containing this SKILL.md>
# bash and zsh. Check the exit status yourself: a process substitution would hide a
# failing script and look like an empty list, and mapfile is not available in zsh.
PR_OUTPUT="$("$SKILL_DIR/scripts/find-my-prs.sh")" || {
  echo "Discovery failed; stopping." >&2
  exit 1
}
PRS=()
while IFS= read -r pr; do
  [ -n "$pr" ] && PRS+=("$pr")
done <<< "$PR_OUTPUT"
```

The script prints a table to stderr and the matching PR numbers to stdout. If it exits
non-zero, stop and report the failure. Do not treat that as an empty result. If `PRS` is
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
# 1) Look up the PR -> writes meta.env + comments.json + threads.json
"$SKILL_DIR/scripts/fetch-pr.sh" <pr-ref>        # add --repo owner/repo for a bare number

# 2) Create a worktree checked out on the PR's branch + run worktrees.json setup
"$SKILL_DIR/scripts/create-pr-worktree.sh" --pr <N> --repo <owner>/<repo>
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
`threads.json` (see [`scripts/fetch-pr.sh`](scripts/fetch-pr.sh)).

Wait for explicit approval. Allow the user to edit, drop, or skip items per PR. Do not
start Phase 3 until approved; if changes are requested, revise and re-present.

## Phase 3 — Implement, commit, push, resolve (parallel)

Pass each subagent the absolute `SKILL_DIR` resolved before Phase 0. The PR worktree
may be an older checkout or another repository, so it may not contain
`fix-procedure.md` or the helper scripts. The subagent reads procedures and runs helpers
from `$SKILL_DIR`. Code edits stay in the PR worktree.

For each approved PR, launch one background `generalPurpose` subagent using the
implementation template in
[references/subagent-prompts.md](references/subagent-prompts.md). Each subagent works
entirely inside its `WORKTREE_PATH`, follows
`"$SKILL_DIR/references/fix-procedure.md"`
(implement -> verify -> **non-interactive** conventional commit), pushes with
`"$SKILL_DIR/scripts/safe-push.sh" --branch <BRANCH>`, then calls
`"$SKILL_DIR/scripts/reply-and-resolve.sh"` for each ADDRESSED thread (never for "skip" threads).

Run all implementation subagents concurrently; each pushes to its own branch.

> **Background subagents have no TTY.** Any command that waits for input (interactive
> `cz c`, `git pull --rebase` that stops on a conflict, a pager, a credential prompt)
> hangs that subagent forever. Subagents MUST use non-interactive git and push via
> `safe-push.sh` — see [Resilience](#resilience--moving-branches--stuck-subagents).

## Resilience — moving branches & stuck subagents

The branch can move **while** a subagent is working (you push to it, CI amends it, or a
human reviewer pushes). A raw `git push` then fails non-fast-forward, and the classic
follow-up — interactive `git pull --rebase` — drops a TTY-less subagent into a conflict
prompt it can never answer, so it hangs indefinitely. Guard against this on both sides:

**Subagent side (built into the template):**

- Push only via `"$SKILL_DIR/scripts/safe-push.sh" --branch <BRANCH>`. It forces non-interactive git,
  retries the push, auto-rebases when the remote moved with non-conflicting changes, and
  on a real conflict **aborts the rebase** (leaving a clean tree) and exits `3` instead of
  blocking. Never run a bare `git push`/`git pull --rebase` in a subagent.
- Commit non-interactively (manual `git commit -m`, never `cz c`).
- If anything can't be finished autonomously, **stop and report the exact state** — never
  leave a rebase/merge in progress.

**Orchestrator side (watchdog):** after dispatching the background subagents, do not block
on them indefinitely. Never run two agents against the same branch at once — if a tick or
retry finds a PR already has an in-flight fix, skip it.

- If a subagent **returns** a `SAFE_PUSH_CONFLICT` or other non-zero push, it has stopped.
  Finish that PR inline: in its worktree, `git fetch origin -- <BRANCH>`, then rebase the
  subagent's fix commit onto `origin/<BRANCH>` (or `git reset --hard origin/<BRANCH>` and
  re-apply the approved fixes), `"$SKILL_DIR/scripts/safe-push.sh" --branch <BRANCH>`, and
  `"$SKILL_DIR/scripts/reply-and-resolve.sh"`.
- If a subagent **times out** with no result, cancel it and confirm it has terminated
  before touching its worktree. A timeout does not mean it has stopped. If termination
  cannot be confirmed, report the stall and do not fetch, rebase, or reset that worktree.

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
- The per-PR implement / verify / commit / reply / resolve specifics and API error
  handling -> [references/fix-procedure.md](references/fix-procedure.md).

## Anti-patterns

- Starting Phase 3 before the user approves the GATE — never touch code first.
- Resolving "skip" threads — only reply + resolve threads actually addressed in code.
- Fabricating comments/threads when `gh` fails — surface the failure instead.
- Detached worktrees for this flow — use `-B` so commits land on the PR branch (see
  worktree-mechanics.md for the one exception).
- Duplicating `fix-procedure.md` in subagent prompts — reference it, don't copy.
- Stacking multiple PRs in one worktree — one worktree per PR, always.
- Running discovery against a repo you didn't intend — Phase 0 always uses the current
  remote; pass explicit PR URLs for any other repo.
- Interactive commands in a background subagent (`cz c`, `git pull --rebase` on a conflict,
  a pager) — they have no TTY and will hang forever. Commit with `git commit -m` and push
  via `safe-push.sh`.
- A bare `git push` in a subagent with no recovery — use `safe-push.sh` so a moved branch
  rebases or fails cleanly instead of stalling.
- Leaving a rebase/merge in progress when a subagent gives up — always abort to a clean
  tree and report, so the orchestrator can finish inline.
- Blocking forever on a stalled subagent, or dispatching a second agent for the same PR —
  watchdog the run and finish inline instead.
