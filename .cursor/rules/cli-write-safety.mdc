---
description: Every CLI in this repo that writes or destroys must support --dry-run, confirm by default, and accept --yes
alwaysApply: true
---

# CLI Write Safety

Applies to **every command-line tool produced in this repo**, whatever the language or
argument parser: Click groups, `argparse` scripts under `tools/`, Django management
commands, TypeScript `bin` entries, and shell scripts.

## The three requirements

Any command that writes remote or local state, deletes, rotates a credential, or is
otherwise not trivially reversible must have all three:

1. **`--dry-run`** — runs the same code path, prints exactly what would change, exits 0,
   and touches nothing. It is not a separate "plan" branch that can drift from the real
   one; resolve the same targets and build the same payloads, then stop before the write.
2. **Confirmation by default** — print a summary of what is about to happen (counts,
   target names, account/stack/environment), then prompt. Abort on anything but yes.
3. **`--yes`** (alias `-y`) — bypasses the prompt, and nothing else. It must never imply
   or cancel `--dry-run`.

## Use these exact flag names

`--dry-run` and `--yes`. Do not invent `--apply`, `--submit`, `--commit`, `--force`,
`--no-confirm`, or `--for-real`.

Opt-in-to-write flags look safe but are not: they make the *safe* path the one the
operator has to remember, and every tool picks a different word for it, so muscle memory
from one tool does nothing for the next. Prompting by default gives the same protection
without depending on recall.

## Precedence and non-interactive runs

- `--dry-run` wins if both flags are passed.
- When a **real write** would occur, never silently proceed without explicit consent.
  Without a TTY, or in `--json` mode, fail and tell the operator to pass `--yes`.
  `--dry-run` skips this check because nothing is written.

## Read-only commands

Must not prompt, and must not offer `--dry-run` — there is nothing to preview.

## Where the flags live

Put `--dry-run` on the group when it governs every subcommand, and `--yes` on each write
command. `keys delete` in `packages/python/ess-langsmith-client/src/ess_langsmith_client/tools/keys.py`
shows the confirmation half: it lists the keys it will delete, prompts by default, and
accepts `--yes`. It does not yet offer `--dry-run`, and its prompt goes to stdout; do not
copy those two gaps. The complete shape:

```python
@click.option("--dry-run", is_flag=True, default=False,
              help="Show planned changes without submitting them.")
...
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation prompt.")
```

with a single guard called by every write path:

```python
def _confirm_or_abort(options, account, locations, *, skip: bool) -> None:
    """Require explicit consent before writing credentials."""
    if skip or options.dry_run:
        return

    # Real write only; --dry-run returned above. --json has no interactive
    # prompt to fall back on, so make the caller opt in rather than silently
    # skipping the guard.
    if options.as_json:
        raise click.UsageError("--json requires --yes, which confirms the write.")

    click.confirm(f"\nSet a new password for {account} in {len(locations)} location(s)?",
                  abort=True, err=True)
```

For interactive **real writes**, prompt on **stderr** (`err=True`) so piping stdout to
a file or `jq` still shows the question. Dry-run and `--yes` paths skip the prompt, so
`--dry-run --json` without `--yes` is valid.

`@click.confirmation_option(prompt=...)` gives you `--yes` for free and satisfies
requirements 2 and 3, but you still owe `--dry-run`.

For `argparse`, the equivalent is `--dry-run` / `--yes` store-true flags plus an explicit
`sys.stdin.isatty()` check before `input()` for real writes (not `--dry-run`); fail with
a message to pass `--yes` if non-interactive.

## Tests (Click / Python)

For Click-based Python CLIs, co-locate `test_*.py` per the repo's testing convention.
Two cases at minimum, using Click's `CliRunner`:

- `--dry-run` performs no writes (assert the client/session mock was never called).
- `--yes` skips the prompt (assert the command succeeds with no stdin).

TypeScript, shell, and Django commands must still prove the same three requirements,
using that language's test tooling and conventions.
