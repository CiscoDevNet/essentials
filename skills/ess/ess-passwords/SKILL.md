---
name: ess-passwords
description: >-
  Generate readable passwords and passphrases from a filtered EFF wordlist,
  with the entropy of each, and pipe them straight into a secret store. Use
  when the user asks to generate, create, suggest, or rotate a password,
  passphrase, or other secret value, or when a task needs a new password for a
  database, service account, or config secret. Also the password generator
  other skills' CLIs import.
license: Apache-2.0
compatibility: >-
  Requires uv. The first run fetches click and xkcdpass from PyPI, which needs
  network access.
metadata:
  author: Matt Norris
  version: "0.1.0"
---

# Passwords

Generates passwords like `swept-staunch-circling-showdown-SCREEN`: random
words from the EFF long list, one upper-cased, with crude words filtered out
so the result can be read aloud or pasted into a ticket. The password goes to
stdout and the entropy note to stderr.

`SKILL_DIR` below is the absolute path of the directory containing this
`SKILL.md`. Do not use a repo-relative path; the skill may be installed
outside the repo.

```bash
uvx --from "$SKILL_DIR/scripts" ess-passwords generate --digits 4
```

## Deliver it without reading it

A password the agent prints lands in the transcript. Pipe it straight into
whatever stores it, and report only where it went and the entropy note:

```bash
uvx --from "$SKILL_DIR/scripts" ess-passwords generate --digits 4 \
  | uv run pulumi config set myproj:dbPassword --secret
```

- Never echo the password into chat, a commit, a log, or a file you then
  read back.
- If there is nowhere to pipe it, because a person must type it somewhere,
  tell the user to run the command in their own terminal instead of running
  it yourself.
- Match the consuming system's rules with flags rather than editing the
  output: `--max-length` for a length cap, `--digits` for a digit
  requirement, `--separator` for a character set. Run `generate --help` for
  the full list.

## Gotchas

- **Entropy is reported, not assumed.** Quote the stderr note, such as
  `63 bits of entropy`, rather than a figure from memory. `--max-length`
  makes that figure an upper bound.
- **A crude word slipped through?** Add it to `_EXCLUDED_WORDS` in
  `scripts/src/ess_passwords/wordlist.py` instead of regenerating by hand.
- **Other skills import this code.** A CLI that needs passwords depends on
  `scripts/` by path; see the "Running the CLI" section of
  [references/cli.md](references/cli.md) before adding one.

Read [references/cli.md](references/cli.md) for every flag, the `--json`
output, and the Python API (`generate_password`, `PasswordOptions`).
