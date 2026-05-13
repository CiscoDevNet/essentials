# ess-webex

Interact with Webex rooms, messages, teams, and meetings from the command line.

```bash
ess-webex rooms --max 5
```

```
Title                                   Type      Last Activity               ID
----------------------------------------------------------------------------------------------------
General                                 group     2026-04-10T10:00:00Z        Y2lzY29zcGF...
```

## Installation

In a `uv` workspace, declare the dependency in your `pyproject.toml`:

```toml
[project]
dependencies = ["ess-webex"]

[tool.uv.sources]
ess-webex = { workspace = true }
```

Then run `uv sync --all-packages` from the workspace root.

## Auth

### OAuth integration (recommended)

1. Create an integration at https://developer.webex.com/my-apps/new/integration
   - Redirect URI: `http://localhost:3030/callback`
   - Scopes: `spark:rooms_read`, `spark:messages_read`, `spark:messages_write`, `meeting:schedules_read`, `meeting:schedules_write`, `spark:people_read`
2. Add your Client ID and Secret to `.env`:
   ```
   WEBEX_CLIENT_ID=<your-client-id>
   WEBEX_CLIENT_SECRET=<your-client-secret>
   ```
3. Run `ess-webex login` -- opens a browser to authorize, then caches a refresh token (~90 day TTL, auto-renews on use).

### Personal access token (quick start)

Set `WEBEX_ACCESS_TOKEN` in `.env` for a 12-hour personal token:

```
WEBEX_ACCESS_TOKEN=<your-token>
```

Get one at https://developer.webex.com/docs/getting-your-personal-access-token

## Usage

```bash
# Login (one-time OAuth flow)
ess-webex login

# Rooms
ess-webex rooms                                       # List rooms (sorted by last activity)
ess-webex rooms --type group --max 10                 # Only group rooms
ess-webex rooms --team <team_id>                      # Rooms in a team
ess-webex rooms <room_id>                             # Room details

# Teams
ess-webex teams                                       # List teams
ess-webex teams <team_id>                             # Team details

# Messages
ess-webex messages list <room_id>                     # Recent messages in a room
ess-webex messages read <message_id>                  # Read a specific message
ess-webex messages send "Hello" --room <room_id>      # Send to a room
ess-webex messages send "Hi" --email user@example.com # Direct message

# Meetings
ess-webex meetings list                               # List meetings
ess-webex meetings list --from 2026-04-01             # Filter by date
ess-webex meetings get <meeting_id>                   # Meeting details
ess-webex meetings create "Standup" --start 2026-04-11T09:00:00 --end 2026-04-11T09:30:00
```

Add `--json-output` to any command for JSON output.

## Running Tests

```bash
uv run pytest packages/python/ess-webex/
```
