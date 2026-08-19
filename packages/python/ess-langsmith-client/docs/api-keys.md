# API keys

Manage LangSmith API keys with `langsmith-client keys`. Listing, creating, and deleting keys all require an admin `LANGSMITH_API_KEY`.

```bash
# List keys in a workspace
uv run langsmith-client keys list --workspace-id <workspace-id>

# Create a service key (the full value is shown only once)
uv run langsmith-client keys create "LangSmith Deployment: hello-world-graph"

# Delete a key by its description (name)
uv run langsmith-client keys delete "my-old-key"
```

> **Workspace scoping:** keys are per-workspace. Pass `--workspace-id` (or set `LANGSMITH_WORKSPACE_ID`); otherwise you may see zero results. Run `langsmith-client workspaces list` to find the ID.

## `keys list`

List API keys for the current workspace.

| Option | Description |
| --- | --- |
| `--api-key` | LangSmith API key (defaults to `LANGSMITH_API_KEY`). |
| `--workspace-id` | Target workspace (defaults to `LANGSMITH_WORKSPACE_ID`). |
| `--expired` | Show only expired keys. |
| `--older-than N` | Show only keys older than `N` days (by `created_at`). |
| `--format {table,json}` | Output format (default: `table`). |

The table shows description, short key, age in days, expiry (with an `EXPIRED` marker), and the key ID.

## `keys create`

Create a new service API key.

```bash
uv run langsmith-client keys create "my-service-key" --format json
```

- Argument: `DESCRIPTION` — the human-readable name shown in the LangSmith UI.
- The **full key value is displayed once, at creation time only.** Copy it immediately.

## `keys delete`

Delete one or more keys by exact description.

```bash
# Delete several keys
uv run langsmith-client keys delete "key-1" "key-2" "key-3"

# Skip the confirmation prompt
uv run langsmith-client keys delete "key-1" --yes

# Delete every key sharing a duplicated name
uv run langsmith-client keys delete "duplicated-name" --all
```

| Option | Description |
| --- | --- |
| `--all` | Delete every key matching a description, even when one description matches multiple keys. |
| `--yes` | Skip the confirmation prompt. |

### Duplicate safeguard

By default, if any description matches **more than one** key, `delete` refuses to act and lists the conflicting keys (short key, ID, expiry) so you can inspect them. This prevents accidentally wiping multiple keys that happen to share a name. Re-run with `--all` to delete every matching key deliberately.
