# LangChain / LangGraph conventions (framework-specific)

Apply this only when the PR touches LangChain/LangGraph agent code. These are
conventions the linters do not enforce, so they belong to the LLM judgment pass.

## `@tool` checklist

For each changed `*/tools.py` (or tool definition):

- [ ] `@tool` decorator used correctly.
- [ ] `@handle_tool_error` decorator present.
- [ ] `RunnableConfig` parameter included.
- [ ] `should_fetch` parameter for cached data (where applicable).
- [ ] ROUTING hints in the docstring (so the LLM can select the tool).
- [ ] Docstring under 1024 chars (validation-enforced).
- [ ] Citation constant defined.
- [ ] Error messages are user-friendly.

## AGENTS.md rules worth quoting

When the diff violates one of these, quote the exact rule in the finding:

| Rule | Check |
| --- | --- |
| Max 5 parameters | "Max 5 parameters per function — group related params into dataclasses/config objects" |
| Tool docstring format | "Docstrings must include ROUTING hints for LLM tool selection" |
| Tool docstring length | "Max 1024 chars for @tool docstrings (validation enforced)" |
| Type hints | "Python 3.11+ with type hints on all functions" |
| DRY | "DRY principle — consolidate duplicated logic into reusable functions" |
| Early returns | "Early returns — use guard clauses to reduce nesting depth" |
| No nested ternaries | "No nested ternaries — use if/else or match/case" |
| Descriptive names | "Descriptive names — use customer_data not d" |
| Dependency workflow | "Follow the uv workflow; don't hand-edit uv.lock" |

Note: several of these (max parameters, nesting, complexity, naming) are also
enforced mechanically by ruff and will appear in `report.md` — quote the AGENTS.md
rule only when adding context the linter finding lacks, and don't double-post.

## Scope a rule before flagging

- Root `AGENTS.md` applies to all files.
- A directory-specific `AGENTS.md` applies only to files in that directory (or
  its children). Don't apply an unrelated directory's rules to a file outside it.
