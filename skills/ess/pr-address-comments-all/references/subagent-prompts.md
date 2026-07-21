# Subagent prompt templates

Reusable prompts the orchestrator passes to the per-PR subagents. Fill in the
`<...>` placeholders from each PR's `meta.env` / `threads.json` (produced by
[`scripts/fetch_pr.sh`](../scripts/fetch_pr.sh)) and the worktree path (from
[`scripts/create_pr_worktree.sh`](../scripts/create_pr_worktree.sh)).

## Phase 2 — analysis (read-only)

One per PR. Launch as an `explore` subagent with `readonly: true` and
`run_in_background: true`. It must NOT edit anything — it only proposes fixes.

```
Repo worktree (read-only): <WORKTREE_PATH>
PR #<N> in <owner>/<repo>, branch <BRANCH>.

For each review thread below, read the referenced file and surrounding code in
this worktree and propose a concrete, minimal fix. If a thread needs discussion
rather than a code change, mark it "skip" and say why. Do NOT edit anything.

Threads (from threads.json — path | line | comment | threadId | commentId):
<paste the NDJSON rows from <OUTPUT_DIR>/threads.json>

Return a markdown table with columns:
# | path:line | reviewer ask | proposed fix (files + approach) | action (fix/skip)
```

## Phase 3 — implementation (read/write, background)

One per PR. Launch as a `generalPurpose` subagent with `run_in_background: true`
only AFTER the user approves the plan at the GATE. Embed that PR's approved plan
verbatim.

```
Work entirely inside this worktree: <WORKTREE_PATH>  (cd there first).
It is already checked out on branch <BRANCH> for PR #<N> in <owner>/<repo>.

You are a BACKGROUND subagent with NO terminal. Never run a command that waits
for input — it will hang you forever. So: no `cz c`, no bare `git pull --rebase`,
no pager. Up front, force non-interactive git:
    export GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true GIT_PAGER=cat PAGER=cat GIT_TERMINAL_PROMPT=0

Read skills/ess/pr-address-comments/SKILL.md and follow Steps 6–8 for this
PR, using the APPROVED PLAN below as the exact list of fixes to make:

<approved per-PR plan from the GATE>

Specifics:
- Step 6: implement each "fix" item. Skip items marked "skip".
- Step 7: verify (grep for stale refs; run cheap, relevant linters/tests).
- Step 8: conventional-commit non-interactively (NOT `cz c`):
    git commit -m "fix(<scope>): address PR #<N> review comments"
- Push with the safe helper (handles a branch that moved under you; never hangs):
    skills/ess/pr-address-comments-all/scripts/safe_push.sh --branch <BRANCH>
  If it exits 3 (SAFE_PUSH_CONFLICT) or otherwise non-zero, STOP — do NOT leave a
  rebase in progress — and report the exact state so the orchestrator finishes
  inline. Do not retry endlessly or improvise an interactive rebase.
- For each ADDRESSED thread, reply + resolve via the helper (do NOT resolve
  "skip" threads):
    skills/ess/pr-address-comments-all/scripts/reply_and_resolve.sh \
      --repo <owner>/<repo> --pr <N> \
      --comment-id <commentId> --thread-id <threadId> \
      --body "Fixed — <what changed>"

Return: commit SHA, files changed, threads replied-to/resolved, threads skipped,
and the push result (including any SAFE_PUSH_CONFLICT/non-zero exit).
```

## Notes

- Steps 6–8 (implement / verify / commit) are NOT duplicated here — the subagent
  follows them from `skills/ess/pr-address-comments/SKILL.md`, with two background
  overrides: commit with `git commit -m` (Step 8's `cz c` is interactive and would
  hang a TTY-less subagent), and push via `safe_push.sh` instead of a bare
  `git push` (so a branch that moved mid-run rebases or fails cleanly).
- `reply_and_resolve.sh` and `safe_push.sh` live in the repo, so they are present
  inside the worktree (a checkout of the same repo) and can be called by their
  workspace-relative paths.
- A `SAFE_PUSH_CONFLICT` (exit 3) is the orchestrator's cue to finish that PR
  inline — see SKILL.md "Resilience". The subagent must report it, not retry.
- For a single PR, the orchestrator may run Phases 2–3 inline instead of spawning
  subagents — there is no parallelism to gain.
