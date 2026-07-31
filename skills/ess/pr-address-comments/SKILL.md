---
name: pr-address-comments
description: >-
  Read a remote GitHub PR's review comments, implement fixes on the PR branch,
  then reply to and resolve addressed threads (REST reply + GraphQL
  resolveReviewThread). Use for /pr-address-comments, a single PR URL or number,
  when not using the parallel batch skill pr-address-comments-all. Requires gh
  and a git checkout of the repo.
metadata:
  version: "1.0"
---

# PR Address Comments

Read a remote PR's review comments, implement fixes, then reply to and resolve the addressed threads.

**Phase**: Fix

## Quick start

```
/pr-address-comments https://github.com/<owner>/<repo>/pull/123
/pr-address-comments 103
```

---

## Prerequisites

- **GitHub CLI** (`gh`) — authenticated and with access to the repository
- The current directory must be a git repo (`.git/` present)

---

## Limitations

- GitHub's REST API does not have a "resolve thread" endpoint. Threads must be resolved via the **GraphQL API** using `resolveReviewThread`.
- The `minimizeComment` mutation hides comments but does NOT resolve threads — do not use it for this purpose.
- Reply endpoint: `POST /repos/{owner}/{repo}/pulls/{number}/comments` with `in_reply_to` field. The older `/replies` sub-resource returns 404.

---

## Instructions

### Step 1: Resolve the PR

Parse the user's input:

- If a **full URL** is provided (e.g., `https://github.com/org/repo/pull/123`), extract the owner, repo, and PR number directly.
- If only a **number** is provided, determine the remote from `.git`:

```bash
# Get the GitHub owner/repo from the git remote
gh repo view --json nameWithOwner --jq .nameWithOwner
```

### Step 2: Fetch PR Details and Review Comments

```bash
# Get PR metadata
gh pr view <NUMBER> --json title,body,state,headRefName,files

# Get inline review comments (these are the ones to address)
gh api repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments
```

Parse each comment for:
- `id` — the comment ID (needed for responding later)
- `path` — the file path
- `line` / `original_line` — the line number
- `body` — the reviewer's feedback

### Step 3: Get Unresolved Thread IDs (GraphQL)

Fetch thread metadata upfront so you can resolve them later:

```bash
gh api graphql -f query='
query {
  repository(owner: "<OWNER>", name: "<REPO>") {
    pullRequest(number: <NUMBER>) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes {
              databaseId
              path
              body
            }
          }
        }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | {threadId: .id, commentId: .comments.nodes[0].databaseId, path: .comments.nodes[0].path, body: .comments.nodes[0].body}'
```

This gives you both the **thread ID** (for resolving) and the **comment database ID** (for replying).

### Step 4: Categorize and Present

Show the user a summary:

```markdown
## PR #<NUMBER>: <TITLE>

### Review Comments (<COUNT>)

| # | File | Line | Comment |
|---|------|------|---------|
| 1 | path/to/file.py | 42 | "Add error handling..." |
| 2 | path/to/other.md | 17 | "Update reference..." |
```

### Step 5: Checkout the PR Branch

```bash
git fetch origin <HEAD_REF_NAME>
git checkout <HEAD_REF_NAME>
```

### Step 6: Address All Comments

For each comment:

1. **Read** the file and surrounding context
2. **Implement** the fix suggested by the reviewer
3. **Verify** the fix (grep for stale references, check consistency)

Work through all comments systematically. Group related fixes (e.g., multiple comments about the same file) to avoid redundant reads.

**Track which comments were addressed** — maintain a list of comment IDs that received code fixes. Only these will be replied to and resolved in Step 9.

### Step 7: Verify

Run verification checks based on the nature of the fixes:

```bash
# Example: check for stale references
grep -r "<old-term>" <relevant-dirs>/

# Example: confirm file structure matches docs
ls <dir>/
```

### Step 8: Commit

Commit using [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification).

**Check if commitizen is available:**

```bash
command -v cz >/dev/null 2>&1 && echo "cz available" || echo "cz not found"
```

**If `cz` is installed**, use it interactively:

```bash
git add <files>
cz c
```

Follow the commitizen prompts, selecting the appropriate type (usually `fix`) and scope.

**If `cz` is NOT installed**, commit manually following the spec:

```bash
git add <files>
git commit -m "fix(<scope>): address PR #<NUMBER> review comments

<brief description of what was fixed>"
```

**Conventional Commits format:**

```
<type>(<scope>): <short description>

[optional body — what and why]

[optional footer(s)]
```

| Type | When to use |
|------|-------------|
| `fix` | Addressing review comments, bug fixes |
| `refactor` | Code restructuring without behavior change |
| `docs` | Documentation-only changes |
| `style` | Formatting, whitespace |
| `chore` | Tooling, config, non-production changes |

### Step 9: Reply and Resolve Addressed Threads

For each comment that was **addressed in Step 6**, reply and resolve its thread.

**Reply to each comment (REST API):**

```bash
gh api repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments \
  -f body="<reply-message>" \
  -F in_reply_to=<COMMENT_DATABASE_ID>
```

Reply format:
- Be concise: "Fixed — <what was done>."
- Reference the specific change if helpful: "Changed `grep hello-world` to `grep hello-agent-auth`."
- Do NOT repeat the reviewer's comment back to them.

**IMPORTANT:** The reply endpoint is:
```
POST /repos/{owner}/{repo}/pulls/{pull_number}/comments
```
with `in_reply_to` as a field in the body. Do NOT use `/replies` sub-resource (returns 404).

**Resolve each thread (GraphQL):**

```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: {threadId: "<THREAD_ID>"}) {
    thread { isResolved }
  }
}'
```

Only resolve threads whose comments were addressed in code. Skip threads that:
- Require discussion rather than a code fix
- Were not implemented (skipped or deferred)

### Step 10: Summary

```markdown
## Done

### Addressed & Resolved
| # | File | Comment | Reply |
|---|------|---------|-------|
| 1 | path/to/file.md | "Update reference..." | Fixed — updated to use new name. |
| 2 | path/to/other.py | "Remove auth..." | Fixed — removed auth prerequisites. |

### Skipped (not addressed)
| # | File | Comment | Reason |
|---|------|---------|--------|
| 3 | path/to/config.py | "Consider refactoring..." | Requires discussion |

**Resolved**: X / Y threads
**Skipped**: Z (not addressed in code)
```

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| 404 on reply | Used wrong endpoint (`/replies`) | Use `POST /pulls/{number}/comments` with `in_reply_to` field |
| 422 on resolve | Thread already resolved | Safe to ignore — thread is already in desired state |
| 403 on GraphQL | Token lacks `write:discussion` scope | Re-authenticate: `gh auth refresh -s write:discussion` |

---

## Related Commands

- `/fix-pr-comments` — Interactive mode (asks before each fix)
- `pr-review` skill — Review someone else's PR
- `/create-pr` — Create a new PR
- `pr-address-comments-all` — Parallel batch with worktrees and approval gate
