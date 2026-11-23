"""Statements for `rotate` and `teardown`, all on Connection 1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from psycopg import sql

from ..naming import Names
from . import Runner, Statement, identifier, password_clause
from .maintenance import grant_owner_to_admin, revoke_owner_from_admin


def rotate_statements(names: Names, verifiers: Mapping[str, str]) -> list[Statement]:
    """`ALTER ROLE ... PASSWORD` for each rotated role kind."""
    statements: list[Statement] = []
    for kind, verifier in verifiers.items():
        role = names.role(kind)
        sent, shown = password_clause(verifier)
        alter = sql.SQL("ALTER ROLE {} {}")
        statements.append(
            Statement(
                Runner.ADMIN,
                alter.format(identifier(role), sent),
                f"rotate password for {role}",
                display=alter.format(identifier(role), shown),
            )
        )
    return statements


def regrant_owner(names: Names, admin: str) -> Statement:
    """Teardown step 2: dropping a database takes its owner."""
    return grant_owner_to_admin(names, admin)


def allow_connections(names: Names, *, allowed: bool) -> Statement:
    """Block or restore new connections without touching the database's ACL."""
    return Statement(
        Runner.OWNER,
        sql.SQL("ALTER DATABASE {} WITH ALLOW_CONNECTIONS {}").format(
            identifier(names.database), sql.SQL("true" if allowed else "false")
        ),
        "restore connections" if allowed else "block connections",
    )


def drop_database(names: Names) -> Statement:
    """Teardown step 6, under `SET ROLE` to the owner."""
    return Statement(
        Runner.OWNER,
        sql.SQL("DROP DATABASE {}").format(identifier(names.database)),
        f"drop database {names.database}",
    )


def drop_roles(roles: Sequence[str]) -> list[Statement]:
    """`DROP ROLE` for each role, as the admin."""
    return [
        Statement(
            Runner.ADMIN,
            sql.SQL("DROP ROLE {}").format(identifier(role)),
            f"drop role {role}",
        )
        for role in roles
    ]


def restore_statements(names: Names, admin: str) -> list[Statement]:
    """The teardown `finally`: restore connections, then give the owner back.

    Order matters: once `SET` is revoked, the admin can no longer act as the
    owner to restore connections.
    """
    return [
        allow_connections(names, allowed=True),
        revoke_owner_from_admin(names, admin),
    ]
