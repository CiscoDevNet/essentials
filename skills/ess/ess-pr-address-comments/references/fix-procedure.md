# Per-PR fix procedure

How one PR's approved plan becomes code, a commit, and resolved threads. The Phase 3
subagent (or the orchestrator, when it runs a single PR inline) follows these steps inside
that PR's worktree. Inputs come from [`scripts/fetch-pr.sh`](../scripts/fetch-pr.sh):
`meta.env` for owner, repo, number, and branch, and `threads.json` for the full
conversation. `threads.json` has one object per comment (`threadId`, `commentId`,
`path`, `line`, `root`, `body`). Reply to the comment whose `root` is true.

## 1. Implement

For each "fix" item in the approved plan:

1. **Read** the file and the surrounding context.
2. **Implement** the fix the reviewer asked for.
3. **Check** consistency: grep for stale references to anything you renamed or moved.

Group related fixes, such as several comments on the same file, to avoid redundant reads.
Track which `commentId`s received a code fix; only those are replied to and resolved in
step 4. Do nothing for "skip" items.

## 2. Verify

Run checks that match the nature of the fixes, and keep them cheap:

```bash
rg "<old-term>" <relevant-dirs>/   # no stale references left
ls <dir>/                          # file layout matches the docs
```

Run the repo's linters or tests for the files you touched when they apply.

## 3. Commit

Commit with [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification),
non-interactively. Never use `cz c` here: it prompts, and a background subagent has no
TTY to answer it.

```bash
git add <files>
git commit -m "fix(<scope>): address PR #<N> review comments" \
  -m "<brief description of what was fixed>"
```

| Type | When to use |
|------|-------------|
| `fix` | Addressing review comments, bug fixes |
| `refactor` | Code restructuring without behavior change |
| `docs` | Documentation-only changes |
| `style` | Formatting, whitespace |
| `chore` | Tooling, config, non-production changes |

Push with `"$SKILL_DIR/scripts/safe-push.sh" --branch <BRANCH>`, never a bare `git push`.
`SKILL_DIR` is the absolute path of this skill, resolved before entering the PR worktree.
See SKILL.md "Resilience" for why.

## 4. Reply and resolve addressed threads

For each thread addressed in step 1, run
[`scripts/reply-and-resolve.sh`](../scripts/reply-and-resolve.sh):

```bash
"$SKILL_DIR/scripts/reply-and-resolve.sh" \
  --repo <owner>/<repo> --pr <N> \
  --comment-id <root commentId> --thread-id <threadId> \
  --body "Fixed — <what changed>"
```

Reply format:

- Be concise: "Fixed — <what was done>."
- Name the specific change when it helps: "Changed `grep hello-world` to `grep hello-agent-auth`."
- Do not repeat the reviewer's comment back to them.

Only resolve threads whose comments were addressed in code. Leave threads that need
discussion, or that were skipped or deferred, open.

### API gotchas

The helper already does this correctly; these matter if you ever call `gh` by hand.

- **Reply** with `POST /repos/{owner}/{repo}/pulls/{number}/comments` and an `in_reply_to`
  field. The older `/replies` sub-resource returns 404.
- **Resolve** with the GraphQL `resolveReviewThread` mutation. REST has no resolve
  endpoint, and `minimizeComment` only hides a comment; it does not resolve the thread.

## Error handling

| Error | Cause | Fix |
|-------|-------|-----|
| 404 on reply | Used the `/replies` sub-resource | Use `POST /pulls/{number}/comments` with `in_reply_to` |
| 422 on resolve | Thread already resolved | Safe to ignore; the thread is already in the desired state |
| 403 on GraphQL | Token lacks `write:discussion` scope | `gh auth refresh -s write:discussion` |
