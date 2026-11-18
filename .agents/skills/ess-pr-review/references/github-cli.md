# GitHub CLI (gh) — fetch and post

`gh` is the primary integration for this skill. GitHub MCP is an optional
alternative (see the bottom note).

## Resolve the repo and PR

```bash
gh repo view --json nameWithOwner --jq .nameWithOwner          # {owner}/{repo}
gh pr view <N> --json number,title,author,state,isDraft,headRefName,baseRefName,files,additions,deletions
```

## Fetch existing reviews and inline comments (dedup)

```bash
gh api repos/<owner>/<repo>/pulls/<N>/reviews                  # prior reviews
gh api repos/<owner>/<repo>/pulls/<N>/comments                 # inline comments
```

Skip any issue another reviewer already raised. Note it as
`⏭️ Skipped (already flagged by @reviewer)` in the summary.

## Checkout the branch

```bash
BRANCH="$(gh pr view <N> --json headRefName --jq .headRefName)"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"    # only if the local branch is behind
```

## Post the review

Ask the user first: inline comments / summary only / request changes / approve /
don't post.

### Review with inline comments (preferred)

Build a JSON payload and submit one review with all comments at once. `event` is
one of `COMMENT`, `REQUEST_CHANGES`, `APPROVE`.

```bash
cat > /tmp/pr-review-body.json <<'JSON'
{
  "event": "COMMENT",
  "body": "<review summary markdown>",
  "comments": [
    { "path": "path/to/file.py", "line": 42, "side": "RIGHT",
      "body": "Missing error handling for the customer-not-found case." },
    { "path": "path/to/tools.py", "line": 88, "side": "RIGHT",
      "body": "Extract this to a named constant." }
  ]
}
JSON
gh api repos/<owner>/<repo>/pulls/<N>/reviews \
  --method POST --input /tmp/pr-review-body.json
```

### Summary-only comment

```bash
gh pr comment <N> --body-file /tmp/review-summary.md
```

## Confirm

```
## Review Posted ✅

**PR**: #<N> | **Action**: REQUEST_CHANGES / COMMENT / APPROVE
**Comments**: X added, Y skipped (already flagged)
```

## Optional: GitHub MCP

If GitHub MCP is configured, the equivalents are `get_pull_request`,
`get_pull_request_files`, `get_pull_request_reviews`, `get_pull_request_comments`
(fetch) and `create_pull_request_review` / `create_issue_comment` (post). Prefer
`gh` unless the user explicitly asks for MCP — it needs no extra setup and works
in every checkout.
