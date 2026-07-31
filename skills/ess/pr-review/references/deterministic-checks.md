# Deterministic checks: what the scan owns, what you own

The scan (`scripts/scan-pr.sh` → `report.md`) runs the repo's own linters over
the PR diff so you don't re-derive mechanical findings by hand. Read the report;
then spend your judgment on the rows in the **LLM-only** table below.

## Check → linter/rule mapping (scan handles these)

| Category | Tool / rule | Notes |
| --- | --- | --- |
| Too many arguments | ruff `PLR0913` | Group into a `@dataclass` / config object |
| Too many locals | ruff `PLR0914` | Extract helpers |
| Too many branches / statements | ruff `PLR0912` / `PLR0915` | Extract condition handlers |
| Cyclomatic complexity | ruff `C901` | Split the function |
| Deep nesting | ruff `PLR1702` | Guard clauses / early returns |
| Magic values | ruff `PLR2004` | Named constants |
| Unused imports / vars | ruff `F401` / `F841` | Remove |
| Undefined names | ruff `F821` (and `F`\*) | Real bug — HIGH |
| Naming | ruff `N` | PEP 8 |
| Performance | ruff `PERF`, pylint `perflint` W8xxx | N+1, list/dict literals, loops |
| Security | `bandit -ll` | SQL injection `B608`, subprocess, etc. (medium+) |
| Secrets | TruffleHog (pre-commit/CI) | Not re-run here; note if relevant |
| Duplication (Python) | pylint `R0801` (re-enabled) | Root config disables it; the script turns it back on |
| Duplication / cognitive complexity (TS) | eslint `eslint-plugin-sonarjs` | `no-identical-functions`, `no-duplicate-string` |
| Suppressions added | `scripts/scan_disables.sh` | `pylint: disable`, `noqa`, `type: ignore`, `@ts-ignore` |

Do **not** hand-flag anything in this table — if it's real, it's already in
`report.md`. Re-flagging it just adds noise.

## LLM-only (not mechanizable — this is the actual review)

| Category | What to check | Severity |
| --- | --- | --- |
| Correctness vs intent | Does the code do what the PR description claims? | High |
| Logic / cross-file conflicts | New code contradicting other changed files; detection logic vs documented behavior | High |
| Prompt ↔ code mismatch | Prompt instructions not matching the code that consumes them | High |
| Resource cleanup | Files/connections/temp files freed on every path (incl. error paths) | High |
| Breaking changes | Changed signature/return without updating callers | Medium |
| Suppression justification | Is each disable in the report actually justified? (see `pylint-disables.md`) | Varies |
| AGENTS.md rules | Rules not covered by ruff; quote the exact rule when flagging | Varies |
| Version-scoped deprecations | Check `pyproject.toml` / `.nvmrc` first; don't flag a deprecation the minimum version is unaffected by | Low |

## Review focus by file type

| File pattern | Extra scrutiny |
| --- | --- |
| `*/tools.py` | `@tool`, `@handle_tool_error`, ROUTING docstring, citation (see `agent-conventions.md`) |
| `*/queries.py` | SQL injection, parameterized queries, N+1 |
| `*_skill.py` | `routing_examples`, skill model pattern |
| `*/prompts/*.py` | Prompt-injection risk, instructions matching code |

## Verify project config before flagging version issues

```bash
grep -E "python_requires|python-version|requires-python|python =" pyproject.toml .python-version 2>/dev/null
cat .nvmrc package.json 2>/dev/null | grep -E "node|engines"
```

`datetime.utcnow()` is deprecated in 3.12+, but if the project supports 3.11
don't flag it. Always confirm the minimum version first.
