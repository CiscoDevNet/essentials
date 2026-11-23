"""Statements for Connection 1, held open on the `postgres` database."""

from __future__ import annotations

from collections.abc import Mapping

from psycopg import sql

from ..naming import ROLE_KINDS, Names
from . import Runner, Statement, identifier, identifiers, password_clause

_ROLE_ATTRIBUTES = sql.SQL(
    "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT"
)


def role_statements(
    names: Names, verifiers: Mapping[str, str], run_id: str, admin: str
) -> list[Statement]:
    """The single transaction that creates all four roles with their markers.

    Args:
        names: The derived names.
        verifiers: SCRAM verifier per role kind.
        run_id: The run ID stamped into every marker.
        admin: The provisioning role.
    """
    statements: list[Statement] = []
    for kind in ROLE_KINDS:
        role = names.role(kind)
        sent, shown = password_clause(verifiers[kind])
        create = sql.SQL("CREATE ROLE {} {} {}")
        statements.append(
            Statement(
                Runner.ADMIN,
                create.format(identifier(role), _ROLE_ATTRIBUTES, sent),
                f"create role {role}",
                display=create.format(identifier(role), _ROLE_ATTRIBUTES, shown),
            )
        )
        statements.append(
            Statement(
                Runner.ADMIN,
                sql.SQL("COMMENT ON ROLE {} IS {}").format(
                    identifier(role), sql.Literal(names.marker(run_id))
                ),
                f"mark role {role}",
            )
        )
    statements.extend(membership_statements(names, admin))
    return statements


def membership_statements(names: Names, admin: str) -> list[Statement]:
    """Owner joins migrations; the admin may `SET ROLE` to the owner.

    Every option is stated so `INHERIT` and `NOINHERIT` admins get the same grant.
    """
    return [
        Statement(
            Runner.ADMIN,
            sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                identifier(names.migrations), identifier(names.owner)
            ),
            "grant migrations to owner",
        ),
        grant_owner_to_admin(names, admin),
    ]


def grant_owner_to_admin(names: Names, admin: str) -> Statement:
    """Let the admin `SET ROLE` to the owner without inheriting its privileges."""
    return Statement(
        Runner.ADMIN,
        sql.SQL("GRANT {} TO {} WITH SET TRUE, INHERIT FALSE").format(
            identifier(names.owner), identifier(admin)
        ),
        "grant owner to admin",
    )


def create_database_statement(names: Names) -> Statement:
    """`CREATE DATABASE` from `template0`, which is never modified."""
    return Statement(
        Runner.ADMIN,
        sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0").format(
            identifier(names.database), identifier(names.owner)
        ),
        f"create database {names.database}",
    )


def connect_statements(names: Names, admin: str) -> list[Statement]:
    """Grant `CONNECT` to the four roles and the admin, then close it to `PUBLIC`.

    The admin's own grant comes first so later connections can always open
    the database.
    """
    return [
        Statement(
            Runner.OWNER,
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                identifier(names.database), identifiers([*names.roles, admin])
            ),
            "grant connect",
        ),
        Statement(
            Runner.OWNER,
            sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(
                identifier(names.database)
            ),
            "revoke connect from public",
        ),
    ]


def revoke_owner_from_admin(names: Names, admin: str) -> Statement:
    """Give the owner role back, so the admin can manage it but not become it."""
    return Statement(
        Runner.ADMIN,
        sql.SQL("REVOKE {} FROM {}").format(identifier(names.owner), identifier(admin)),
        "revoke owner from admin",
    )
