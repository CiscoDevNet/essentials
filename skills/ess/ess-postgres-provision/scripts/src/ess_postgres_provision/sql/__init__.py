"""Composed statements, each tagged with the role that runs it.

Every identifier and literal goes through `psycopg.sql`, so names are quoted
by the driver rather than by string formatting.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from ..exceptions import ProvisioningError

REDACTED = "***"


class Runner(StrEnum):
    """Who runs a statement.

    `OWNER` statements run as the admin under `SET ROLE <base>_owner`,
    because the admin is granted `SET` but not `INHERIT` on the owner.
    """

    ADMIN = "admin"
    OWNER = "owner"


@dataclass(frozen=True)
class Statement:
    """One statement and how to run and show it.

    Attributes:
        runner: Who runs it.
        query: The statement as sent to the server.
        purpose: A short label naming the step, used in errors.
        display: The statement as shown in a dry run, when it differs from
            `query` because it carries a secret.
        only_if: A query returning one boolean; the statement runs only
            when it returns true.
    """

    runner: Runner
    query: sql.Composable
    purpose: str
    display: sql.Composable | None = None
    only_if: sql.Composable | None = None


@dataclass(frozen=True)
class Phase:
    """Statements that run on one connection, optionally in one transaction.

    Attributes:
        database: The database the connection is open on.
        statements: The statements, in order.
        transaction: Run them in one transaction.
    """

    database: str
    statements: Sequence[Statement]
    transaction: bool = False


def identifier(name: str) -> sql.Identifier:
    """Shorthand for `sql.Identifier`."""
    return sql.Identifier(name)


def identifiers(names: Sequence[str]) -> sql.Composed:
    """A comma-separated list of quoted identifiers."""
    return sql.SQL(", ").join(sql.Identifier(name) for name in names)


def password_clause(verifier: str) -> tuple[sql.Composable, sql.Composable]:
    """`PASSWORD '<verifier>'` for the server and `PASSWORD '***'` for display."""
    sent = sql.SQL("PASSWORD {}").format(sql.Literal(verifier))
    shown = sql.SQL("PASSWORD {}").format(sql.Literal(REDACTED))
    return sent, shown


def execute(conn: psycopg.Connection, statement: Statement, owner: str) -> bool:
    """Run one statement as its runner.

    Returns:
        False if `only_if` returned false and the statement was skipped.

    Raises:
        ProvisioningError: The server rejected the statement. The message
            names the step, never the statement text.
    """
    try:
        if statement.only_if is not None:
            row = conn.execute(statement.only_if).fetchone()
            if not row or not row[0]:
                return False
        if statement.runner is Runner.OWNER:
            _execute_as_owner(conn, statement.query, owner)
        else:
            conn.execute(statement.query)
    except psycopg.Error as exc:
        msg = f"Step {statement.purpose!r} failed: {_server_message(exc)}"
        raise ProvisioningError(msg) from exc
    return True


def run_phase(
    conn: psycopg.Connection,
    phase: Phase,
    owner: str,
    before_commit: Callable[[], None] | None = None,
) -> None:
    """Run a phase's statements, in one transaction if the phase asks for it.

    Args:
        conn: A connection to `phase.database`, in autocommit mode.
        phase: The statements.
        owner: The owner role, for `OWNER` statements.
        before_commit: Called after the last statement, just before `COMMIT`,
            so a caller can record that the writes may now be live.
    """
    if not phase.transaction:
        for statement in phase.statements:
            execute(conn, statement, owner)
        return
    with conn.transaction():
        for statement in phase.statements:
            execute(conn, statement, owner)
        if before_commit is not None:
            before_commit()


def _execute_as_owner(
    conn: psycopg.Connection, query: sql.Composable, owner: str
) -> None:
    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(owner)))
    try:
        conn.execute(query)
    finally:
        if conn.info.transaction_status is not TransactionStatus.INERROR:
            conn.execute(sql.SQL("RESET ROLE"))


def _server_message(exc: psycopg.Error) -> str:
    diag = exc.diag
    if diag.message_primary:
        return diag.message_primary
    return str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__


def render(phases: Sequence[Phase], owner: str, admin: str) -> str:
    """The SQL a run would send, with every password verifier redacted."""
    lines: list[str] = []
    for phase in phases:
        lines.append(f"-- Connected to {phase.database} as {admin}")
        if phase.transaction:
            lines.append("BEGIN;")
        lines.extend(
            _render_statement(statement, owner) for statement in phase.statements
        )
        if phase.transaction:
            lines.append("COMMIT;")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_statement(statement: Statement, owner: str) -> str:
    text = (statement.display or statement.query).as_string() + ";"
    if statement.only_if is not None:
        text = f"-- only if: {statement.only_if.as_string()}\n{text}"
    if statement.runner is Runner.OWNER:
        set_role = sql.SQL("SET ROLE {};").format(sql.Identifier(owner)).as_string()
        text = f"{set_role}\n{text}\nRESET ROLE;"
    return text
