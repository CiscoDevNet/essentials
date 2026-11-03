# Review output format

## Review summary (post as the review body)

```
## AI Code Review: PR #<N>

**Title**: <title>
**Author**: @<author>
**Files Changed**: X files (+Y/-Z lines)

---

### Summary

| Severity | Count | Note |
| --- | --- | --- |
| 🔴 High | X | |
| 🟡 Medium | Y | |
| 🟢 Low | Z | |
| ⏭️ Skipped | N | Already flagged by other reviewers |

**Recommendation**: APPROVE / REQUEST_CHANGES / COMMENT

---

### Issues Found

#### 🔴 HIGH: <short title>

**File**: `path/to/file.py` (line 42-45)

**Problem**: <what is wrong and why it matters>

**Suggested Fix**: <corrected approach or code>

---

### Already Flagged (Skipping)

- ⏭️ `path/to/file.py:290-377` — <issue> (flagged by @reviewer)

### What Looks Good ✅

- <genuinely good things worth calling out>
```

## Inline comment format

**Small fixes (< 6 lines): include a `suggestion` block** so the author can
one-click apply it.

````markdown
Missing error handling for the customer-not-found case.

**AGENTS.md rule**: "Early returns — use guard clauses to reduce nesting depth"

```suggestion
if not customer:
    return {"error": "Customer not found", "data": None}
```
````

**Larger / structural fixes (6+ lines): description only.** Describe the issue
and the approach; do not attach a `suggestion` block — structural changes are
better discussed than auto-applied.

## Code link format

When linking to code, use the full commit SHA (not `HEAD` or a branch):

```
https://github.com/{owner}/{repo}/blob/{full_sha}/path/to/file.py#L10-L15
```

- Derive `{owner}/{repo}` from `gh repo view --json nameWithOwner --jq .nameWithOwner`
  or the PR metadata.
- Get the SHA with `git rev-parse HEAD`.
- Include `#L<start>-L<end>` and give at least one line of context on each side.

## Rules

- **One comment per unique issue.** Never post duplicates.
- Post **only high-signal** findings (see `SKILL.md` step 6). If you are not
  confident an issue is real, drop it.
- Quote the exact AGENTS.md rule when flagging a compliance violation.
