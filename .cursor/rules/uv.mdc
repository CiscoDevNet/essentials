---
description: uv workspace conventions for this monorepo
alwaysApply: true
---

# uv Workspace

This project is a uv workspace with multiple members (see `pyproject.toml` `[tool.uv.workspace]`).

## Syncing

Always use `--all-packages` when syncing:

```bash
uv sync --all-packages
```

Plain `uv sync` only installs the **root** project's dependencies, which are empty. Without `--all-packages`, workspace member packages (and their entry-point scripts) will not be installed into the virtual environment.

## Locking

Use `uv lock` (not `poetry lock` or `uv lock --no-update`). No special flags are needed.
