# Listeners

List and delete LangSmith listeners with `langsmith-client listeners`. Listeners connect the LangSmith control plane to a self-hosted Kubernetes cluster; their ID is required when creating Docker-based deployments against that cluster.

```bash
uv run langsmith-client listeners list
uv run langsmith-client listeners delete <listener-id> --dry-run
```

Requires `LANGSMITH_API_KEY` and `LANGSMITH_WORKSPACE_ID`.

## `listeners list`

| Option | Description |
| --- | --- |
| `--api-key` | LangSmith API key (defaults to `LANGSMITH_API_KEY`). |
| `--workspace-id` | Target workspace (defaults to `LANGSMITH_WORKSPACE_ID`). |
| `--region {us,eu}` | Control plane region (default: `us`). |
| `--format {table,json}` | Output format (default: `table`). |

The table shows each listener's ID, compute ID (usually the Kubernetes cluster name), and version. Feed the ID into [`deploy docker create --listener-id <id>`](deploying-agents.md) for hybrid deployments.

## `listeners delete LISTENER_ID...`

Deletes one or more listeners by ID, for example after the cluster behind a listener has been torn down. It refuses to delete a listener that still has deployments placed on it, checking again after confirmation, and lists those deployments instead; delete or move them first. That check is a client-side snapshot: the control plane delete has no in-use precondition, so a deployment placed after the second check can still be removed with the listener.

| Option | Description |
| --- | --- |
| `LISTENER_ID...` | One or more listener IDs (required). |
| `--dry-run` | Show the listeners that would be deleted, then exit without deleting. Wins over `--yes`. |
| `--yes`, `-y` | Skip the confirmation prompt. Required when there is no terminal to prompt on. |
| `--api-key`, `--workspace-id`, `--region` | As for `listeners list`. |

Deleting a listener does not touch the cluster. Uninstall the dataplane Helm release there separately.
