# Deploying agents

Deploy LangGraph agents to LangSmith with `langsmith-client deploy`. Two sources are supported:

- `deploy docker` — deploy a prebuilt Docker image (self-hosted / hybrid clusters).
- `deploy github` — deploy from a GitHub repo (LangSmith Cloud).

Both require `LANGSMITH_API_KEY` and `LANGSMITH_WORKSPACE_ID`.

```bash
# Docker: build & push first, then deploy
uv run langsmith-client build --push --registry <registry>
uv run langsmith-client deploy docker create --listener-id <id> --wait

# GitHub: deploy from a repo (one-time integration setup required)
uv run langsmith-client deploy github create --repo-url <url> --integration-id <id>
```

## Canonical naming and idempotent upsert

Deployments use a stable canonical name of the form `<service>-<env>`:

- `service` defaults to `[project].name` in `pyproject.toml` (override with `--name`).
- `env` comes from `--env`, then `$APP_ENV`, then `dev`.
- For Docker you can also pass `--deployment` to use a full base name as-is (e.g. `my-agent-prod-dev`) without the service/env split.

Re-running `create` is an **idempotent upsert**:

- updates the live deployment in place if one exists,
- creates the canonical name if none exists,
- creates a **git-SHA rescue name** (`<service>-<env>-<sha>`) only when the canonical name is stuck/orphaned.

## `deploy docker`

### `create`

Deploy (or upsert) a Docker image.

| Option | Description |
| --- | --- |
| `--name` | Service name for `<service>-<env>` (default: project name). |
| `--deployment` | Full base name used as-is (skips service/env split). |
| `--env` | Environment component (default: `$APP_ENV` or `dev`). |
| `-C, --project-dir` | Project dir containing `pyproject.toml` (default: `.`). |
| `--image-uri` | Docker image URI (default: `name:version` from pyproject). |
| `--listener-id` | Listener for hybrid deployments (or `LANGSMITH_LISTENER_ID`). See [listeners](listeners.md). |
| `--namespace` | Kubernetes namespace (default: `default`). |
| `--secret NAME=VALUE` | Secret (repeatable); `NAME=$ENV_VAR` reads from the environment. |
| `--min-scale` / `--max-scale` | Instance bounds (default: 1 / 3). |
| `--cpu` / `--memory` | CPU cores / memory MB per instance (default: 1 / 1024). |
| `--wait` | Wait for the deployment to complete. |

### `update`

Update a specific deployment by ID with a new image (and secrets).

| Option | Description |
| --- | --- |
| `--deployment-id` | **Required.** Deployment to update. |
| `-C, --project-dir` | Project dir for deriving the image URI. |
| `--image-uri` | New image URI (default: `name:version` from pyproject). |
| `--secret NAME=VALUE` | Secret (repeatable). |
| `--wait` | Wait for completion. |

### `list`

List deployments; `--filter` matches names (contains), `--docker-only` shows only Docker deployments.

### `delete`

Delete by `--deployment-id`, or by the resolved `<service>-<env>` base name (via `--name`/`--deployment`/`-C` + `--env`). `--if-exists` exits 0 when nothing matches; `--yes`/`-y` skips confirmation.

## `deploy github`

### `create`

Deploy (or upsert) from a GitHub repository. Requires a one-time GitHub integration (LangSmith UI → Deployments → Import from GitHub), then a `GITHUB_INTEGRATION_ID`.

| Option | Description |
| --- | --- |
| `--name` | Service name for `<service>-<env>` (default: project name). |
| `--env` | Environment component (default: `$APP_ENV` or `dev`). |
| `-C, --project-dir` | Project dir containing `pyproject.toml`. |
| `--repo-url` | **Required.** GitHub repository URL. |
| `--branch` | Branch to deploy (default: `main`). |
| `--config-path` | Path to `langgraph.json` (default: `langgraph.json`). |
| `--integration-id` | GitHub integration ID (or `GITHUB_INTEGRATION_ID`). |
| `--type {dev,prod}` | Deployment type (default: `dev`). |
| `--auto-build/--no-auto-build` | Rebuild on push (default: on). |
| `--shareable` | Make shareable via Studio. |
| `--secret NAME=VALUE` | Secret (repeatable). |
| `--min-scale` / `--max-scale` / `--cpu` / `--memory` | Resource spec. |
| `--wait` | Wait for completion. |

### `update`

Update a deployment by `--deployment-id` (creates a new revision). Optional `--branch`, `--config-path`, `--auto-build/--no-auto-build`, `--wait`.

### `list`

List deployments; `--filter` matches names, `--github-only` shows only GitHub deployments.

### `delete`

Delete by `--deployment-id` (prompts for confirmation).
