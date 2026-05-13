# ess-service-now-incident

Fetch incident records from a [ServiceNow](https://www.servicenow.com/)
instance via an authenticated browser session.

The library wraps the ServiceNow Table API and runs the call from
inside a persistent Chrome profile (managed by `ess-browser`) so that
SSO cookies survive between runs. No API tokens or basic-auth
credentials are required -- the user authenticates once in the browser,
and subsequent runs reuse the same session.

## What you get

- `get_incident()` -- programmatic access to a single incident record.
- `parse_incident_input()` -- parse an incident number or URL into a
  structured query.
- `build_cli()` -- factory that returns a `click.Command`, suitable
  for building organization-specific CLI wrappers with a baked-in
  default instance.
- An `ess-service-now-incident` console script with no organization
  defaults: callers must specify the instance via flag, environment
  variable, or a full ServiceNow URL.

## Installation

In a `uv` workspace, declare the dependency in your `pyproject.toml`:

```toml
[project]
dependencies = ["ess-service-now-incident"]

[tool.uv.sources]
ess-service-now-incident = { workspace = true }
```

Then run `uv sync --all-packages` from the workspace root.

## Library usage

```python
from ess_service_now_incident import get_incident

record = get_incident(
    "INC0000001",
    instance="example.service-now.com",
)
print(record["description"])
```

Passing a full ServiceNow URL lets the library extract the instance
hostname automatically:

```python
record = get_incident(
    "https://example.service-now.com/now/sow/record/incident/<sys_id>",
)
```

The returned dict contains `number`, `sys_id`, `short_description`,
and `description`.

## CLI usage

The package ships an `ess-service-now-incident` console script with
no built-in default for `--instance`. The instance hostname is
resolved in this order:

1. The host embedded in the `IDENTIFIER` argument when it is a URL.
2. The `--instance` flag.
3. The `SERVICENOW_INSTANCE` environment variable.

```bash
# By incident number with explicit instance
uv run ess-service-now-incident --instance example.service-now.com INC0000001

# By URL (instance derived from the URL host)
uv run ess-service-now-incident \
    "https://example.service-now.com/now/sow/record/incident/<sys_id>"

# Headed mode (show the browser window for first-time SSO login)
uv run ess-service-now-incident --headed \
    --instance example.service-now.com INC0000001

# Emit the full record as JSON
uv run ess-service-now-incident --json \
    --instance example.service-now.com INC0000001
```

### Options

| Option          | Description                                                  |
| --------------- | ------------------------------------------------------------ |
| `--headed`      | Show the browser window. Use for first-time SSO login.       |
| `--profile-dir` | Browser profile directory for session persistence.           |
| `--instance`    | ServiceNow instance hostname (overridden by URL host).        |
| `--json`        | Emit the full record as JSON instead of the description.      |
| `-v/--verbose`  | Verbose logging to stderr.                                    |

## Building a wrapper with a default instance

Wrappers can use `build_cli()` to construct a CLI with an
organization-specific default. The user can still override with
`--instance` or `SERVICENOW_INSTANCE`.

```python
# tools/python/my-team-tool/src/my_team_tool/__main__.py
from ess_service_now_incident import build_cli

main = build_cli(default_instance="my-org.service-now.com")

if __name__ == "__main__":
    main()
```

Wire that up in your wrapper's `pyproject.toml`:

```toml
[project]
dependencies = ["ess-service-now-incident"]

[tool.uv.sources]
ess-service-now-incident = { workspace = true }

[project.scripts]
my-team-tool = "my_team_tool.__main__:main"
```

## Errors

All library errors derive from `ServiceNowIncidentError`:

| Exception                | Raised when                                           |
| ------------------------ | ----------------------------------------------------- |
| `InputParseError`        | The input is not a recognisable URL or `INC...` number, or no instance is supplied. |
| `AuthenticationError`    | SSO login times out or the Table API returns 401/403. |
| `IncidentNotFoundError`  | The Table API returns an empty result set.            |
| `APIError`               | The Table API returns a non-success HTTP status, or the response is not JSON. |

## Hostname safety

The library validates instance hostnames against the
`*.service-now.com` suffix using an exact suffix match. Hostnames like
`evilservice-now.com` or `service-now.com.evil.com` are rejected,
mitigating subdomain-confusion attacks against URL inputs.

## Testing

```bash
uv run pytest packages/python/ess-service-now-incident/tests
```

The tests stub out the browser session and never touch a real
ServiceNow instance.
