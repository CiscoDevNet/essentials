"""Check the catalog, and optionally each role's login, against the design.

Neither a missing `FOR ROLE` nor a per-schema function revoke raises an
error, so a run that exits 0 proves nothing until these checks pass.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import NamedTuple

import psycopg

from .connection import MAINTENANCE_DATABASE, Connector
from .exceptions import PreflightError, VerificationError
from .naming import Names
from .options import VerifyOptions
from .preflight import inspect_database, inspect_roles
from .sql import catalog

_SYSTEM_SCHEMAS = ["pg_catalog", "information_schema"]
_CHECKED_RELKINDS = ["r", "p", "v", "m", "f"]


@dataclass(frozen=True)
class Check:
    """One row of the verification table.

    Attributes:
        name: What was checked.
        passed: Whether it matched.
        detail: What was found, when it did not match or is worth noting.
        informational: Listed for review; never fails the run.
    """

    name: str
    passed: bool
    detail: str = ""
    informational: bool = False


def failures(checks: list[Check]) -> list[Check]:
    """The checks that fail the run."""
    return [check for check in checks if not check.passed and not check.informational]


def require_passed(checks: list[Check]) -> None:
    """Raise if any non-informational check failed.

    Raises:
        VerificationError: Naming each failed check.
    """
    failed = failures(checks)
    if failed:
        listed = "; ".join(f"{check.name}: {check.detail}" for check in failed)
        msg = f"Verification failed: {listed}"
        raise VerificationError(msg)


def render_table(checks: list[Check]) -> str:
    """The verification table, one check per line."""
    width = max(len(check.name) for check in checks) + 2
    lines = [f"{'Check':<{width}}Result", f"{'-' * (width - 2):<{width}}------"]
    for check in checks:
        result = "info" if check.informational else ("pass" if check.passed else "FAIL")
        detail = f"  {check.detail}" if check.detail else ""
        lines.append(f"{check.name:<{width}}{result}{detail}")
    return "\n".join(lines)


type _Runner = Callable[[psycopg.Connection, Names, VerifyOptions], list[Check]]


def verify(connector: Connector, names: Names, options: VerifyOptions) -> list[Check]:
    """The `verify` subcommand: every catalog check, as the admin.

    A database whose connections are blocked, as an interrupted teardown
    leaves it, still gets the checks that read shared catalogs.

    Raises:
        VerificationError: The database does not exist.
    """
    with connector.connect(MAINTENANCE_DATABASE) as maintenance:
        database = inspect_database(maintenance, names)
        if database is None:
            msg = f"Database {names.database} does not exist."
            raise VerificationError(msg)
        if not database.allow_connections:
            checks = _run_checks(maintenance, names, options, _SHARED_CHECKS)
            checks.append(
                Check(
                    "per-database checks",
                    passed=False,
                    detail="skipped: connections are blocked; rerun teardown to finish",
                )
            )
            return checks
    with connector.connect(names.database) as conn:
        return verify_catalog(conn, names, options)


def verify_catalog(
    conn: psycopg.Connection, names: Names, options: VerifyOptions
) -> list[Check]:
    """Every catalog check, run as the admin on a connection to the new database."""
    return _run_checks(conn, names, options, [*_SHARED_CHECKS, *_LOCAL_CHECKS])


def _run_checks(
    conn: psycopg.Connection,
    names: Names,
    options: VerifyOptions,
    runners: list[_Runner],
) -> list[Check]:
    checks: list[Check] = []
    for runner in runners:
        checks.extend(runner(conn, names, options))
    return checks


def verify_logins(
    connector: Connector,
    names: Names,
    passwords: Mapping[str, str],
    options: VerifyOptions,
) -> list[Check]:
    """Log in as each role with its new password and read its session settings."""
    expected_path = f"{names.schema}, public"
    checks: list[Check] = []
    for kind, password in passwords.items():
        role = names.role(kind)
        name = f"{role} logs in"
        try:
            conn = connector.connect_as(role, password, names.database)
        except PreflightError as exc:
            checks.append(Check(name, passed=False, detail=str(exc)))
            continue
        with conn:
            row = conn.execute(catalog.SESSION_SETTINGS).fetchone()
        problems: list[str] = []
        if row.role != role:
            problems.append(f"connected as {row.role}")
        if row.search_path.replace('"', "") != expected_path:
            problems.append(f"search_path is {row.search_path!r}")
        if kind == "reader" and options.reader_read_only and row.read_only != "on":
            problems.append("default_transaction_read_only is off")
        checks.append(Check(name, passed=not problems, detail="; ".join(problems)))
    return checks


# === Roles ===


def _check_roles(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    states = list(inspect_roles(conn, names).values())
    present = {state.name for state in states}
    missing = [role for role in names.roles if role not in present]
    no_login = [state.name for state in states if not state.can_login]
    attributes = [state.name for state in states if state.cluster_attributes]
    run_ids = {state.run_id for state in states}
    unmarked = [state.name for state in states if state.run_id is None]
    return [
        Check(
            "all four roles exist and can log in",
            passed=not missing and not no_login,
            detail=_join("missing", missing) + _join("no LOGIN", no_login),
        ),
        Check(
            "no role has a cluster attribute",
            passed=not attributes,
            detail=_join("has one", attributes),
        ),
        Check(
            "every role carries the marker, one run ID",
            passed=not unmarked and len(run_ids) == 1,
            detail=_join("unmarked", unmarked)
            or ("" if len(run_ids) <= 1 else "roles come from different runs"),
        ),
    ]


def _check_memberships(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    rows = conn.execute(catalog.MEMBERSHIPS, {"roles": list(names.roles)}).fetchall()
    unexpected = [
        row
        for row in rows
        if not _is_owner_in_migrations(row, names)
        and not _is_admin_only_grant(row, names)
    ]
    has_expected = any(_is_owner_in_migrations(row, names) for row in rows)
    detail = "; ".join(
        f"{row.member} in {row.role} (admin {row.admin_option}, "
        f"inherit {row.inherit_option}, set {row.set_option})"
        for row in unexpected
    )
    if not has_expected:
        detail = "owner is not a member of migrations with INHERIT and SET" + (
            f"; {detail}" if detail else ""
        )
    return [
        Check(
            "memberships: owner in migrations, nothing else",
            passed=has_expected and not unexpected,
            detail=detail,
        )
    ]


def _is_owner_in_migrations(row: NamedTuple, names: Names) -> bool:
    """The one membership the design creates: owner in migrations, with INHERIT, SET."""
    return (
        row.role == names.migrations
        and row.member == names.owner
        and not row.admin_option
        and row.inherit_option
        and row.set_option
    )


def _is_admin_only_grant(row: NamedTuple, names: Names) -> bool:
    """A `CREATEROLE` admin's automatic grant: it can manage the role, not become it."""
    return (
        row.role in names.roles
        and row.member not in names.roles
        and row.admin_option
        and not (row.inherit_option or row.set_option)
    )


# === Database and schema ===


def _check_database(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    database = inspect_database(conn, names)
    if database is None:
        return [Check("database exists", passed=False, detail="missing")]
    owner = database.owner
    return [
        Check(
            "database owned by the owner role",
            passed=owner == names.owner,
            detail="" if owner == names.owner else f"owned by {owner}",
        ),
        Check(
            "PUBLIC has no CONNECT; connections allowed",
            passed=not database.public_connect and database.allow_connections,
            detail=("PUBLIC can connect; " if database.public_connect else "")
            + ("" if database.allow_connections else "datallowconn is false"),
        ),
    ]


def _check_schema_owner(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    row = conn.execute(catalog.SCHEMA_OWNER, {"schema": names.schema}).fetchone()
    owner = row.owner if row else None
    detail = (
        "" if owner == names.owner else (f"owned by {owner}" if owner else "missing")
    )
    return [Check("schema owned by the owner role", owner == names.owner, detail)]


def _check_schema_privileges(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    expected = [
        (names.migrations, names.schema, "USAGE", True),
        (names.migrations, names.schema, "CREATE", True),
        (names.app, names.schema, "USAGE", True),
        (names.app, names.schema, "CREATE", False),
        (names.reader, names.schema, "USAGE", True),
        (names.reader, names.schema, "CREATE", False),
        (names.migrations, "public", "CREATE", False),
        (names.app, "public", "CREATE", False),
        (names.reader, "public", "CREATE", False),
    ]
    missing = [
        *_missing_roles(conn, names, [role for role, *_ in expected]),
        *_missing_schemas(conn, [schema for _, schema, *_ in expected]),
    ]
    if missing:
        return [Check("schema privileges", passed=False, detail=_cannot_check(missing))]
    wrong: list[str] = []
    for role, schema, privilege, should_have in expected:
        row = conn.execute(
            catalog.SCHEMA_PRIVILEGE,
            {"role": role, "schema": schema, "privilege": privilege},
        ).fetchone()
        if row.held != should_have:
            verb = "lacks" if should_have else "has"
            wrong.append(f"{role} {verb} {privilege} on {schema}")
    return [Check("schema privileges", passed=not wrong, detail="; ".join(wrong))]


def _check_role_settings(
    conn: psycopg.Connection, names: Names, options: VerifyOptions
) -> list[Check]:
    quoted = conn.execute(catalog.QUOTE_IDENT, {"name": names.schema}).fetchone().quoted
    expected_path = f"search_path={quoted}, public"
    rows = conn.execute(
        catalog.ROLE_SETTINGS,
        {"database": names.database, "roles": list(names.roles)},
    ).fetchall()
    settings = {row.rolname: set(row.setconfig or []) for row in rows}
    missing = [
        role for role in names.roles if expected_path not in settings.get(role, set())
    ]
    checks = [
        Check(
            "search_path set for all four, in this database",
            passed=not missing,
            detail=_join("missing", missing),
        )
    ]
    if options.reader_read_only:
        read_only = "default_transaction_read_only=on" in settings.get(
            names.reader, set()
        )
        checks.append(
            Check(
                "reader defaults to read-only",
                passed=read_only,
                detail="" if read_only else "default_transaction_read_only is not on",
            )
        )
    return checks


# === Default privileges ===


def _check_default_privileges(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    rows = conn.execute(
        catalog.DEFAULT_PRIVILEGES, {"role": names.migrations}
    ).fetchall()
    actual: dict[tuple[str, str], dict[str, set[str]]] = {}
    for row in rows:
        grants = actual.setdefault((row.schema_name, row.object_type), {})
        if row.grantee != names.migrations:
            grants.setdefault(row.grantee, set()).add(row.privilege_type)
    expected = {
        (names.schema, "r"): {
            names.app: {"SELECT", "INSERT", "UPDATE", "DELETE"},
            names.reader: {"SELECT"},
        },
        (names.schema, "S"): {names.app: {"USAGE", "SELECT"}},
        ("", "f"): {},
        (names.schema, "f"): {names.app: {"EXECUTE"}},
    }
    problems: list[str] = []
    if ("", "f") not in actual:
        problems.append(
            "no global function row: the PUBLIC revoke may have been written "
            "with IN SCHEMA"
        )
    for key in sorted(set(actual) | set(expected)):
        if key == ("", "f") and key not in actual:
            continue
        if actual.get(key) != expected.get(key):
            label = f"{key[0] or 'global'}/{key[1]}"
            problems.append(
                f"{label}: found {actual.get(key)}, expected {expected.get(key)}"
            )
    return [
        Check(
            "default privileges for migrations' objects",
            not problems,
            "; ".join(problems),
        )
    ]


# === Extensions, tables, and functions ===


def _check_extensions(
    conn: psycopg.Connection, _names: Names, options: VerifyOptions
) -> list[Check]:
    if not options.extensions:
        return []
    rows = conn.execute(
        catalog.INSTALLED_EXTENSIONS, {"names": list(options.extensions)}
    ).fetchall()
    installed = {row.extname for row in rows}
    missing = [name for name in options.extensions if name not in installed]
    return [
        Check("requested extensions installed", not missing, _join("missing", missing))
    ]


def _check_tables(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    reader_name = "reader cannot write any table"
    app_name = "app cannot truncate any table"
    missing = _missing_roles(conn, names, [names.reader, names.app])
    if missing:
        detail = _cannot_check(missing)
        return [Check(reader_name, False, detail), Check(app_name, False, detail)]
    rows = conn.execute(
        catalog.TABLE_PRIVILEGES,
        {
            "reader": names.reader,
            "app": names.app,
            "schema": names.schema,
            "relkinds": _CHECKED_RELKINDS,
        },
    ).fetchall()
    reader_writes = [row.relation for row in rows if row.reader_writes]
    app_truncates = [row.relation for row in rows if row.app_truncates]
    return [
        Check(reader_name, not reader_writes, _join("writable", reader_writes)),
        Check(app_name, not app_truncates, _join("truncatable", app_truncates)),
    ]


def _check_functions(
    conn: psycopg.Connection, names: Names, _: VerifyOptions
) -> list[Check]:
    public_rows = conn.execute(
        catalog.PUBLIC_EXECUTABLE_FUNCTIONS, {"schema": names.schema}
    ).fetchall()
    definer_rows = (
        []
        if _missing_roles(conn, names, [names.reader])
        else conn.execute(
            catalog.DEFINER_FUNCTIONS_EXECUTABLE_BY,
            {"system_schemas": _SYSTEM_SCHEMAS, "role": names.reader},
        ).fetchall()
    )
    public = [row.signature for row in public_rows]
    definers = [row.signature for row in definer_rows]
    checks = [
        Check(
            f"no function in {names.schema} executable by PUBLIC",
            not public,
            _join("executable", public),
        )
    ]
    if definers:
        checks.append(
            Check(
                "SECURITY DEFINER functions the reader can run",
                passed=True,
                detail=", ".join(definers),
                informational=True,
            )
        )
    return checks


def _join(label: str, items: list[str]) -> str:
    return f"{label}: {', '.join(items)}. " if items else ""


def _missing_roles(
    conn: psycopg.Connection, names: Names, roles: list[str]
) -> list[str]:
    """The roles that do not exist; privilege functions raise on them."""
    present = {state.name for state in inspect_roles(conn, names).values()}
    return [role for role in dict.fromkeys(roles) if role not in present]


def _missing_schemas(conn: psycopg.Connection, schemas: list[str]) -> list[str]:
    """The schemas that do not exist; privilege functions raise on them."""
    wanted = list(dict.fromkeys(schemas))
    rows = conn.execute(catalog.EXISTING_SCHEMAS, {"schemas": wanted}).fetchall()
    present = {row.nspname for row in rows}
    return [f"schema {schema}" for schema in wanted if schema not in present]


def _cannot_check(missing: list[str]) -> str:
    return f"skipped: {', '.join(missing)} missing"


# Shared catalogs read the same from any database; the rest need the new one.
_SHARED_CHECKS: list[_Runner] = [
    _check_roles,
    _check_memberships,
    _check_database,
    _check_role_settings,
]
_LOCAL_CHECKS: list[_Runner] = [
    _check_schema_owner,
    _check_schema_privileges,
    _check_default_privileges,
    _check_extensions,
    _check_tables,
    _check_functions,
]
