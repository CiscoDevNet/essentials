# AppleScript Backend (Removed)

The original Outlook CLI used AppleScript to interact with Microsoft
Outlook on macOS. This backend was removed in favor of the Microsoft
Graph API. This document preserves what we learned.

## How It Worked

Two modules made up the backend:

### Runner (`runner.py`)

A thin wrapper around `/usr/bin/osascript` that executed AppleScript
strings as subprocesses. It detected three failure modes from stderr:

- **"not running"** -- Outlook wasn't open
- **"not allowed" / "permission"** -- macOS denied automation access
- **Everything else** -- generic AppleScript error

```python
result = subprocess.run(
    ["/usr/bin/osascript", "-e", script],
    capture_output=True, text=True, timeout=30, check=False,
)
```

### Client (`client.py`)

`OutlookClient` built AppleScript strings dynamically to query
Outlook's object model. Key patterns:

- **Field delimiter** -- `|||` separated fields in AppleScript output
  since commas appear in email content.
- **Inbox resolution** -- Outlook can have multiple "Inbox" folders
  (e.g., Exchange + local "On My Computer"). The client iterated all
  mail folders named "Inbox" and picked the one with the most messages.
- **Message IDs** -- AppleScript uses numeric integer IDs
  (`message id 12345`), unlike Graph API's opaque string IDs.
- **Folder references** -- Built dynamically: `mail folder id {id}`
  for inbox, `mail folder "{name}" of default account` for others.

Example AppleScript for listing messages:

```applescript
tell application "Microsoft Outlook"
    set msgs to (every message of inbox whose is read is false)
    repeat with m in msgs
        set output to output & (id of m) & "|||" & (subject of m) & "|||" & ...
    end repeat
    return output
end tell
```

## Why We Removed It

### Security issues

1. **AppleScript injection via folder names** -- User-controlled
   folder names were interpolated directly into AppleScript strings.
   A folder name containing quotes could break the script or inject
   commands. We added escaping, but the attack surface remained.

2. **Untyped message IDs** -- The CLI accepted message IDs as
   strings, but AppleScript required integers. Without validation,
   non-numeric input could inject into `message id {value}`
   expressions. We added `int()` casting, but this was a band-aid.

### Maintenance burden

- **macOS only** -- Required a running Outlook desktop app and macOS
  automation permissions.
- **Fragile parsing** -- Relied on string splitting with `|||`
  delimiters; any field containing the delimiter would break parsing.
- **No pagination** -- AppleScript enumeration loaded all messages
  into memory.
- **Permission dialogs** -- First run triggered a macOS automation
  permission dialog that confused users.

### Graph API advantages

- **Cross-platform** -- Works anywhere with network access, no
  desktop app needed.
- **Typed responses** -- JSON responses with well-defined schemas.
- **Pagination** -- Built-in `$top`, `$skip`, `$filter` via OData.
- **Token management** -- MSAL handles refresh automatically.
- **No injection risk** -- Parameters passed as query strings, not
  interpolated into scripts.

## Reference

The original source files were:

```
src/ess_outlook/applescript/
├── __init__.py            # Exported OutlookClient, run_applescript
├── runner.py              # osascript subprocess wrapper
└── client/
    ├── __init__.py
    ├── client.py          # OutlookClient with all AppleScript logic
    └── test_client.py     # Unit tests (mocked osascript calls)
```
