# Testing agents

Smoke-test a deployed LangGraph agent with `langsmith-client test-deployed`. It resolves the agent's base URL, sends a message, and prints the response.

```bash
# Resolve the deployment via the control plane by service + env
uv run langsmith-client test-deployed --service hello-agent --env prod -m "What is 2+2?"
```

## `test-deployed`

| Option | Description |
| --- | --- |
| `--service` | **Required.** Service name for control-plane lookup. |
| `-d, --deployment` | Explicit deployment name (default: `<service>-<env>`). |
| `-e, --env` | Environment for the canonical name (default: `$APP_ENV` or `dev`). |
| `--region {us,eu}` | Control plane region (default: `us`). |
| `--url` | Friendly ingress host for resolution (e.g. `https://agents.example.com`), or the base URL when using `--prefix`/`--kubectl`. |
| `--prefix` | Mount prefix (e.g. `/lgp/<hash>`) joined onto `--url`; skips control-plane resolution. |
| `--kubectl` | Auto-detect the mount prefix from a running pod via `kubectl`, joined onto `--url`. |
| `--assistant-id` | Assistant/graph ID to invoke (default: `agent`). |
| `-m, --message` | Message to send (default: `Hello! What can you do?`). |
| `--stream` | Stream the response instead of waiting for completion. |

## Resolution modes

The base URL is resolved in one of three ways, in priority order:

1. **`--prefix`** — join the mount prefix onto `--url` directly (no control-plane call).
2. **`--kubectl`** — auto-detect the prefix from a live pod, joined onto `--url`.
3. **Control plane (default)** — resolve `<service>-<env>` (or `--deployment`) through the control plane; use `--url` to override the ingress host.

```bash
# Friendly dev ingress host
uv run langsmith-client test-deployed --service hello-agent \
    --url https://agents.example.com -d hello-agent-prod-dev

# Manual prefix (port-forward)
uv run langsmith-client test-deployed --service hello-agent --prefix /lgp/abc

# kubectl auto-detect, streaming
uv run langsmith-client test-deployed --service hello-agent --kubectl --stream
```
