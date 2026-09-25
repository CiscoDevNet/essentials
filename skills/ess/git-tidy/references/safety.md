# Safety

Ordering constraints, the failure modes they prevent, and how to recover when
something still goes wrong.

## Execution order

`report.md` emits its `### Safe` block in this order. It is not cosmetic — each
step removes a blocker for the next.

```bash
git checkout <base>                  # 1. only if you are on a branch being deleted
git worktree remove "<path>"         # 2. release worktrees holding those branches
git worktree prune                   # 3. drop registrations whose directory is gone
git branch -d <merged ancestors>     # 4. lossless deletes
git branch -D <verified squashes>    # 5. forced deletes, each one verified
```

**1 before 4 and 5.** Git refuses to delete the branch you have checked out.
Without this, the last item in the list fails and you are left half done.

**2 before 4 and 5.** A branch checked out in *any* worktree is protected the
same way:

```
error: Cannot delete branch 'ancestor' checked out at '/path/to/wt-ancestor'
```

**3 after 2.** `git worktree prune` only removes registrations whose directory
is already gone. Running it first is harmless but accomplishes nothing; running
it after keeps the bookkeeping in one place.

**4 before 5.** Not a hard dependency, only sequencing that keeps the risky
operation last, where a mistake in the safe half is still recoverable.

## Never remove the worktree you are standing in

`git worktree remove` on your own working directory leaves the shell in a
deleted path, where nearly every subsequent command fails in a confusing way.
The audit marks that worktree `current` and keeps it. To remove it, `cd` into
the primary tree first, then re-run the audit so the classification reflects
where you now stand.

## Never remove a dirty worktree

`git worktree remove` refuses when there are uncommitted changes, and
`--force` overrides that refusal. Nothing in this skill emits `--force`. A dirty
worktree is someone's unsaved work; the recovery path is `git stash` or a
commit, both of which are the owner's decision, not the cleanup's.

If a worktree is dirty only because of build artifacts, that is a `.gitignore`
bug worth fixing rather than forcing past.

## `-d` versus `-D`

`git branch -d` refuses to delete a branch holding commits not reachable from
HEAD or its upstream. That refusal is the safety net, and `-D` removes it.

Squash merges force the issue. GitHub's squash creates a single new commit on
`main` with a different SHA and different parentage, so the original branch is
never an ancestor of `main` no matter how thoroughly its content landed. `-d`
cannot tell that branch apart from genuinely unmerged work, so it refuses, and
`-D` becomes the only way to delete it.

That makes `-D` routine, which makes it dangerous. The audit only puts a branch
in the `-D` list when the local tip SHA equals the merged PR's `headRefOid` —
proof that the exact commit you are deleting is the one GitHub squashed. When
the tip has moved (`pr-merged-diverged`), the extra commits exist nowhere else
and the branch goes to the ask pile instead.

Never hand-extend the `-D` list with a branch the audit did not verify.

## Local and remote deletion are separate

`git branch -d` touches only the local ref. The remote branch survives, along
with the PR and its history. This is deliberate: local cleanup is cheap and
reversible for a while, remote deletion affects everyone and can break links.

If remote deletion is genuinely wanted, it is a separate question with its own
approval, and worth checking that no open PR targets the branch first. Note that
many repos delete the head branch automatically on merge, so the remote is often
already gone.

## Failure modes

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `Cannot delete branch 'x' checked out at ...` | A worktree still holds it | Remove that worktree first; re-read the ordering above |
| `error: the branch 'x' is not fully merged` | Squash merge, or genuinely unmerged | Only use `-D` if the audit classified it `pr-merged-verified` |
| `fatal: '<path>' contains modified or untracked files` | Dirty worktree | Do not force. Commit, stash, or leave it |
| Audit reports every branch as `unmerged-no-pr` | `gh` missing or unauthenticated | `gh auth status`, then re-run; or accept the conservative result |
| A deleted remote branch still reads `live` | Stale local view | The audit uses `git ls-remote`, so this means the remote really does still have it |
| Report lists a worktree whose directory you deleted | Registration outlives the directory | That is `prunable`; `git worktree prune` clears it |

## Recovery

A deleted local branch is recoverable for as long as the reflog keeps its tip,
which defaults to 90 days:

```bash
git reflog --no-abbrev | grep <branch-name>
git branch <branch-name> <sha>
```

The audit prints every branch's tip SHA into `branches.tsv` and `report.json`
before deleting anything, so the previous report is itself a recovery record.
Keep the output directory until you are satisfied with the result.

Worktree removal is not recoverable in the same way, but nothing is lost: a
worktree is a checkout, and the commits live in the shared object store. Re-add
it with `git worktree add <path> <branch>`. Only uncommitted changes are
genuinely gone, which is why dirty worktrees are never touched.

## What the audit will not do

`audit.sh` never deletes, never force-pushes, never rewrites history, and never
writes to the repository it inspects. It prints commands. The only writes it
performs are to its output directory, and to remote-tracking refs when you pass
`--fetch`. Keeping execution in the agent's hands, after an explicit approval,
is what makes the single gate meaningful.
