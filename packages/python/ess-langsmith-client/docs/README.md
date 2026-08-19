# langsmith-client docs

Detailed guides for each `langsmith-client` subcommand. Start with the [package README](../README.md) for install and configuration, then dive into the area you need:

- [API keys](api-keys.md) — `keys` list/create/delete, the `--all` duplicate safeguard, workspace scoping.
- [Workspaces](workspaces.md) — `workspaces` list/get; find the workspace IDs other commands need.
- [Deploying agents](deploying-agents.md) — `deploy docker` and `deploy github`: canonical naming, idempotent upsert, git-SHA rescue, secrets, scale.
- [Building images](building-images.md) — `build`: LangGraph image build, tagging, `--push`.
- [Listeners](listeners.md) — `listeners list` for hybrid (self-hosted) deployments.
- [Projects](projects.md) — `projects` (tracing) vs `control-plane` (control-plane records).
- [Testing agents](testing-agents.md) — `test-deployed` resolution flags.
