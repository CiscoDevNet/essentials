# groups.toml format

Read this only when someone wants to edit the file by hand. The CLI writes the same
format, and hand edits survive later CLI writes, including your comments.

```toml
[users.ada]
name = "Ada Lovelace"
aliases = ["Ada"]
email = "ada@example.com"

[users.ada.handles]
github = ["ada_example", "ada_oss"]
webex = ["ada@example.com"]

[groups.platform-team]
aliases = ["my pod"]
members = ["ada", "grace@example.com", "Someone New"]

[groups.my-team]
aliases = ["my team"]
members = ["ada"]
groups = ["platform-team"]
```

## `[users.<key>]`

The key is a short, stable identifier, such as `ada`. Quote it in the header if it
contains anything other than letters, digits, `-`, or `_`: `[users."zoe.obrien"]`.
A key needs at least one ASCII letter or digit, and can't start with `user:` or
`group:`; the same holds for group keys.

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | Yes | Display name. |
| `aliases` | No | Nicknames and shortcuts, such as `["Ada"]`. |
| `email` | No | Email address ([RFC 5322](https://www.rfc-editor.org/rfc/rfc5322) addr-spec). |

## `[users.<key>.handles]`

Usernames on online services, one key per service: `github`, `webex`, `slack`, or
any other. Each value is a list, so a user can have a work login and a public
one; a single string also works. Service names ignore case, as JSContact requires,
and a CLI edit merges keys that differ only in case. Handles themselves ignore case
only: `sam-smith` and `sam_smith` are two accounts. The skill attaches no meaning to
a service name; whatever uses the handles decides which service it needs.

## `[groups.<key>]`

| Field | Required | Meaning |
| --- | --- | --- |
| `aliases` | No | Other names for the group, such as `["my pod"]`. |
| `members` | No | Users in the group. Store user keys; an email or a bare name also works. |
| `groups` | No | Keys of other groups whose members are also members of this one. |

The CLI always stores members by key. A member written another way, such as `"Ada"`
or a known user's email, still resolves, but `validate` warns and names the key to
store instead. A bare name that matches no user (and has no `@`) is reported as
unresolved: the agent asks who it is rather than guessing.

## Rules

- The file has only `[users.<key>]` and `[groups.<key>]` tables.
- `name` and `email` are strings. `aliases`, `members`, and `groups` are lists of
  strings, even with one entry: `members = ["ada"]`, not `members = "ada"`.
  Fields not listed here may be a string or a list of strings.
- Keys, names, aliases, emails, and handles are all lookup names, and each kind
  compares by its own rule. All of them ignore case, and Unicode text matches
  however it was typed: `zoë` written as one character or as `o` plus an accent.
  - Keys compare as slugs: `Platform Team`, `platform_team`, and
    `platform-team` all find the key `platform-team`.
  - Names and aliases compare as nicknames
    ([RFC 8266](https://www.rfc-editor.org/rfc/rfc8266)): runs of spaces count as
    one, and punctuation counts, so `Jean-Luc` and `Jean Luc` differ.
  - Handles compare as usernames ([RFC 8265](https://www.rfc-editor.org/rfc/rfc8265)):
    `sam-smith` and `sam_smith` are different accounts.
  - Emails ignore case only, so `alice-smith@example.com` and
    `alice_smith@example.com` are different users.
- An email must be a valid RFC 5322 address; `validate` and the CLI reject one
  that isn't. The CLI stores and prints it in canonical form, dropping comments
  and extra spaces: `Jane@Example.com (work)` becomes `Jane@Example.com`.
- A lookup name may belong to only one user or group. `validate` reports clashes,
  and the CLI refuses any change that would create one.
- A `user:` or `group:` prefix limits a lookup to that kind, as `chown user:group`
  does: `user:pod` and `group:pod` stay distinct even when a hand edit made `pod`
  ambiguous.
- Changing a user's name, email, alias, or handle with `user update` rewrites group
  members that used the old value to the user's key, so they stay attached.
  Removing a group alias with `group update` does the same for nested groups.
- Groups may overlap freely, and may nest, but not in a cycle. `validate` reports
  each unknown nested group, and warns about one not stored by key.

Check the file after editing:

```bash
uv run --script "$SKILL_DIR/scripts/my_groups.py" validate
```
