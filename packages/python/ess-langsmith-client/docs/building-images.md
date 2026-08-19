# Building images

Build a Docker image for a LangGraph agent with `langsmith-client build`. It wraps `langgraph build`, deriving a consistent image tag from `pyproject.toml` and the current git SHA.

```bash
# Build with defaults from pyproject.toml (tag: name:version-<git-sha>)
uv run langsmith-client build

# Build and push to a registry
uv run langsmith-client build --push --registry gcr.io/my-project
```

## Tagging

When `--tag` is not given, the tag is `name:version-<git-sha>` (falling back to `name:version` when the SHA is unavailable), read from `[project]` in `pyproject.toml`. A changing tag per commit is what makes each deploy roll out a fresh image.

## Options

| Option | Description |
| --- | --- |
| `-t, --tag` | Override the image tag (default: `name:version` from pyproject). |
| `--push` | Push to the registry after build. |
| `--registry` | Registry prefix for push (e.g. `gcr.io/my-project`). |
| `--platform` | Docker platform (default: `linux/amd64`; use `linux/arm64` for local Apple Silicon testing). |
| `-C, --project-dir` | Project dir containing `pyproject.toml` and `langgraph.json` (default: `.`). |
| `LANGGRAPH_ARGS` | Any trailing arguments are passed straight through to `langgraph build`. |

## Examples

```bash
# Build a specific project directory
uv run langsmith-client build -C path/to/my-agent

# Custom tag
uv run langsmith-client build -t my-image:v2

# Build for local ARM testing
uv run langsmith-client build --platform linux/arm64
```

Once pushed, deploy the image with [`deploy docker`](deploying-agents.md).
