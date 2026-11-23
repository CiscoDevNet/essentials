"""Statements for Connection 2, opened on the new database."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from psycopg import sql

from ..naming import Names
from . import Runner, Statement, catalog, identifier, identifiers

DEFAULT_IDLE_IN_TRANSACTION_TIMEOUT = "60s"
DEFAULT_STATEMENT_TIMEOUT = "5min"


@dataclass(frozen=True)
class Extension:
    """An extension to create, and whether the owner may create it.

    Attributes:
        name: The extension name.
        trusted: Trusted extensions run under `SET ROLE` to the owner;
            untrusted ones run as the admin.
    """

    name: str
    trusted: bool


@dataclass(frozen=True)
class ReaderGuards:
    """Per-database defaults set on the reader role.

    Attributes:
        read_only: Set `default_transaction_read_only = on`.
        idle_in_transaction_timeout: `idle_in_transaction_session_timeout`,
            or None to leave it unset.
        statement_timeout: `statement_timeout`, or None to leave it unset.
    """

    read_only: bool = True
    idle_in_transaction_timeout: str | None = DEFAULT_IDLE_IN_TRANSACTION_TIMEOUT
    statement_timeout: str | None = DEFAULT_STATEMENT_TIMEOUT

    def settings(self) -> list[tuple[str, str]]:
        """The `(name, value)` pairs to set, in order."""
        pairs: list[tuple[str, str]] = []
        if self.read_only:
            pairs.append(("default_transaction_read_only", "on"))
        if self.idle_in_transaction_timeout:
            pairs.append(
                (
                    "idle_in_transaction_session_timeout",
                    self.idle_in_transaction_timeout,
                )
            )
        if self.statement_timeout:
            pairs.append(("statement_timeout", self.statement_timeout))
        return pairs


def database_statements(
    names: Names, extensions: Sequence[Extension], guards: ReaderGuards
) -> list[Statement]:
    """Everything Connection 2 runs, in order."""
    return [
        *schema_statements(names),
        *extension_statements(names, extensions),
        *schema_grant_statements(names),
        *search_path_statements(names),
        *default_privilege_statements(names),
        *reader_guard_statements(names, guards),
    ]


def schema_statements(names: Names) -> list[Statement]:
    """Create the dedicated schema; close `public` to `PUBLIC` if it is open."""
    return [
        Statement(
            Runner.OWNER,
            sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                identifier(names.schema), identifier(names.owner)
            ),
            f"create schema {names.schema}",
        ),
        Statement(
            Runner.OWNER,
            sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"),
            "revoke create on public",
            only_if=sql.SQL(catalog.PUBLIC_HOLDS_CREATE_ON_PUBLIC),
        ),
    ]


def extension_statements(
    names: Names, extensions: Sequence[Extension]
) -> list[Statement]:
    """`CREATE EXTENSION ... SCHEMA public` for each requested extension."""
    return [
        Statement(
            Runner.OWNER if extension.trusted else Runner.ADMIN,
            sql.SQL("CREATE EXTENSION IF NOT EXISTS {} SCHEMA public").format(
                identifier(extension.name)
            ),
            f"create extension {extension.name} in {names.database}",
        )
        for extension in extensions
    ]


def schema_grant_statements(names: Names) -> list[Statement]:
    """Migrations may create in the schema; app and reader may only use it."""
    schema = identifier(names.schema)
    return [
        Statement(
            Runner.OWNER,
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA {} TO {}").format(
                schema, identifier(names.migrations)
            ),
            "grant schema to migrations",
        ),
        Statement(
            Runner.OWNER,
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                schema, identifiers([names.app, names.reader])
            ),
            "grant schema usage to app and reader",
        ),
    ]


def search_path_statements(names: Names) -> list[Statement]:
    """Point every role at the dedicated schema, in this database only."""
    return [
        Statement(
            Runner.ADMIN,
            sql.SQL("ALTER ROLE {} IN DATABASE {} SET search_path = {}, public").format(
                identifier(role), identifier(names.database), identifier(names.schema)
            ),
            f"set search_path for {role}",
        )
        for role in names.roles
    ]


def default_privilege_statements(names: Names) -> list[Statement]:
    """Grants on objects migrations will create later.

    The function revoke has no `IN SCHEMA` on purpose: per-schema default
    privileges only add to the global ones, so a per-schema revoke does nothing.
    """
    for_migrations = sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {}").format(
        identifier(names.migrations)
    )
    in_schema = sql.SQL("{} IN SCHEMA {}").format(
        for_migrations, identifier(names.schema)
    )
    app = identifier(names.app)
    reader = identifier(names.reader)
    clauses = [
        (
            in_schema,
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(app),
            "app tables",
        ),
        (
            in_schema,
            sql.SQL("GRANT SELECT ON TABLES TO {}").format(reader),
            "reader tables",
        ),
        (
            in_schema,
            sql.SQL("GRANT USAGE, SELECT ON SEQUENCES TO {}").format(app),
            "app sequences",
        ),
        (
            for_migrations,
            sql.SQL("REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"),
            "functions from public",
        ),
        (
            in_schema,
            sql.SQL("GRANT EXECUTE ON FUNCTIONS TO {}").format(app),
            "app functions",
        ),
    ]
    return [
        Statement(
            Runner.OWNER,
            sql.SQL("{} {}").format(prefix, clause),
            f"default privileges: {label}",
        )
        for prefix, clause, label in clauses
    ]


def reader_guard_statements(names: Names, guards: ReaderGuards) -> list[Statement]:
    """Per-database defaults on the reader."""
    return [
        Statement(
            Runner.ADMIN,
            sql.SQL("ALTER ROLE {} IN DATABASE {} SET {} = {}").format(
                identifier(names.reader),
                identifier(names.database),
                identifier(setting),
                sql.Literal(value),
            ),
            f"set {setting} for {names.reader}",
        )
        for setting, value in guards.settings()
    ]
