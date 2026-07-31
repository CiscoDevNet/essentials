# Evaluating suppression comments

`scripts/scan_disables.sh` lists every `pylint: disable`, `noqa`, `type: ignore`,
and `@ts-ignore` the PR **adds** (with file and new-file line number). A
suppression is not automatically acceptable just because it carries a comment —
judge each one. The disable exists to hide a linter finding; decide whether
hiding it is the right call or whether the underlying issue should be fixed.

## Disable → verdict matrix

| Disable | Verdict | Acceptable when | Flag when |
| --- | --- | --- | --- |
| `import-error` | ✅ Often OK | Runtime import pylint can't resolve (monorepo, plugins, sub-venvs) | Import is genuinely broken |
| `no-member` | ✅ Often OK | Dynamic attributes (SQLAlchemy, Pydantic, etc.) | Typo / missing attribute |
| `unused-argument` | ⚠️ Sometimes | Interface requires the signature (`_`-prefix preferred) | Just lazy; the arg should be used |
| `protected-access` | ⚠️ Sometimes | Testing or framework API limitation | Production code reaching into private members |
| `broad-exception-caught` | ⚠️ Sometimes | Top-level handler / graceful degradation, with a comment explaining why | No comment; hides specific exceptions |
| `too-many-arguments` | 🔴 Never OK | — | Always — refactor to a dataclass/config object |
| `too-many-locals` | 🔴 Never OK | — | Always — extract helper functions |
| `too-many-branches` | 🔴 Never OK | — | Always — extract condition handlers |
| `line-too-long` | 🔴 Never OK | — | Always — just break the line |

## How to evaluate one

1. **Is there a comment, and does it explain _why_?** "This function is complex"
   restates the problem — it is not a justification.
2. **Code smell or false positive?** `too-many-*` is always a smell;
   `import-error` is often a false positive.
3. **Can it be refactored away?** Extract helpers, use a dataclass, catch
   specific exceptions.
4. **Is the justification just avoidance?** "Would require refactoring" → flag it
   for refactoring.

### Common invalid justifications (flag these)

- "This function is complex" → extract helpers.
- "Need many parameters" → dataclass / config object.
- "Many branches for edge cases" → extract condition handlers.
- "External library raises a generic Exception" → acceptable **only** if no
  narrower exception exists.

## Severity when flagging

- 🔴 **High**: `too-many-*`, `line-too-long`, unjustified disables, "lazy" justifications.
- 🟡 **Medium**: valid use case that could still be improved by refactoring.
- 🟢 **Low**: `import-error`, `no-member` on valid dynamic attributes,
  `protected-access` for a known API limitation. Usually no action needed.

## Repo note

The root `pyproject.toml` disables pylint's `C`/`R`/`W` categories, so
`scripts/lint_python.sh` re-enables `duplicate-code` (R0801) and the perflint
checks explicitly. The `too-many-*` rules are enforced by **ruff** (`PLR09xx`,
`C901`, `PLR1702`) and appear in the report from there.
