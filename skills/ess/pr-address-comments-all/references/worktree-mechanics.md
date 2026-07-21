# Worktree mechanics

How `pr-address-comments-all` isolates each PR in its own git worktree and why
it differs from the stock `/worktree` command. The script
[`scripts/create_pr_worktree.sh`](../scripts/create_pr_worktree.sh) implements
all of this; read here when you need to understand or debug it.

## `-B <branch>` instead of `--detach`

`/worktree` creates a **detached** worktree (`git worktree add --detach`), which
is right for throwaway experiments but awkward for PR work: there is no branch
to commit onto or push from.

This skill instead creates a worktree **on the PR's head branch**:

```bash
git worktree add -B "$BRANCH" "$WORKTREE_DIR" "origin/$BRANCH"
```

`-B` creates (or resets) a real local branch `$BRANCH` pointing at
`origin/$BRANCH` and checks it out in the new worktree. As a result:

- Commits land directly on the PR branch.
- `git push origin "$BRANCH"` updates the PR — no `push HEAD:<branch>` dance.
- There is nothing to merge back into the main working tree, so `/apply-worktree`
  is not part of this workflow.

## On-disk layout (so `/delete-worktree` still works)

The worktree is created under the **same tree** the `/worktree` command uses, with
the same repo-key scheme, so cleanup tooling recognizes it:

```
~/.cursor/worktrees/<WORKTREE_ID>/<REPO_KEY>
```

- `WORKTREE_ID = pr-<number>-<8 hex>` — unique per PR, so multiple PRs never collide.
- `REPO_KEY  = <repo-basename>-<sha256(REPO_ROOT)[:12]>` — identical to the
  `/worktree` create block, so the path is one `/worktree`-style worktree would
  produce.

Because each PR gets a distinct `WORKTREE_ID`, every PR is independently
removable.

## Setup

After creating the worktree, the script runs the repo's `setup-worktree` steps
from `.cursor/worktrees.json` with `ROOT_WORKTREE_PATH` exported to the main repo
root (jq-parsed when available, otherwise the documented default). For this repo
that is: rsync `.env` files from the main tree, then `uv sync --all-packages`.

## Cleanup

Each worktree has already pushed to the PR branch, so just remove it:

```bash
git worktree remove "$WORKTREE_PATH"   # add --force if it complains about state
git worktree prune
```

Or, since the layout matches `/worktree`, use `/delete-worktree <WORKTREE_ID>`
per PR. Confirm with the user before removing any worktree whose push failed.

## Edge cases

### Branch already checked out elsewhere

`git worktree add -B` refuses if `$BRANCH` is checked out in the main tree or
another worktree (git forbids the same branch in two worktrees). Options:

- Reuse the existing checkout instead of creating a new worktree, or
- Create the worktree detached and push explicitly:

  ```bash
  SKILL=skills/ess/pr-address-comments-all
  git worktree add --detach "$WORKTREE_DIR" "origin/$BRANCH"
  # ... commit ...
  "$SKILL/scripts/safe_push.sh" --branch "$BRANCH"   # pushes HEAD:<branch>, rebases if moved
  ```

  `safe_push.sh` already pushes `HEAD:<branch>`, so it works the same whether the
  worktree is attached (`-B`) or detached — and it will not hang if the branch
  moved while you worked.

### Cross-repo PRs

When PRs span multiple repositories (full URLs in different repos), run
`create_pr_worktree.sh` from **each PR's own repo root** so `REPO_ROOT` and the
remote resolve correctly. Always pass `--repo owner/repo` so a bare-number
assumption from one repo never leaks into another.
