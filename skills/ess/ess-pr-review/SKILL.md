---
name: ess-pr-review
description: >-
  AI-assisted review of one or more GitHub Pull Requests. Offloads deterministic
  checks (lint, complexity, duplication, security, perf) to repo linters via
  self-contained scripts, then applies LLM judgment to what linters cannot catch
  and posts high-signal findings after a single human approval. Pass one or many
  PRs (numbers or URLs); with none, it discovers PRs where your review is
  requested, optionally narrowed to given authors or a GitHub org team. Use for
  /ess-pr-review, "review PR <number/URL>", "review my requested PRs", "code review
  these pull requests", "review PRs from <person>", "review my teammate's PRs",
  "review the PRs from <team>". Requires gh and a git checkout.
metadata:
  version: "2.0"
---

# Review PR

Review **one or more** GitHub Pull Requests. **Linters find, the LLM judges**: a
scan script runs the repo's own linters over each PR diff and emits a compact
report, so you spend attention on correctness, cross-file logic, and
disable-comment justification — not on re-deriving lint findings token by token.

This skill is **variadic**: it always operates on a set of PRs of size N ≥ 1. A
single PR is just N = 1 and uses a fast in-place path; multiple PRs each get an
isolated read-only worktree. Nothing is posted to any PR until you approve at one
gate.

**Phase**: Review

## Quick start

```
/ess-pr-review https://github.com/<owner>/<repo>/pull/456   # one PR
/ess-pr-review 456                                          # one PR, bare number
/ess-pr-review 456 461 470                                  # several PRs
/ess-pr-review                                              # discover: PRs awaiting my review
/ess-pr-review from alice                                   # ...only hers
/ess-pr-review from @acme/platform-team                     # ...only that team's
```

---

## Prerequisites

- **GitHub CLI** (`gh`) — authenticated, with access to the repo. Primary
  integration. Filtering discovery by a GitHub org team additionally needs the
  `read:org` scope (`gh auth status` lists your scopes).
- The current directory must be a git repo (`.git/` present).
- Linters are optional: the scan runs whatever is installed (`ruff`, `pylint`,
  `bandit`, `eslint`) and records the rest as "not run". Python linters run via
  `uv run` when the repo is a uv project, and as bare executables otherwise.
- TypeScript/eslint needs the workspace deps hoisted to the repo-root
  `node_modules` — run `npm install` once at the repo root. Until then the scan
  records eslint as "not run" with that hint and continues.
- For N > 1, `openssl` and (ideally) `jq` are used to create and provision
  isolated worktrees. GitHub MCP is an optional alternative for posting (see
  [references/github-cli.md](references/github-cli.md)); `gh` is the default.

## Scripts

Every step runs the bundled scripts from `SKILL_DIR`: the absolute path of the directory
that contains this `SKILL.md`. Resolve it once, before Step 1, and reuse it. Do not use a
repo-relative path; the skill may be installed outside the repo you are reviewing.

---

## Workflow

### 1. Resolve the set of PRs

Build the list of PR numbers to review, then let N = its length.

- **Refs given** (one or many): each arg is a full URL
  (`https://github.com/<owner>/<repo>/pull/<N>`) or a bare number. Extract
  `owner/repo` from URLs; for bare numbers use
  `gh repo view --json nameWithOwner --jq .nameWithOwner`.
- **No refs**: discover PRs awaiting your review:

  ```bash
  "$SKILL_DIR/scripts/find-review-requests.sh"                  # user-requested PRs (default)
  "$SKILL_DIR/scripts/find-review-requests.sh" --include-team   # also team-requested
  ```

  It prints matching numbers to stdout and a human table to stderr. Show the
  table and **confirm the set with the user** before reviewing. If empty, say so
  and stop.

- **Narrowing to certain people**: when the user names whose PRs they want, pass
  `--author` — repeatable, and a PR is kept if it matches **any** term:

  ```bash
  "$SKILL_DIR/scripts/find-review-requests.sh" --author alice --author 'Bob Brown'
  "$SKILL_DIR/scripts/find-review-requests.sh" --author @acme/platform-team
  ```

  | Term | Matches |
  | --- | --- |
  | `@me` | you |
  | `@org/team-slug` | every member of that GitHub org team |
  | `@team-slug` | same, resolved in this repo's own org |
  | `alice` | a GitHub login, whole-field |
  | `bob@corp.example.com` | a PR or commit author email, whole-field |
  | `Bob Brown` | a display name, substring — so `Bob` also matches |

  `@me` and team terms are answered entirely by the one query discovery already
  makes, so they cost nothing extra. Every other term is also matched against
  each PR's **commit** authors, which that query cannot carry — so a login,
  email, or display-name term costs one extra lookup per PR it has not already
  matched. That is deliberate: a commit author's name or email often differs from
  the PR author's GitHub profile, and skipping the lookup silently drops those
  PRs. To keep the cost down, prefer `@me` or a team term, or a term that matches
  the PR author directly.

  `--author` only ever **narrows** the review-requested set; it cannot surface a
  PR that was never assigned to you. It applies to discovery only — when the user
  passes explicit PR numbers or URLs, review exactly those and ignore authorship.
  Listing org team members needs the `read:org` scope on the gh token.

If N = 1, continue with the fast path below. If N > 1, follow
[references/batch-mechanics.md](references/batch-mechanics.md) to scan each PR in
its own worktree (via a read-only subagent per PR), then converge on the same
single GATE in Step 7.

### 2. Pre-check — skip unnecessary reviews (per PR)

Fetch metadata, then **drop the PR from the set and record a skip** if any hold:

```bash
gh pr view <N> --json state,isDraft,title,files
```

| Condition | Check | Action |
| --- | --- | --- |
| Closed/merged | `state != "OPEN"` | Skip |
| Draft | `isDraft == true` | Skip |
| AI already reviewed | prior AI review in `gh api .../pulls/<N>/reviews` | Skip (no dupes) |
| Trivial only | changes limited to `CHANGELOG.md`, `uv.lock`, lockfiles | Skip |
| Dependency bump | title matches "bump", "update deps" | Skip |

```
> **Skipping review** for PR #<N>
> **Reason**: <draft / already reviewed / trivial change>
```

Still review AI-authored PRs — do **not** skip just because the author is an AI.

### 3. Get the PR code (N = 1 fast path)

**Optional.** `scan-pr.sh <N>` (Step 4) fetches and pins the PR's head commit
itself, so it scans the real PR diff regardless of what is checked out — you no
longer need to check out the branch just to scan. Check out only if you want the
PR code in your working tree for local inspection:

```bash
BRANCH="$(gh pr view <N> --json headRefName --jq .headRefName)"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"   # if the local branch is behind
```

For N > 1, each PR is already isolated in its own detached read-only worktree
(no branch checkout in the main tree) — see the batch reference.

### 4. Run the deterministic scan (per PR)

```bash
"$SKILL_DIR/scripts/scan-pr.sh" <N>                              # a PR ref (URL or number)
"$SKILL_DIR/scripts/scan-pr.sh" --base origin/main --head HEAD   # or an explicit range
"$SKILL_DIR/scripts/scan-pr.sh" --base origin/main --head <SHA> --number <N> --repo <o>/<r>
```

Given a PR ref, `scan-pr.sh` fetches and pins the PR's head SHA (printed in its
output) and **aborts** if that commit can't be resolved — so it is safe to run
from any checkout and never silently scans the local tree.

The output dir is unique per PR: a PR ref uses `...-<N>`, and an explicit
`--base/--head` range with no `--number` falls back to a short head hash (so
concurrent range scans never share a dir). Batch reviews (N > 1) pass
`--number <N>` so each PR writes to its own `/tmp/pr-review-<owner>-<repo>-<N>`
and the report is stamped `owner/repo#N` — see the batch reference.

The orchestrator resolves base/head, computes changed files, runs every
available linter scoped to the diff, scans for suppression comments, and writes
`report.json` + `report.md` under `/tmp/pr-review-<owner>-<repo>-<N>/`. **Read
`report.md`** — it replaces manual lint eyeballing and the simplification /
common-issue tables from the old command.

What the scan covers (do not re-derive these by hand — see
[references/deterministic-checks.md](references/deterministic-checks.md)):

- **Python**: `ruff` (`E,F,B,PERF,C,I,N,PL` — complexity `C901`, too-many-*
  `PLR09xx`, magic values `PLR2004`, perf `PERF`, naming `N`, unused `F401`),
  `bandit` (security), `pylint` duplicate-code `R0801` + perflint.
- **TypeScript**: `eslint` + `eslint-plugin-sonarjs` (duplication, cognitive complexity).
- **Suppressions**: every `pylint: disable` / `noqa` / `type: ignore` added by the diff.

### 5. LLM judgment pass — the actual review (per PR)

The report handles the mechanical checks. Spend your effort **only** on what
linters cannot decide:

- **Correctness vs PR intent** — does the code do what the PR claims?
- **Cross-file / logic conflicts** — new code contradicting other changed files;
  prompt instructions not matching code behavior.
- **Resource cleanup semantics** — files/connections/temp files freed on every path.
- **Suppression justifications** — for each disable in the report, judge whether
  it is acceptable. `too-many-*` / `line-too-long` are never OK; `import-error` /
  `no-member` on dynamic attributes often are. Full matrix:
  [references/pylint-disables.md](references/pylint-disables.md).
- **AGENTS.md rules** not covered by ruff — locate root and directory-scoped
  `AGENTS.md`, and quote the exact rule when flagging a violation.
- **Version-scoped deprecations** — check `pyproject.toml` / `.nvmrc` first; do
  not flag a deprecation the project's minimum version is unaffected by.

For LangChain/LangGraph files (tool, prompt, and agent-definition modules — e.g.
`*/tools.py`, `*/prompts/*.py`), apply the framework checklist in
[references/agent-conventions.md](references/agent-conventions.md).

### 6. High-signal filtering (required, per PR)

**Only flag issues you are confident are real.** False positives erode trust.

Flag: compile/parse failures, definite wrong results, security vulns, resource
leaks, quoted AGENTS.md violations. Do **not** flag: pre-existing issues, pure
style a linter already owns, speculative input-dependent bugs, subjective
nitpicks, or anything already silenced by a comment. If you are not certain an
issue is real, drop it. Validate each finding (is it truly undefined? is the
AGENTS.md rule scoped to this file? could it be a false positive?) before the GATE.

Also dedup against existing reviews: **skip anything another reviewer already
flagged** (`gh api repos/<owner>/<repo>/pulls/<N>/reviews` and `.../comments`).

### 7. GATE — one approval for the whole set

Aggregate the proposed findings across **all** PRs into a single view and stop.
Nothing has been posted yet. Present, per PR:

- the review summary and each proposed finding (severity, `path:line`, fix), per
  [references/output-format.md](references/output-format.md);
- any PRs skipped in Step 2 and why.

Let the user edit or drop individual findings and choose a post mode **per PR**:
inline comments / summary only / request changes / approve / don't post. Do not
post until they approve.

### 8. Post approved findings (per PR)

- Format findings per [references/output-format.md](references/output-format.md)
  (severity table, inline `suggestion` blocks for <6-line fixes,
  `{owner}/{repo}` code links).
- Post with `gh` — commands in [references/github-cli.md](references/github-cli.md).
  Post **one comment per unique issue**, in each PR's chosen mode.

### 9. Cleanup (N > 1 only)

Remove the per-PR review worktrees created in Step 1:

```bash
git worktree remove "$WORKTREE_PATH"   # add --force if it complains
git worktree prune
```

The layout matches `/worktree`, so `/delete-worktree <WORKTREE_ID>` also works.
N = 1 creates no worktree, so there is nothing to clean up.

---

## Scope & limitations

- DRY/duplication is detected across **changed files only** — the scan will not
  compare a changed file against untouched files.
- Same-origin PRs only (fork PRs are out of scope).
- `--author` filters the queue *after* it is fetched, so a queue truncated by
  `--limit` can hide matching PRs. The script warns when that happens, and exits
  non-zero when a commit-author lookup failed, since the kept set may then be
  missing a PR.
- Scripts depend only on `git`, `gh`, `openssl`/`jq` (N > 1), and the repo's
  auto-discovered linter config; they run standalone when the skill is copied
  into another repo.

## References

- [references/batch-mechanics.md](references/batch-mechanics.md) — N > 1 only: worktree-per-PR layout, per-PR read-only review subagent, GATE aggregation, cleanup.
- [references/deterministic-checks.md](references/deterministic-checks.md) — full check → linter/rule map, and the LLM boundary.
- [references/pylint-disables.md](references/pylint-disables.md) — disable evaluation matrix.
- [references/output-format.md](references/output-format.md) — review summary, inline comment, code-link format.
- [references/github-cli.md](references/github-cli.md) — gh commands to fetch and post; MCP note.
- [references/agent-conventions.md](references/agent-conventions.md) — LangChain/LangGraph checklist + file-type focus.
