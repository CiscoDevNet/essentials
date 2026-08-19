# Listeners

List LangSmith listeners with `langsmith-client listeners`. Listeners connect the LangSmith control plane to a self-hosted Kubernetes cluster; their ID is required when creating Docker-based deployments against that cluster.

```bash
uv run langsmith-client listeners list
```

Requires `LANGSMITH_API_KEY` and `LANGSMITH_WORKSPACE_ID`.

## `listeners list`

| Option | Description |
| --- | --- |
| `--api-key` | LangSmith API key (defaults to `LANGSMITH_API_KEY`). |
| `--workspace-id` | Target workspace (defaults to `LANGSMITH_WORKSPACE_ID`). |
| `--region {us,eu}` | Control plane region (default: `us`). |
| `--format {table,json}` | Output format (default: `table`). |

The table shows each listener's ID, name, and status. Feed the ID into [`deploy docker create --listener-id <id>`](deploying-agents.md) for hybrid deployments.
