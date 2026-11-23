"""Read-only checks, the advisory lock, and the header every write prints.

Nothing here writes. Every check raises `PreflightError` (exit 3).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

import psycopg

from .connection import Target
from .exceptions import PreflightError
from .naming import ROLE_KINDS, Names
from .options import CreateOptions
from .sinks import SecretSink
from .sql import catalog
from .sql.database import Extension, ReaderGuards

MIN_SERVER_VERSION = 160000

_MANAGED_SUPERUSER_ROLES = ["rds_superuser", "azure_pg_admin", "cloudsqlsuperuser"]


# === The lock ===


def lock_key(base: str) -> int:
    """A stable 64-bit advisory lock key, never Python's salted `hash()`."""
    digest = hashlib.sha256(f"ess-postgres-provision:{base}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def acquire_lock(conn: psycopg.Connection, names: Names) -> None:
    """Take the session advisory lock for `names.base` on Connection 1.

    Held until the connection closes, so a second run fails at once.

    Raises:
        PreflightError: Another run holds the lock.
    """
    row = conn.execute(
        catalog.TRY_ADVISORY_LOCK, {"key": lock_key(names.base)}
    ).fetchone()
    if not row or not row.acquired:
        msg = (
            f"Another run is provisioning {names.base!r} on this server. Wait for "
            "it to finish, then retry."
        )
        raise PreflightError(msg)


# === The admin ===


@dataclass(frozen=True)
class AdminFacts:
    """What the provisioning role can do, as resolved from the server."""

    user: str
    superuser: bool
    createdb: bool
    createrole: bool
    managed_superuser: bool
    signal_backend: bool
    server_version: int
    server_version_text: str
    ssl: str
    createrole_self_grant: str


def admin_facts(conn: psycopg.Connection, ssl: str) -> AdminFacts:
    """Read the admin's attributes and the server version."""
    row = conn.execute(
        catalog.ADMIN_FACTS, {"managed_superusers": _MANAGED_SUPERUSER_ROLES}
    ).fetchone()
    if row is None:
        msg = "Could not read the connecting role from pg_roles."
        raise PreflightError(msg)
    return AdminFacts(
        user=row.rolname,
        superuser=row.rolsuper,
        createdb=row.rolcreatedb,
        createrole=row.rolcreaterole,
        managed_superuser=row.managed_superuser,
        signal_backend=row.rolsuper or row.signal_backend,
        server_version=conn.info.server_version,
        server_version_text=row.server_version,
        ssl=ssl,
        createrole_self_grant=row.createrole_self_grant,
    )


def require_capability(facts: AdminFacts) -> None:
    """Superuser, or both `CREATEDB` and `CREATEROLE`."""
    if facts.superuser or (facts.createdb and facts.createrole):
        return
    msg = (
        f"{facts.user!r} needs SUPERUSER, or both CREATEDB and CREATEROLE "
        f"(createdb: {_yes_no(facts.createdb)}, "
        f"createrole: {_yes_no(facts.createrole)})."
    )
    raise PreflightError(msg)


def require_version(facts: AdminFacts) -> None:
    """PostgreSQL 16 or later; membership grants rely on 16's `SET` and `INHERIT`."""
    if facts.server_version >= MIN_SERVER_VERSION:
        return
    msg = (
        "PostgreSQL 16 or later is required; this server runs "
        f"{facts.server_version_text}."
    )
    raise PreflightError(msg)


def neutralize_self_grant(conn: psycopg.Connection, facts: AdminFacts) -> None:
    """Stop a `CREATEROLE` admin silently gaining `INHERIT` or `SET` on new roles."""
    if facts.createrole_self_grant:
        conn.execute("SET createrole_self_grant = ''")


# === The target ===


@dataclass(frozen=True)
class RoleState:
    """One existing derived role, as found in the catalog."""

    kind: str
    name: str
    can_login: bool
    cluster_attributes: tuple[str, ...]
    run_id: str | None


@dataclass(frozen=True)
class DatabaseState:
    """The existing database, as found in the catalog."""

    oid: int
    owner: str
    allow_connections: bool
    public_connect: bool


def inspect_roles(conn: psycopg.Connection, names: Names) -> dict[str, RoleState]:
    """The derived roles that exist, by kind."""
    rows = conn.execute(catalog.ROLES, {"roles": list(names.roles)}).fetchall()
    found: dict[str, RoleState] = {}
    for row in rows:
        kind = names.kind_of(row.rolname)
        held = {
            "SUPERUSER": row.rolsuper,
            "CREATEDB": row.rolcreatedb,
            "CREATEROLE": row.rolcreaterole,
            "REPLICATION": row.rolreplication,
            "BYPASSRLS": row.rolbypassrls,
        }
        found[kind] = RoleState(
            kind=kind,
            name=row.rolname,
            can_login=row.rolcanlogin,
            cluster_attributes=tuple(name for name, has in held.items() if has),
            run_id=names.run_id_from_marker(row.marker),
        )
    return {kind: found[kind] for kind in ROLE_KINDS if kind in found}


def inspect_database(conn: psycopg.Connection, names: Names) -> DatabaseState | None:
    """The database's owner, `datallowconn`, and `PUBLIC` `CONNECT`, or None."""
    row = conn.execute(catalog.DATABASE, {"database": names.database}).fetchone()
    if row is None:
        return None
    return DatabaseState(
        oid=row.oid,
        owner=row.owner,
        allow_connections=row.datallowconn,
        public_connect=row.public_connect,
    )


def require_nothing_exists(conn: psycopg.Connection, names: Names) -> None:
    """Refuse an existing database or role; `create` never adopts one."""
    found: list[str] = []
    if inspect_database(conn, names) is not None:
        found.append(f"database {names.database}")
    found.extend(f"role {state.name}" for state in inspect_roles(conn, names).values())
    if found:
        msg = (
            f"Already exists: {', '.join(found)}. create never reuses an existing "
            f"database or role. If an earlier run left these, run "
            f"`ess-postgres-provision teardown {names.base}` first."
        )
        raise PreflightError(msg)


def require_template0_utf8(conn: psycopg.Connection) -> None:
    """The new database copies `template0`, so it must be `UTF8`."""
    row = conn.execute(catalog.TEMPLATE0_ENCODING).fetchone()
    if not row or row.encoding != "UTF8":
        found = row.encoding if row else "missing"
        msg = f"template0 must use UTF8 encoding; found {found}."
        raise PreflightError(msg)


def resolve_extensions(
    conn: psycopg.Connection, requested: Sequence[str], facts: AdminFacts
) -> list[Extension]:
    """Check each requested extension is available and installable by this admin.

    Raises:
        PreflightError: An extension is unavailable, or untrusted and the
            admin is neither a superuser nor a managed-service superuser.
    """
    extensions: list[Extension] = []
    for name in dict.fromkeys(requested):
        row = conn.execute(catalog.EXTENSION_TRUSTED, {"name": name}).fetchone()
        if row is None:
            msg = f"Extension {name!r} is not available on this server."
            raise PreflightError(msg)
        trusted = bool(row.trusted)
        if not trusted and not (facts.superuser or facts.managed_superuser):
            msg = (
                f"Extension {name!r} is not trusted, so it needs a superuser or a "
                f"member of {', '.join(_MANAGED_SUPERUSER_ROLES)}; {facts.user!r} "
                "is neither."
            )
            raise PreflightError(msg)
        extensions.append(Extension(name, trusted))
    return extensions


def validate_reader_guards(conn: psycopg.Connection, guards: ReaderGuards) -> None:
    """Let the server parse each guardrail value, then roll the settings back."""
    for setting, value in guards.settings():
        try:
            with conn.transaction(force_rollback=True):
                conn.execute(
                    catalog.VALIDATE_SETTING, {"setting": setting, "value": value}
                )
        except psycopg.Error as exc:
            msg = f"Invalid value {value!r} for {setting}: {exc.diag.message_primary}"
            raise PreflightError(msg) from exc


def check_sinks(sinks: Sequence[SecretSink]) -> None:
    """Run each sink's own preflight."""
    for sink in sinks:
        sink.check()


def require_signal_backend(facts: AdminFacts) -> None:
    """`--terminate-sessions` needs superuser or `pg_signal_backend`."""
    if facts.signal_backend:
        return
    msg = (
        f"--terminate-sessions needs SUPERUSER or membership in pg_signal_backend; "
        f"{facts.user!r} has neither."
    )
    raise PreflightError(msg)


def preflight_create(
    conn: psycopg.Connection,
    names: Names,
    facts: AdminFacts,
    options: CreateOptions,
    sinks: Sequence[SecretSink],
) -> list[Extension]:
    """Every `create` check after the lock, in order, before any write.

    Returns:
        The requested extensions, each marked trusted or not.
    """
    require_capability(facts)
    require_version(facts)
    require_nothing_exists(conn, names)
    require_template0_utf8(conn)
    extensions = resolve_extensions(conn, options.extensions, facts)
    validate_reader_guards(conn, options.guards)
    check_sinks(sinks)
    neutralize_self_grant(conn, facts)
    return extensions


# === The header ===


def header(
    target: Target, facts: AdminFacts, base: str, rows: Sequence[tuple[str, str]]
) -> str:
    """The block shown by a dry run and before the confirmation prompt."""
    attributes = (
        f"superuser: {_yes_no(facts.superuser)}, createdb: {_yes_no(facts.createdb)}, "
        f"createrole: {_yes_no(facts.createrole)}"
    )
    ssl = facts.ssl if facts.ssl != "off" or not target.is_local else "off (local)"
    lines = [
        ("Connecting as:", f"{facts.user}  ({attributes})"),
        ("Target:", f"{base} @ {target.display}  (SSL: {ssl})"),
        *rows,
    ]
    width = max(len(label) for label, _ in lines) + 2
    return "\n".join(f"{label:<{width}}{value}" for label, value in lines)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
