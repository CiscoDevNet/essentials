"""CLI entry point for ess-passwords.

Every command here is read-only: it reads the wordlist, prints a password,
and writes nothing anywhere. `.cursor/rules/cli-write-safety.mdc` therefore
forbids `--dry-run` and a confirmation prompt -- there is no state to
preview and nothing to consent to. Do not add them: generating a password
is not the same as rotating one, and a decorative `--dry-run` teaches
operators to distrust the real ones.
"""

from __future__ import annotations

import json

import click

from .exceptions import EssPasswordsError
from .password import (
    DEFAULT_SEPARATOR,
    DEFAULT_WORD_COUNT,
    GeneratedPassword,
    PasswordOptions,
    generate_password,
)


@click.group()
def main() -> None:
    """Generate readable passwords from a filtered EFF wordlist."""


@main.command("generate")
@click.option(
    "--words",
    default=DEFAULT_WORD_COUNT,
    show_default=True,
    help="Number of words in the password.",
)
@click.option(
    "--separator",
    default=DEFAULT_SEPARATOR,
    show_default=True,
    help="Separator between words.",
)
@click.option(
    "--max-length",
    type=int,
    default=None,
    help="Regenerate until the password fits within this many characters.",
)
@click.option(
    "--capitalize-at",
    type=int,
    default=None,
    help=(
        "Position of the upper-cased word, counting from 0. "
        "Omit to have it chosen at random."
    ),
)
@click.option(
    "--digits",
    default=0,
    show_default=True,
    help="Digits to append after the last word.",
)
@click.option(
    "--count",
    "-n",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Number of passwords to print, one per line.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit JSON instead of a bare password.",
)
def generate_command(  # noqa: PLR0913 -- Click option surface; bundling hurts readability
    words: int,
    separator: str,
    max_length: int | None,
    capitalize_at: int | None,
    digits: int,
    count: int,
    as_json: bool,
) -> None:
    """Print a password such as `marble-TUNDRA-lantern-copper-bison`.

    The password goes to stdout and its entropy to stderr, so the output
    pipes straight into a secret store without a stray note tagging along.
    """
    options = PasswordOptions(
        word_count=words,
        separator=separator,
        max_length=max_length,
        capitalized_index=capitalize_at,
        digit_count=digits,
    )

    try:
        generated = [generate_password(options) for _ in range(count)]
    except EssPasswordsError as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        payload = [_as_dict(item) for item in generated]
        click.echo(json.dumps(payload[0] if count == 1 else payload))
        return

    for item in generated:
        click.echo(item.value)

    first = generated[0]
    click.echo(
        f"({first.entropy_bits:.0f} bits of entropy from "
        f"{first.wordlist_size:,} candidate words)",
        err=True,
    )


def _as_dict(generated: GeneratedPassword) -> dict[str, object]:
    """The JSON shape for one generated password."""
    return {
        "password": generated.value,
        "entropy_bits": round(generated.entropy_bits, 1),
        "wordlist_size": generated.wordlist_size,
    }


if __name__ == "__main__":
    main()
