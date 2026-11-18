---
name: ess-summarize-change-log
description: >-
  Condense long commit logs, squash messages, or change narratives into 1–5
  GitHub-ready markdown bullets with Conventional Commit subjects (≤50 chars).
  Use for /ess-summarize-change-log, or when the user asks to summarize a git
  log, boil down commits, write a squash-merge message, or produce a
  five-bullet PR/merge summary.
license: Apache-2.0
compatibility: >-
  Requires uv. The validator fetches a pinned Commitizen on first run, which
  needs network access.
---

# Summarize Change Log

Turn a long git log, squash message draft, or PR narrative into **1–5 copy-paste markdown bullets** for a GitHub merge commit or extended description.

## Output format

Return **only** markdown bullets. No preamble, no section headings unless the user asks.

```markdown
- **type(scope): subject** — One sentence: what changed and why it matters.
```

- **1 to 5 bullets, never more than 5.**
- Preserve `Co-authored-by:` footers from the input **only if present**; place after bullets with a blank line before them.

## Subject rules

Follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/#specification):

- Format: `<type>[optional scope]: <description>` — imperative mood, lowercase type.
- Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.
- **Entire subject ≤ 50 characters** (type, scope, colon, space, description).
- Scope matches the primary area (`api-client`, `cli`, `web`).

### What changed, not process

Every subject must state **what changed**. Ban vague/process subjects:

| Bad | Good |
| --- | --- |
| `address PR #123 review comments` | `fix(cli): defer delete confirm` |
| `port docs from #120` | `docs(api-client): document --deployment` |
| `follow up on review` | `fix(web): align listener id messaging` |

## Consolidation (>5 input commits)

1. Group by scope + intent; merge overlapping fixes.
2. Keep distinct areas separate (infra vs CLI vs docs).
3. If still >5, drop least user-visible items; fold detail into a bullet body.

## Validation (required)

Before returning output, run the validator from `SKILL_DIR`: the absolute path of the
directory that contains this `SKILL.md`. Do not use a repo-relative path; the skill may be
installed outside the repo you are working in.

```bash
"$SKILL_DIR/scripts/validate-summary.sh" /tmp/draft-summary.md
```

Or validate the checked-in fixture:

```bash
"$SKILL_DIR/scripts/validate-summary.sh" "$SKILL_DIR/examples-good.md"
```

Or pipe stdin:

```bash
printf '%s\n' '- **fix: short subject** — Details.' \
  | "$SKILL_DIR/scripts/validate-summary.sh"
```

The script enforces:

- 1–5 bullets in the expected format
- `cz check -m … -l 50` from a pinned Commitizen, run with `uv tool run` in an empty
  directory, so the current repo's Commitizen config and dependencies do not apply
- Vague-subject blocklist

Fix every failure and re-run until exit 0. Only then return the markdown.

## Workflow

1. Read input; extract **outcomes**, not chronology.
2. Draft 1–5 bullets; merge if needed.
3. Rewrite process-oriented subjects to outcome-oriented ones.
4. **Validate** with `validate-summary.sh`.
5. Output validated markdown only.

## Examples

- [examples.md](examples.md) — before/after narrative and bad-vs-good subjects
- [examples-good.md](examples-good.md) — canonical validated bullets (fixture for `validate-summary.sh`)
