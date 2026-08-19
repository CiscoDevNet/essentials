# ess-langsmith-client

A shared LangSmith Control Plane client and CLI. One `langsmith-client` command manages API keys, workspaces, deployments, images, listeners, and tracing projects.

```bash
uv sync --all-packages

# List your workspaces, then list the keys in one of them
uv run langsmith-client workspaces list
uv run langsmith-client keys list --workspace-id <workspace-id>
```

## Installation

In a `uv` workspace, declare the dependency in your `pyproject.toml`:

```toml
[project]
dependencies = ["ess-langsmith-client"]

[tool.uv.sources]
ess-langsmith-client = { workspace = true }
```

Then run `uv sync --all-packages` from the workspace root and use the CLI via
`uv run langsmith-client ...`.

The `test-deployed` command needs the `agent-test` extra:
`ess-langsmith-client[agent-test]`.

## Configuration

Most commands read credentials from the environment (a `.env` file in this package is auto-loaded). Copy [`.env.example`](.env.example) to `.env` and fill it in:

| Variable | Description | Required |
| --- | --- | --- |
| `LANGSMITH_API_KEY` | LangSmith API key. Key and project operations need an admin key. | Yes |
| `LANGSMITH_WORKSPACE_ID` | Workspace to scope tenant-specific calls (keys, projects). | For workspace-scoped commands |
| `APP_ENV` | Environment suffix in canonical `<service>-<env>` deployment names. Consulted only when `--env` is not passed; falls back to `dev`. | No |
| `LANGSMITH_LISTENER_ID` | Default for `deploy docker --listener-id`. See [docs/listeners.md](docs/listeners.md). | For hybrid deployments |
| `GITHUB_INTEGRATION_ID` | Default for `deploy github --integration-id`. | For GitHub deployments |

Most commands also accept `--region` (defaults to the US control plane).

> **Workspace scoping gotcha:** API keys and tracing projects are per-workspace. If you run `keys list` or `projects list` without `--workspace-id` (or `LANGSMITH_WORKSPACE_ID`), you may get zero results even when keys exist. Run `langsmith-client workspaces list` first to find the ID.

## Commands

Each subcommand has its own `--help` and a detailed guide in [`docs/`](docs/):

- `keys` — manage API keys — [docs/api-keys.md](docs/api-keys.md)
- `workspaces` — query workspaces and their IDs — [docs/workspaces.md](docs/workspaces.md)
- `deploy docker` / `deploy github` — deploy agents — [docs/deploying-agents.md](docs/deploying-agents.md)
- `build` — build LangGraph Docker images — [docs/building-images.md](docs/building-images.md)
- `listeners` — list hybrid (self-hosted) listeners — [docs/listeners.md](docs/listeners.md)
- `projects` / `control-plane` — tracing projects and control-plane records — [docs/projects.md](docs/projects.md)
- `test-deployed` — smoke-test a deployed agent — [docs/testing-agents.md](docs/testing-agents.md)

## Library

`ControlPlaneClient` and the naming, secrets, and project helpers import directly from `ess_langsmith_client`:

```python
from ess_langsmith_client import ControlPlaneClient, get_project_info
```

### Deployment secrets

`deploy docker` and `deploy github` send only the secrets you name with
`--secret NAME=VALUE`; nothing is read from your environment implicitly. To layer
on convenience defaults, pass your own key list to `merge_secrets`:

```python
from ess_langsmith_client import merge_secrets

secrets = merge_secrets(cli_secrets, auto_detect_keys=["OPENAI_API_KEY"])
```

## Running Tests

```bash
uv run pytest packages/python/ess-langsmith-client
```

## License

Apache License 2.0.
