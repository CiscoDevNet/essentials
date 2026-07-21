---
name: summarize-change-log
description: >-
  Condense long commit logs, squash messages, or change narratives into 1–5
  GitHub-ready markdown bullets with Conventional Commit subjects (≤50 chars).
  Use when the user asks to summarize a git log, boil down commits, write a
  squash-merge message, or produce a five-bullet PR/merge summary.
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
- Scope matches the primary area (`langsmith-client`, `azure-ai`, `hello-agent`).

### What changed, not process

Every subject must state **what changed**. Ban vague/process subjects:

| Bad | Good |
| --- | --- |
| `address PR #513 review comments` | `fix(langsmith-client): defer delete confirm` |
| `port docs from #510` | `docs(langsmith-client): document --deployment` |
| `follow up on review` | `fix(hello-agent): align listener id messaging` |

## Consolidation (>5 input commits)

1. Group by scope + intent; merge overlapping fixes.
2. Keep distinct areas separate (infra vs CLI vs docs).
3. If still >5, drop least user-visible items; fold detail into a bullet body.

## Validation (required)

Before returning output, run from this skill's directory:

```bash
scripts/validate-summary.sh /tmp/draft-summary.md
```

Or validate the checked-in fixture:

```bash
scripts/validate-summary.sh \
  examples-good.md
```

Or pipe stdin:

```bash
printf '%s\n' '- **fix: short subject** — Details.' \
  | scripts/validate-summary.sh
```

The script enforces:

- 1–5 bullets in the expected format
- `uv run cz check -m … -l 50` (explicit 50-char limit; config alone is not applied without `-l`)
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
