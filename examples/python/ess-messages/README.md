# ess-messages

Unified inbox -- aggregates recent email and Webex messages, sorted by date.

```bash
ess-messages --limit 5
```

```
[W] bob@example.com  2026-04-10 12:55  (General)
     Team sync moved to 1pm. Please use the updated meeting link.

[E] Alice Smith  2026-04-10 12:43  (Build Health Alert)
     Build health alert: latency exceeded threshold for 5 minutes.

[W] carol@example.com  2026-04-10 12:01  (Slides Space for Monday)
     Uploaded the latest deck to the room files tab.

[E] broker-alerts-noreply@example.com  2026-04-10 08:26  (Shares of Restricted Stock Ve...)
     Your restricted stock vesting transaction has been processed.
```

Output uses [Activity Streams 2.0](https://www.w3.org/TR/activitystreams-core/) (W3C) format.

## Installation

From the workspace root:

```bash
uv sync --all-packages
```

## Auth

Requires credentials for one or both sources. See:
- [Outlook setup](../../../packages/python/ess-outlook/.env.example) -- `CLIENT_ID`, `TENANT_ID`
- [Webex setup](../../../packages/python/ess-webex/.env.example) -- `WEBEX_CLIENT_ID`/`WEBEX_CLIENT_SECRET` or `WEBEX_ACCESS_TOKEN`

Copy this example's `.env.example` to `.env` and fill in values, or set the
variables in your shell environment. Never commit `.env` -- it is meant to
hold secrets.

## Usage

```bash
ess-messages                          # Latest 25 from both sources
ess-messages --limit 10               # Limit results
ess-messages --email-only             # Only email
ess-messages --webex-only             # Only Webex
ess-messages --webex-rooms R1,R2      # Specific Webex rooms
ess-messages --json-output            # Activity Streams 2.0 JSON
```

## Running Tests

```bash
uv run pytest examples/python/ess-messages/src/ess_messages/aggregator/test_aggregator.py
```
