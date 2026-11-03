---
name: ess-my-groups
description: >-
  Resolve and maintain the user's personal users and groups: nicknames like "Ada"
  and group names like "my team", "my pod", or "platform team", which may overlap
  and nest. Use whenever a request refers to people by a group name or a nickname
  ("PRs my pod asked me to review", "what did Ada send me", "ping my team"), to turn
  those names into users with emails and service handles before doing the task, or
  when the user asks to add, rename, or remove a user or a group, or asks who is in
  a group. These are personal groups kept in a local file, not corporate directory
  groups.
license: Apache-2.0
compatibility: >-
  Requires uv. The first run fetches the pinned tomlkit package, which needs network
  access.
metadata:
  author: Matt Norris
  version: "1.0.0"
---

# My Groups

The user keeps a small file of users (with nicknames, an email, and handles on
services such as GitHub or Webex) and named groups of those users. This skill turns
"my pod" or "Ada" into those users, and edits the file when the user asks, so they
never touch TOML themselves. It only answers "who"; the task that needs the people
(a search, a message, a review) is done with whatever tool fits it.

`SKILL_DIR` below is the absolute path of the directory containing this `SKILL.md`.
Do not use a repo-relative path; the skill may be installed outside the repo.

```bash
uv run --script "$SKILL_DIR/scripts/my_groups.py" resolve "my pod"
```

## The file

`${XDG_CONFIG_HOME}/ess-my-groups/groups.toml`. `XDG_CONFIG_HOME` counts only when it
is absolute; otherwise the path is `~/.config/ess-my-groups/groups.toml`.
`ESS_MY_GROUPS_FILE` overrides both. `my_groups.py path` prints the resolved path.

Read [references/groups-format.md](references/groups-format.md) only if you need the
schema, for example when the user wants to edit the file by hand.

## Resolve before acting

When a request names a group or a user by nickname:

1. Run `resolve` with every name from the request, in one call:
   `uv run --script "$SKILL_DIR/scripts/my_groups.py" resolve "my pod" Ada`
2. Read the output: a JSON array of [JSContact](https://www.rfc-editor.org/rfc/rfc9553)
   Cards.
   - Each group you named comes first, as a Card with `"kind": "group"`. Its
     `members` holds the `uid` of every user in the group, nested groups included.
   - Then comes one Card per user, deduplicated across overlapping and nested
     groups. Its `uid` is `user:<key>`, or `mailto:<address>` for an email with no
     user entry. It may have `name.full`, `nicknames`, `emails` (each with an
     `address`), and `onlineServices`, where each entry has a `service`, such as
     `github`, and a `user`, the handle. A user may have several handles on one
     service; use all of them.
3. Handle gaps before doing the task, not after:
   - stderr lists `warning: unresolved name '…'` for bare names with no user
     entry. Say so, and ask whether to add them (with an email) or skip them.
   - Check each member for the exact identifier the task needs: an email, or a
     handle on that particular service. Having one doesn't stand in for the other;
     a member with an email but no GitHub handle can't be found by a GitHub search.
     Name every member who lacks it in your answer, and offer to add it.
4. If `resolve` fails with "No user or group named …", show the "Did you mean" hint
   if there is one, and otherwise ask the user who they meant. Don't guess. If it
   fails because a name matches more than one entry, retry with the `user:` or
   `group:` form it lists.
5. Then do the task with the resolved emails and handles.

When a command takes plain values, print them one per line instead of JSON:
`resolve "my pod" --handle github` prints every GitHub handle, and `--email` prints
every email. Members without one are listed on stderr, so report them. Add `-0` to
end each value with NUL instead, for `xargs -0`.

Data goes to stdout and warnings to stderr. `resolve` exits 0 even when something
is missing; add `--strict` to exit 3 instead when a name is unresolved or a member
lacks the requested email or handle. Other failures exit 1, and bad arguments
exit 2.

To answer "who is in my team?", run `show "my team"`. `list` prints everything.

## Adding and editing

Turn the user's plain-language request into CLI calls. Ask only for what a command
can't run without: a user needs a name, and a new group needs at least one member
or nested group. Don't ask for optional handles up front; offer to add them later.

| User says | Command |
| --- | --- |
| "Add Alan, alan@example.com, nickname Al" | `user add "Alan Turing" --alias Al --email alan@example.com` |
| "Ada's GitHub is ada_example" | `user update Ada --add-handle github=ada_example` |
| "Alan's Slack handle is al" | `user update Alan --add-handle slack=al` |
| "Ada stopped using ada_oss" | `user update Ada --remove-handle github=ada_oss` |
| "Forget Alan's Slack" | `user update Alan --remove-handle slack` |
| "Drop Ada's email" | `user update Ada --email ""` |
| "Remove Alan entirely" | `user remove Alan` |
| "Make a group called reviewers with Ada and Grace" | `group add reviewers --member Ada --member Grace` |
| "Also call my team 'the crew'" | `group update "my team" --add-alias "the crew"` |
| "My team includes my pod" | `group update "my team" --include "my pod"` |
| "Add Alan and jdoe@example.com to my pod" | `group add-member "my pod" Alan jdoe@example.com` |
| "Take Grace out of my team" | `group remove-member "my team" Grace` |
| "Delete the reviewers group" | `group remove reviewers` |

Run `uv run --script "$SKILL_DIR/scripts/my_groups.py" --help` (or `user --help`,
`group --help`) for every flag.

Every write follows the same three steps:

1. Run the command with `--dry-run`. It prints a list of planned changes and a diff
   of the file. Nothing is written.
2. Show the user the planned changes. Point out every line that says "Create user
   … with only a name", especially ones with a "Did you mean" hint: that's usually
   a typo, or a user not added yet.
3. Only after the user confirms, re-run the identical command with `--yes`. Your
   shell has no terminal, so without `--yes` the command refuses to write.

One confirmation can cover several related commands: show all their dry-runs
together, then run each with `--yes`.

## Gotchas

- Keys, display names, aliases, emails, and handles all match, ignoring case.
  Beyond that:
  - Keys are slugs, so "Platform Team" and "platform_team" find the key
    `platform-team`.
  - Names and aliases also ignore extra spaces, but punctuation counts:
    "my-pod" doesn't match the alias "my pod". It gets a "Did you mean" hint.
  - Handles and emails are exact apart from case: `sam-smith` and `sam_smith` are
    different accounts. Pass them exactly as written.
- A name may belong to only one entry. Writes refuse a name that is already taken,
  and refuse any change that would leave a name meaning two entries. `user:ada` or
  `group:my-team` picks the kind explicitly, in any command.
- A group member can be a user, a bare email, or (from hand edits) a bare name.
  `group add-member` turns an unknown bare name into a stub user with only a
  name, so it can be completed later with `user update`.
- To nest groups, use `--include`. Passing a group name as a member is an error.
- `remove-member` removes only direct members. If the user is in the group
  through a nested group, remove them there, or `--exclude` that nested group.
- Every write keeps the previous file as `groups.toml.bak`, next to the file.
  Restore it by copying it back if the user wants to undo.
- A write refuses if the file changed after its plan was shown, or if another write
  is in progress. Nothing is written; run the dry run again and show the new plan.
- Comments and the order of entries survive CLI edits. A comment sitting directly
  above a table belongs to the table before it, so removing that earlier entry
  removes the comment too.
- If there is no file yet, the first `user add` or `group add` creates it.
  `init` instead writes an example file to start from; it never overwrites.
- After hand edits, or when results look wrong, run `validate`.
