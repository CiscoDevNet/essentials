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

- `CLIENT_ID` and `TENANT_ID` set in the environment (see `.env.example`)
  - `CLIENT_ID` -- the application (client) ID from a Microsoft Entra
    (Azure AD) app registration with delegated `Mail.ReadWrite`
    permission. The well-known "Office Desktop Apps" public client ID
    works on most Microsoft 365 tenants without any registration.
  - `TENANT_ID` -- your organization's Microsoft Entra tenant ID.
- Python 3.12+

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

## Running Tests

```bash
uv run pytest packages/python/ess-outlook/
```
