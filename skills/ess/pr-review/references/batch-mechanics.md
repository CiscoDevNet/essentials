# Batch mechanics (N > 1)

How `pr-review` reviews **multiple** PRs at once. Read this only when the set has
more than one PR — a single-PR review (N = 1) uses the in-place fast path in
`SKILL.md` and never touches any of this.

The core idea: give each PR its own **read-only** worktree, run the scan +
judgment for it in a **read-only subagent**, collect each subagent's proposed
findings, then converge on the single GATE in `SKILL.md` Step 7 before anything
is posted.

## Why worktrees + subagents (and why read-only)

- **Isolation**: N PRs on different branches cannot share one working tree; each
  needs its own checkout so linters see the right code.
- **Parallelism**: one subagent per PR runs the scan and judgment concurrently.
- **Read-only**: review posts comments, it never edits code. So worktrees are
  created **detached at the PR head SHA** (`git worktree add --detach`), and the
  subagents are told to edit nothing. This is the key contrast with
  `pr-address-comments-all`, whose worktrees use `-B <branch>` because it writes
  fixes back to the PR.

## Per-PR worktree layout

[`scripts/create_review_worktree.sh`](../scripts/create_review_worktree.sh)
creates each worktree and provisions it (runs `.cursor/worktrees.json`
`setup-worktree`, or a best-effort `.env` + `uv sync` default):

```
~/.cursor/worktrees/<WORKTREE_ID>/<REPO_KEY>
```

- `WORKTREE_ID = pr-<number>-<8 hex>` — unique per PR, so PRs never collide.
- `REPO_KEY = <repo-basename>-<sha256(REPO_ROOT)[:12]>` — matches the `/worktree`
  command, so `/delete-worktree` recognizes it.

Run it once per PR from the repo root:

```bash
scripts/create_review_worktree.sh --pr <N> --repo <owner>/<repo>
# prints WORKTREE_ID=..., WORKTREE_PATH=..., HEAD_SHA=...
```

For cross-repo sets (full URLs in different repos), run it from **each PR's own
repo root** and always pass `--repo owner/repo`.

## Per-PR review subagent (read-only)

Launch one subagent per PR. Use an `explore` subagent with `readonly: true` and
`run_in_background: true` so they run in parallel. Each must post nothing and
edit nothing — it only returns proposed findings for the GATE.

First resolve `<SKILL_DIR_ABS>` = the absolute path to the directory holding the
`pr-review` skill you are running (the one that contains this `SKILL.md`,
`scripts/`, and `references/`). Pass it into each subagent so the scan script and
reference docs are reachable **by absolute path** — the worktree is a detached
checkout of the PR head and may not contain the skill at all (it is only on your
branch), or may contain a stale copy.

Fill in `<...>` from `create_review_worktree.sh` output and the PR metadata:

```
Repo worktree (READ-ONLY, detached at the PR head): <WORKTREE_PATH>
PR #<N> in <owner>/<repo>. pr-review skill dir: <SKILL_DIR_ABS>

cd into that worktree. Do NOT edit, commit, push, or post anything.

1. Run the deterministic scan by ABSOLUTE path (the worktree does not contain
   the skill), passing --number so this PR gets its own output dir:
     bash "<SKILL_DIR_ABS>/scripts/scan-pr.sh" \
       --base origin/<baseRef> --head <HEAD_SHA> \
       --number <N> --repo <owner>/<repo>
   Read the generated report.md (its path is printed on the last line;
   it is /tmp/pr-review-<owner>-<repo>-<N>).
2. Do the LLM judgment pass and high-signal filtering exactly as
   <SKILL_DIR_ABS>/SKILL.md Steps 5–6 describe (correctness vs intent,
   cross-file logic, resource cleanup, suppression justifications, AGENTS.md
   rules, version-scoped deprecations; <SKILL_DIR_ABS>/references/agent-conventions.md
   for LangChain files).
3. Dedup against existing reviews/comments on the PR.

Return ONLY a proposed-findings table for this PR (post nothing):
  # | severity | path:line | issue | proposed fix | post mode suggestion
Also note: files scanned, any linters that did not run, and whether the PR
should be skipped (draft / already reviewed / trivial) with the reason.
```

The scan script and reference docs come from `<SKILL_DIR_ABS>` (your checkout),
not the worktree — do not assume a workspace-relative
`skills/ess/pr-review/...` path resolves inside the worktree. The worktree only
supplies the code under review: it is the scan's working directory, and because
worktrees share the repo object store, `origin/<baseRef>` is already available.
Reports are written under `/tmp`, so the worktree stays read-only, and the
`--number <N>` gives each PR its own `/tmp/pr-review-<owner>-<repo>-<N>` dir so
concurrent scans never overwrite each other.

## GATE aggregation

Collect every subagent's table and present them together as one approval point
(`SKILL.md` Step 7): group by PR, list skips and their reasons, and show
per-finding severity / `path:line` / fix. The user edits or drops findings and
picks a post mode per PR. Only after approval do you post (Step 8), one comment
per unique issue, in each PR's chosen mode.

For a single PR the orchestrator runs the scan + judgment inline instead of
spawning a subagent — there is no parallelism to gain.

## Cleanup

After posting, remove each worktree:

```bash
git worktree remove "$WORKTREE_PATH"   # add --force if it complains about state
git worktree prune
```

Or, since the layout matches `/worktree`, `/delete-worktree <WORKTREE_ID>` per
PR. Nothing was committed or pushed (detached, read-only), so removal is safe.

## Edge cases

- **PR head moves mid-run**: worktrees are pinned to the `HEAD_SHA` captured at
  creation, so the review is consistent even if the author pushes more commits.
  Note in the GATE if a PR advanced past what you reviewed.
- **Fork PRs**: out of scope (same-origin only).
- **A subagent fails to scan** (e.g. missing linter): it still returns judgment
  findings and flags which linters did not run; surface that at the GATE rather
  than silently dropping the PR.
