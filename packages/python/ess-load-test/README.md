# ess-load-test

Generic EC2 Locust load testing engine. A shell package calls `build_cli()` with an
`AppConfig` and `deploy_cluster()` with its own paths, tags, and Locust scenarios.

```bash
cd packages/python/ess-load-test
uv run ess-load-test run --help
```

## Installation

From the workspace root:

```bash
uv sync --all-packages
```

## Usage

```bash
uv run ess-load-test status --stack dev --profile your-aws-profile
uv run ess-load-test run --url https://example.com --stack dev
```

## Shell settings

The standalone CLI ships no organization defaults. A shell sets these on its `AppConfig`:

| Field | Effect | Default |
|-------|--------|---------|
| `oauth.default_token_url` | OAuth token URL used when `LOAD_TEST_OAUTH_TOKEN_URL` is unset | `""` (the env var is required) |
| `extra_auth_domains` | IdP hosts that browser auth should treat as an SSO login, beyond `ess_browser.AUTH_DOMAINS` | `()` |
| `project_tag` | `Project` tag on every cluster resource; pass it to `deploy_cluster(project_tag=...)` | `component_name` |

Changing `project_tag` on a live stack retags every resource on the next deploy.

## Pulumi network placement (shell stack YAML)

Shell projects pass config under their namespace (e.g. `my-load-test:*`):

| Config key | Effect |
|------------|--------|
| `useDefaultVpc` | `true` → account default VPC; `false` without overrides → error |
| `vpcId` + `subnetIds` | When **both** set, place EC2 in that VPC/subnet (first subnet used for all instances) |
