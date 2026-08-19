# Workspaces

Query the LangSmith workspaces available to your API key with `langsmith-client workspaces`. This is usually the **first** command you run — most other commands need a workspace ID, and keys/projects are scoped per workspace.

```bash
uv run langsmith-client workspaces list
```

Only `LANGSMITH_API_KEY` is required.

## `workspaces list`

List every workspace the API key can access.

| Option | Description |
| --- | --- |
| `--api-key` | LangSmith API key (defaults to `LANGSMITH_API_KEY`). |
| `--format {table,json}` | Output format (default: `table`). |
| `--role NAME` | Filter by role name (contains match). |
| `--active-only` | Show only non-deleted workspaces. |

The table shows display name, workspace **ID**, your role, and creation date. Copy the ID for use as `--workspace-id` (or `LANGSMITH_WORKSPACE_ID`) elsewhere.

## `workspaces get`

Show full JSON details for a single workspace.

```bash
uv run langsmith-client workspaces get <workspace-id>
```

- Argument: `WORKSPACE_ID` — the workspace UUID.
- Errors if no accessible workspace matches the ID.
