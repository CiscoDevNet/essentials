# LangChain / LangGraph conventions (framework-specific)

Apply this only when the PR touches LangChain/LangGraph agent code. These are
conventions the linters do not enforce, so they belong to the LLM judgment pass.

## `@tool` checklist

For each changed tool definition (commonly `*/tools.py`):

- [ ] `@tool` decorator used correctly.
- [ ] The project's error-handling decorator or wrapper is applied, so a raised
      exception reaches the model as a message instead of ending the run.
- [ ] `RunnableConfig` parameter included where the tool needs run context.
- [ ] Any cache-control parameter (e.g. a refresh flag) is honored by tools that
      read cached data.
- [ ] Docstring says *when to select* the tool, not just what it does — that is
      what the model routes on.
- [ ] Docstring within the length limit the project enforces (model providers cap
      tool description length).
- [ ] Any citation or source constant the project requires is defined.
- [ ] Error messages are user-friendly.

Check each item against the repo's own conventions before flagging it: decorator
and parameter names differ between projects.

## Quoting the repo's AGENTS.md

Agent repos usually encode these conventions as AGENTS.md rules. When the diff
violates one, quote that repo's exact rule text in the finding instead of
paraphrasing it. Rule areas worth looking for:

| Rule area | What it typically constrains |
| --- | --- |
| Parameter count | A cap per function; group related params into dataclasses/config objects |
| Tool docstring format | Required sections, including routing guidance for tool selection |
| Tool docstring length | A maximum character count for tool descriptions |
| Type hints | A minimum language version, and type hints on all functions |
| DRY | Consolidating duplicated logic into reusable functions |
| Early returns | Guard clauses instead of deep nesting |
| Nested ternaries | Disallowed; use if/else or match/case |
| Descriptive names | Full words over single letters (`customer_data`, not `d`) |
| Dependency workflow | Use the project's package manager; don't hand-edit the lockfile |

Note: several of these (parameter count, nesting, complexity, naming) are also
enforced mechanically by ruff and will appear in `report.md` — quote the AGENTS.md
rule only when adding context the linter finding lacks, and don't double-post.

## Scope a rule before flagging

- Root `AGENTS.md` applies to all files.
- A directory-specific `AGENTS.md` applies only to files in that directory (or
  its children). Don't apply an unrelated directory's rules to a file outside it.
