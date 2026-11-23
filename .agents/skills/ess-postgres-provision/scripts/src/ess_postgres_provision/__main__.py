"""CLI entry point for ess-postgres-provision.

`create`, `rotate`, and `teardown` write, so each takes the group's
`--dry-run`, prompts by default, and accepts `--yes`. `verify` only reads.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import click

from .connection import Connector, Target
from .exceptions import EXIT_TERMINATED, InvalidNameError, ProvisionError, Terminated
from .lifecycle import rotate, teardown
from .naming import ROLE_KINDS, Names, derive_names
from .options import (
    CreateOptions,
    DeliveryOptions,
    RotateOptions,
    TeardownOptions,
    VerifyOptions,
)
from .passwords import DEFAULT_DIGITS, MIN_DIGITS
from .provision import create
from .sinks import SINK_FACTORIES, DeliveryReport
from .sql.database import (
    DEFAULT_IDLE_IN_TRANSACTION_TIMEOUT,
    DEFAULT_STATEMENT_TIMEOUT,
    ReaderGuards,
)
from .ui import Ui
from .verify import render_table, require_passed, verify

_DEFAULT_PORT = 5432
_MAX_PORT = 65535

type _Decorator = Callable[[Callable[..., Any]], Callable[..., Any]]


class CommandError(click.ClickException):
    """A domain error, reported with the exit code its type maps to."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@contextmanager
def _boundary() -> Iterator[None]:
    """Convert domain exceptions to Click exceptions with matching exit codes."""
    try:
        yield
    except ProvisionError as exc:
        raise CommandError(str(exc), exc.exit_code) from exc
    except Terminated as exc:
        raise CommandError("Terminated.", EXIT_TERMINATED) from exc


def _base_name(_ctx: click.Context, _param: click.Parameter, value: str) -> Names:
    try:
        return derive_names(value)
    except InvalidNameError as exc:
        raise click.BadParameter(str(exc)) from exc


def _confirm(skip: bool) -> Callable[[str], None]:
    def confirm(question: str) -> None:
        if skip:
            return
        if not sys.stdin.isatty():
            msg = "This command writes; pass --yes to confirm, or --dry-run to preview."
            raise click.UsageError(msg)
        click.confirm(f"\n{question}", abort=True, err=True)

    return confirm


def _ui(ctx: click.Context, *, yes: bool) -> Ui:
    return Ui(
        echo=click.echo,
        note=lambda message: click.echo(message, err=True),
        confirm=_confirm(yes),
        dry_run=ctx.obj["dry_run"],
    )


def _connector(
    host: str, port: int, admin_user: str, allow_insecure: bool
) -> Connector:
    target = Target(host, port, admin_user, allow_insecure)
    prompt = (
        (lambda text: click.prompt(text, hide_input=True, err=True))
        if sys.stdin.isatty()
        else None
    )
    return Connector(target, prompt)


def _optional(value: str) -> str | None:
    return None if value.strip() in {"", "0"} else value


def _print_report(report: DeliveryReport) -> None:
    for message in report.messages:
        click.echo(message)
    for failure in report.failures:
        click.echo(f"Warning: sink failed: {failure}", err=True)


# === Shared options ===


def connection_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """`--host`, `--port`, `--admin-user`, and `--allow-insecure`."""
    decorators: list[_Decorator] = [
        click.option(
            "--host", required=True, help="Server host, IP, or socket directory."
        ),
        click.option(
            "--port",
            type=click.IntRange(1, _MAX_PORT),
            default=_DEFAULT_PORT,
            show_default=True,
            help="Server port.",
        ),
        click.option(
            "--admin-user",
            required=True,
            help=(
                "Role to provision as: a superuser, or CREATEDB and CREATEROLE. Its "
                "password comes from PGPASSWORD, ~/.pgpass, or a prompt."
            ),
        ),
        click.option(
            "--allow-insecure",
            is_flag=True,
            default=False,
            help="Allow a non-local host without SSL.",
        ),
    ]
    for decorator in reversed(decorators):
        command = decorator(command)
    return command


def delivery_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """`--sink`, `--sink-path`, and `--digits`."""
    decorators: list[_Decorator] = [
        click.option(
            "--sink",
            "sinks",
            multiple=True,
            type=click.Choice(list(SINK_FACTORIES)),
            help="Where credentials go; repeatable. Default: file.",
        ),
        click.option(
            "--sink-path",
            "sink_paths",
            multiple=True,
            type=click.Path(path_type=Path, dir_okay=False),
            help="Write a credentials file here instead; repeatable.",
        ),
        click.option(
            "--digits",
            type=click.IntRange(min=MIN_DIGITS),
            default=DEFAULT_DIGITS,
            show_default=True,
            help="Digits appended to each generated password.",
        ),
    ]
    for decorator in reversed(decorators):
        command = decorator(command)
    return command


def reader_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """The reader guardrail flags."""
    decorators: list[_Decorator] = [
        click.option(
            "--reader-read-only/--no-reader-read-only",
            default=True,
            show_default=True,
            help="Default the reader's transactions to read-only.",
        ),
        click.option(
            "--reader-idle-timeout",
            default=DEFAULT_IDLE_IN_TRANSACTION_TIMEOUT,
            show_default=True,
            help="Reader's idle_in_transaction_session_timeout; 0 leaves it unset.",
        ),
        click.option(
            "--reader-statement-timeout",
            default=DEFAULT_STATEMENT_TIMEOUT,
            show_default=True,
            help="Reader's statement_timeout; 0 leaves it unset.",
        ),
    ]
    for decorator in reversed(decorators):
        command = decorator(command)
    return command


_yes_option = click.option(
    "--yes", "-y", is_flag=True, default=False, help="Skip the confirmation prompt."
)
_extension_option = click.option(
    "--extension",
    "extensions",
    multiple=True,
    help="Extension to create in schema public; repeatable.",
)
_base_name_argument = click.argument("base_name", callback=_base_name)


# === Commands ===


@click.group()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run every check and show the SQL that would run, without writing.",
)
@click.pass_context
def main(ctx: click.Context, dry_run: bool) -> None:
    """Provision a Postgres database, schema, and four separated login roles."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    ctx.obj = {"dry_run": dry_run}


@main.command("create")
@_base_name_argument
@connection_options
@_extension_option
@delivery_options
@reader_options
@_yes_option
@click.pass_context
def create_command(  # noqa: PLR0913 -- Click option surface; bundling hurts readability
    ctx: click.Context,
    base_name: Names,
    host: str,
    port: int,
    admin_user: str,
    allow_insecure: bool,
    extensions: tuple[str, ...],
    sinks: tuple[str, ...],
    sink_paths: tuple[Path, ...],
    digits: int,
    reader_read_only: bool,
    reader_idle_timeout: str,
    reader_statement_timeout: str,
    yes: bool,
) -> None:
    """Create database and schema BASE_NAME, and roles BASE_NAME_owner,
    BASE_NAME_migrations, BASE_NAME_app, and BASE_NAME_reader."""
    options = CreateOptions(
        extensions=extensions,
        guards=ReaderGuards(
            read_only=reader_read_only,
            idle_in_transaction_timeout=_optional(reader_idle_timeout),
            statement_timeout=_optional(reader_statement_timeout),
        ),
        delivery=DeliveryOptions(sinks, sink_paths, digits),
    )
    connector = _connector(host, port, admin_user, allow_insecure)
    with _boundary():
        result = create(connector, base_name, options, _ui(ctx, yes=yes))
    if result is None:
        return
    _print_report(result.report)
    click.echo(f"Each password carries {result.entropy_bits:.0f} bits of entropy.")


@main.command("verify")
@_base_name_argument
@connection_options
@_extension_option
@click.option(
    "--reader-read-only/--no-reader-read-only",
    default=True,
    show_default=True,
    help="Expect the reader's read-only default.",
)
def verify_command(  # noqa: PLR0913 -- Click option surface; bundling hurts readability
    base_name: Names,
    host: str,
    port: int,
    admin_user: str,
    allow_insecure: bool,
    extensions: tuple[str, ...],
    reader_read_only: bool,
) -> None:
    """Check BASE_NAME's catalog against the design. Read-only.

    Rerun it after migrations to check the tables and functions they created.
    """
    connector = _connector(host, port, admin_user, allow_insecure)
    with _boundary():
        checks = verify(
            connector, base_name, VerifyOptions(extensions, reader_read_only)
        )
        click.echo(render_table(checks))
        require_passed(checks)


@main.command("rotate")
@_base_name_argument
@connection_options
@click.option(
    "--role",
    "kinds",
    multiple=True,
    type=click.Choice(ROLE_KINDS),
    help="Role to rotate; repeatable. Default: all four.",
)
@delivery_options
@_yes_option
@click.pass_context
def rotate_command(  # noqa: PLR0913 -- Click option surface; bundling hurts readability
    ctx: click.Context,
    base_name: Names,
    host: str,
    port: int,
    admin_user: str,
    allow_insecure: bool,
    kinds: tuple[str, ...],
    sinks: tuple[str, ...],
    sink_paths: tuple[Path, ...],
    digits: int,
    yes: bool,
) -> None:
    """Set new passwords for BASE_NAME's roles and deliver them to a new file."""
    options = RotateOptions(
        kinds=kinds or ROLE_KINDS, delivery=DeliveryOptions(sinks, sink_paths, digits)
    )
    connector = _connector(host, port, admin_user, allow_insecure)
    with _boundary():
        report = rotate(connector, base_name, options, _ui(ctx, yes=yes))
    if report is not None:
        _print_report(report)


@main.command("teardown")
@_base_name_argument
@connection_options
@click.option(
    "--terminate-sessions",
    is_flag=True,
    default=False,
    help="End other sessions on the database instead of refusing.",
)
@_yes_option
@click.pass_context
def teardown_command(  # noqa: PLR0913 -- Click option surface; bundling hurts readability
    ctx: click.Context,
    base_name: Names,
    host: str,
    port: int,
    admin_user: str,
    allow_insecure: bool,
    terminate_sessions: bool,
    yes: bool,
) -> None:
    """Drop an empty BASE_NAME database and its roles, from any partial state."""
    connector = _connector(host, port, admin_user, allow_insecure)
    with _boundary():
        dropped = teardown(
            connector, base_name, TeardownOptions(terminate_sessions), _ui(ctx, yes=yes)
        )
    for item in dropped:
        click.echo(f"Dropped {item}")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter  # Click injects params at runtime
