# ess-outlook

Read and manage Microsoft Outlook emails from the command line via
Microsoft Graph.

```bash
ess-outlook list --unread-only
```

```
ID         Status   Sender                         Date                   Subject
----------------------------------------------------------------------------------------------------
12345               alice@example.com              2026-04-09 10:00       Weekly standup
12346      *        bob@example.com                2026-04-09 09:30       Q1 Report
```

## Installation

In a `uv` workspace, declare the dependency in your `pyproject.toml`:

```toml
[project]
dependencies = ["ess-outlook"]

[tool.uv.sources]
ess-outlook = { workspace = true }
```

Then run `uv sync --all-packages` from the workspace root.

## Prerequisites

- Python 3.12+
- Credentials for one of the two authentication paths in
  [Configuration](#configuration)

## Configuration

Set these in the environment or in this package's `.env` file (see
`.env.example`). The CLI loads that `.env` on startup from any working
directory, so no `source .env` is needed. Real environment variables take
precedence over the file.

Boolean variables accept `1`, `true`, `yes`, `y`, `on`, `t` (and their
negatives), case-insensitively, via [python-decouple's][decouple] `strtobool`.
An unrecognized value raises `ValueError` rather than being treated as off, so
typos surface immediately.

| Variable | Required | Description |
| ---- | ---- | ----- |
| `CLIENT_ID` | Yes, unless `GRAPH_ACCESS_TOKEN` is set | Application (client) ID of a Microsoft Entra app registration with delegated `Mail.ReadWrite`. |
| `TENANT_ID` | Yes, unless `GRAPH_ACCESS_TOKEN` is set | Your organization's Microsoft Entra tenant ID. |
| `GRAPH_ACCESS_TOKEN` | No | Pre-issued access token. Bypasses MSAL, so `CLIENT_ID` and `TENANT_ID` are then unused. See [Bring your own token](#bring-your-own-token). |
| `GRAPH_INTERACTIVE_AUTH` | No | Set to `1` for browser sign-in instead of a device code. See [Browser sign-in](#browser-sign-in). |

There is no built-in default client ID. If neither `CLIENT_ID`/`TENANT_ID`
nor `GRAPH_ACCESS_TOKEN` is set, authentication raises `GraphAuthError`.

The well-known "Office Desktop Apps" public client works on many Microsoft
365 tenants for the device-code flow without a dedicated registration, but
it has no `http://localhost` redirect URI, so it cannot be used with
`GRAPH_INTERACTIVE_AUTH`.

## Usage

```bash
# List recent inbox messages
ess-outlook list

# Only unread, as JSON
ess-outlook list --unread-only --json-output

# Read a specific message
ess-outlook read 12345

# Mark one message as read
ess-outlook mark-read 12345

# Mark all inbox messages as read
ess-outlook mark-read --all

# Delete a message (prompts for confirmation)
ess-outlook delete 12345

# Delete without confirmation
ess-outlook delete 12345 --force
```

### Options

| Command     | Options                                                       |
| ----------- | ------------------------------------------------------------- |
| `list`      | `--limit N`, `--unread-only`, `--folder NAME`, `--json-output`|
| `read`      | `MESSAGE_ID`                                                  |
| `mark-read` | `MESSAGE_ID` or `--all`, `--folder NAME`                      |
| `delete`    | `MESSAGE_ID`, `--force`                                       |

## Authentication

The first run uses MSAL's device-code flow. A browser opens to
`https://microsoft.com/devicelogin`, where you enter the printed code
and sign in with your Microsoft 365 account. The refresh token is
cached under `~/.cache/ess-outlook/` with restrictive permissions
(via `ess-dirs.write_secure`); subsequent runs refresh silently.

If your tenant blocks device-code flow via Conditional Access, run
the command directly in your terminal session rather than over a
remote shell.

### Browser sign-in

Set `GRAPH_INTERACTIVE_AUTH=1` to sign in through the system browser
(authorization code + PKCE on a loopback redirect) instead of entering a
device code. Conditional Access policies often permit this where they
block device code.

This requires `CLIENT_ID` to name an app registration that lists
`http://localhost` as a redirect URI; without one, sign-in fails with
`AADSTS50011`. Well-known first-party client IDs generally do not
qualify, so this is off by default. On success, MSAL caches a refresh token;
later runs renew silently.

### Bring your own token

Set `GRAPH_ACCESS_TOKEN` to skip MSAL entirely. `CLIENT_ID` and
`TENANT_ID` are then unnecessary:

```bash
GRAPH_ACCESS_TOKEN="$(pbpaste)" ess-outlook list --limit 10
```

Get a token from [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer):
sign in, open the **Access token** tab, and copy the value. Consent to
`Mail.Read` (or `Mail.ReadWrite` for `mark-read` and `delete`) under
**Modify permissions** first, or requests return 403.

Graph Explorer tokens expire after about an hour and are not cached, so
this suits one-off reads rather than unattended jobs.

## Running Tests

```bash
uv run pytest packages/python/ess-outlook/
```

[decouple]: https://github.com/HBNetwork/python-decouple
