# Projects

There are two distinct "project" concepts in LangSmith, each with its own command:

- **Tracing projects** (sessions) — where traces land. Managed with `langsmith-client projects`.
- **Control-plane projects** — the control plane's backing records for deployments. Managed with `langsmith-client control-plane projects`.

Deleting a control-plane project does **not** delete traces unless you explicitly opt in. Use `projects` to manage traces, `control-plane` to manage deployment-backing records.

## Tracing projects — `projects`

Tracing projects are created automatically when LangGraph deployments are created. Only `LANGSMITH_API_KEY` is required.

```bash
uv run langsmith-client projects list --prefix hello-agent-dev
uv run langsmith-client projects info --name hello-agent-dev
uv run langsmith-client projects delete --name hello-agent-auth
```

### `projects list`

| Option | Description |
| --- | --- |
| `--api-key` | LangSmith API key (defaults to `LANGSMITH_API_KEY`). |
| `--name` | Filter by exact project name. |
| `--prefix` | Match `<prefix>` and `<prefix>-*` — finds a service's live project regardless of any git-SHA rescue suffix. |
| `--format {table,json}` | Output format (default: `table`). |

`--name` and `--prefix` are mutually exclusive. The table shows ID, name, run count, and the linked deployment ID.

### `projects info`

Show metadata and trace stats for one project by exact `--name` (required): run count, last run time, and deployment ID.

### `projects delete`

Delete by `--id` (single project) or `--name` (all projects with that exact name); the two are mutually exclusive. Prompts for confirmation.

`--force`:
- deletes projects that still contain traces (**data loss**), and
- clears stale deployment references (orphaned deployments) that would otherwise block deletion with a 409.

Without `--force`, projects that still hold traces are skipped and reported.

## Control-plane projects — `control-plane projects`

These records belong to the control plane's `/api-host` API and are distinct from tracing projects. Requires `LANGSMITH_API_KEY` (Admin) and `LANGSMITH_WORKSPACE_ID`.

```bash
uv run langsmith-client control-plane projects delete --id <uuid>
uv run langsmith-client control-plane projects delete --id <uuid> --id <uuid> --yes
```

### `control-plane projects delete`

| Option | Description |
| --- | --- |
| `--id` | Control-plane project ID to delete (repeatable, required). |
| `--force/--no-force` | Clear stale references that block deletion (default: on). |
| `--delete-tracing-project` | Also delete the paired tracing project and its traces (off by default, so traces are preserved). |
| `--yes` | Skip the confirmation prompt. |
