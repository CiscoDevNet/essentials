"""`rotate` and `teardown`, which act only on what `create` built."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

import psycopg

from .connection import MAINTENANCE_DATABASE, Connector, ssl_description, url_sslmode
from .credentials import Delivery, LiveFlag, role_secrets, run_and_deliver
from .exceptions import PreflightError, ProvisioningError
from .interrupts import interrupts_ignored, sigterm_raises
from .naming import ROLE_KINDS, Names
from .options import RotateOptions, TeardownOptions
from .passwords import generate_role_passwords
from .preflight import (
    AdminFacts,
    DatabaseState,
    RoleState,
    acquire_lock,
    admin_facts,
    check_sinks,
    header,
    inspect_database,
    inspect_roles,
    require_signal_backend,
    require_version,
)
from .provision import recovery_command
from .sinks import (
    DeliveryReport,
    Outcome,
    SinkContext,
    build_failed_sinks,
    build_sinks,
    default_path,
    describe,
    display_path,
    env_names,
)
from .sql import Phase, Statement, catalog, execute, render, run_phase
from .sql.lifecycle import (
    allow_connections,
    drop_database,
    drop_roles,
    regrant_owner,
    restore_statements,
    rotate_statements,
)
from .ui import Ui

logger = logging.getLogger(__name__)

_TERMINATE_TIMEOUT_MS = 5000
_SAMPLE_LIMIT = 5


# === Provenance ===


def require_provenance(
    names: Names, roles: Mapping[str, RoleState], database: DatabaseState | None
) -> None:
    """Every role carries the marker with one run ID, and the owner owns the database.

    Raises:
        PreflightError: Naming the role or database that fails.
    """
    unmarked = [state.name for state in roles.values() if state.run_id is None]
    if unmarked:
        msg = (
            f"Refusing: {', '.join(unmarked)} exists but was not created by "
            "ess-postgres-provision (no marker). Inspect it by hand."
        )
        raise PreflightError(msg)
    run_ids = sorted({str(state.run_id) for state in roles.values()})
    if len(run_ids) > 1:
        msg = (
            f"Refusing: the roles for {names.base!r} come from different runs "
            f"({', '.join(run_ids)})."
        )
        raise PreflightError(msg)
    elevated = [
        f"{state.name} ({', '.join(state.cluster_attributes)})"
        for state in roles.values()
        if state.cluster_attributes
    ]
    if elevated:
        msg = f"Refusing: {', '.join(elevated)} holds cluster attributes."
        raise PreflightError(msg)
    if database is not None and database.owner != names.owner:
        msg = (
            f"Refusing: database {names.database} is owned by {database.owner}, "
            f"not {names.owner}."
        )
        raise PreflightError(msg)


# === Rotate ===


def rotate(
    connector: Connector, names: Names, options: RotateOptions, ui: Ui
) -> DeliveryReport | None:
    """Set new passwords for the chosen role kinds and deliver them.

    Returns:
        None for a dry run, otherwise where the new passwords went.

    Raises:
        PreflightError: A check refused; nothing was written.
        ProvisioningError: The change failed after it may have committed.
        DeliveryError: No sink received the new passwords.
    """
    target = connector.target
    kinds = list(dict.fromkeys(options.kinds))
    rotated_roles = ", ".join(names.role(kind) for kind in kinds)
    context = SinkContext(
        base=names.base,
        host=target.host,
        target=target.display,
        run_id=uuid4().hex,
        outcome=Outcome.ROTATED,
        timestamp=datetime.now(UTC),
        notes=(f"Rotated: {rotated_roles}",),
    )
    delivery = options.delivery
    sinks = build_sinks(delivery.sink_names, delivery.sink_paths, context)
    failed_sinks = build_failed_sinks(delivery.sink_names, delivery.sink_paths, context)

    with connector.connect(MAINTENANCE_DATABASE) as maintenance:
        acquire_lock(maintenance, names)
        facts = admin_facts(maintenance, ssl_description(maintenance))
        require_version(facts)
        _require_rotatable(maintenance, names, kinds)
        check_sinks([*sinks, *failed_sinks])
        passwords = generate_role_passwords(maintenance, names, kinds, delivery.digits)
        verifiers = {kind: password.verifier for kind, password in passwords.items()}
        phase = Phase(
            MAINTENANCE_DATABASE, rotate_statements(names, verifiers), transaction=True
        )
        rows = [("Will rotate:", rotated_roles), ("Credentials to:", describe(sinks))]
        ui.note(header(target, facts, names.base, rows))
        if ui.dry_run:
            ui.echo(render([phase], names.owner, facts.user))
            return None
        ui.confirm(f"Set new passwords for {len(kinds)} role(s) on {target.display}?")

        def work(flag: LiveFlag) -> None:
            run_phase(maintenance, phase, names.owner, before_commit=flag.mark)

        report = run_and_deliver(
            work,
            role_secrets(passwords, target, names, url_sslmode(maintenance, target)),
            Delivery(
                sinks=sinks,
                failed_sinks=failed_sinks,
                context=context,
                recovery=(
                    "the passwords may or may not have changed; rerun "
                    f"{recovery_command('rotate', target, names, _role_flags(kinds))}"
                ),
            ),
        )
    report.messages.append(_stale_note(names, kinds, context))
    return report


def _role_flags(kinds: Sequence[str]) -> list[str]:
    """`--role` per kind, or nothing when all four rotate, as they do by default."""
    if set(kinds) == set(ROLE_KINDS):
        return []
    return [flag for kind in kinds for flag in ("--role", kind)]


def _require_rotatable(
    conn: psycopg.Connection, names: Names, kinds: Sequence[str]
) -> None:
    roles = inspect_roles(conn, names)
    database = inspect_database(conn, names)
    if database is None:
        msg = f"Database {names.database} does not exist; run create first."
        raise PreflightError(msg)
    missing = [names.role(kind) for kind in kinds if kind not in roles]
    if missing:
        msg = (
            f"Cannot rotate {', '.join(missing)}: no such role. "
            "Run teardown, then create."
        )
        raise PreflightError(msg)
    require_provenance(names, {kind: roles[kind] for kind in kinds}, database)


def _stale_note(names: Names, kinds: Sequence[str], context: SinkContext) -> str:
    created = default_path(replace(context, outcome=Outcome.CREATED, path=None))
    variables = ", ".join(
        name for kind in kinds for name in env_names(names.base, kind)
    )
    where = display_path(created) if created.exists() else "earlier credential files"
    return f"Now stale in {where}: {variables}"


# === Teardown ===


def teardown(
    connector: Connector, names: Names, options: TeardownOptions, ui: Ui
) -> list[str]:
    """Drop what `create` built, from whatever state it left.

    Returns:
        One line per thing dropped; empty for a dry run or when nothing exists.

    Raises:
        PreflightError: A refusal: unmarked roles, a foreign owner, data,
            or open sessions.
        ProvisioningError: A drop failed. The database is left accepting
            connections.
    """
    with connector.connect(MAINTENANCE_DATABASE) as maintenance:
        acquire_lock(maintenance, names)
        facts = admin_facts(maintenance, ssl_description(maintenance))
        require_version(facts)
        roles = inspect_roles(maintenance, names)
        database = inspect_database(maintenance, names)
        require_provenance(names, roles, database)
        require_no_foreign_objects(maintenance, names, roles)
        if options.terminate_sessions:
            require_signal_backend(facts)
        if not roles and database is None:
            ui.note(f"Nothing to do: no database or roles for {names.base!r} exist.")
            return []

        run = _Teardown(maintenance, connector, names, facts.user, options)
        run.held = run.open_and_check(database)
        try:
            ui.note(_teardown_header(connector, facts, names, roles, database))
            if ui.dry_run:
                ui.echo(_render_teardown(names, facts.user, roles, database))
                return []
            ui.confirm(f"Drop everything listed above on {connector.target.display}?")
            dropped: list[str] = []
            with sigterm_raises():
                if database is not None:
                    run.drop_database()
                    dropped.append(f"database {names.database}")
                dropped.extend(run.drop_roles())
            return dropped
        finally:
            run.close_held()


@dataclass
class _Teardown:
    """Teardown's two connections: Connection 1 with the lock, and Connection T.

    From the re-grant until the drop succeeds, any failure, refusal, or
    interrupt restores connections and then gives the owner back.
    """

    maintenance: psycopg.Connection
    connector: Connector
    names: Names
    admin: str
    options: TeardownOptions
    held: psycopg.Connection | None = None

    def open_and_check(
        self, database: DatabaseState | None
    ) -> psycopg.Connection | None:
        """Step 1: open Connection T; refuse before changing anything if there is data.

        A database left blocked by an interrupted teardown cannot be opened
        yet; `drop_database` restores connections and checks it then.
        """
        if database is None or not database.allow_connections:
            return None
        held = self.connector.connect(self.names.database)
        try:
            require_empty(held, self.names)
        except BaseException:
            held.close()
            raise
        return held

    def drop_database(self) -> None:
        """Steps 2 to 6."""
        granted = dropped = False
        try:
            self._run(regrant_owner(self.names, self.admin))
            granted = True
            if self.held is None:
                self._run(allow_connections(self.names, allowed=True))
                self.held = self.connector.connect(self.names.database)
                require_empty(self.held, self.names)
            self._run(allow_connections(self.names, allowed=False))
            self._drain()
            require_empty(self.held, self.names)
            self.close_held()
            self._run(drop_database(self.names))
            dropped = True
        finally:
            self.close_held()
            if granted and not dropped:
                with interrupts_ignored():
                    self._restore()

    def drop_roles(self) -> list[str]:
        """Drop whichever derived roles remain."""
        present = inspect_roles(self.maintenance, self.names)
        order = [state.name for state in reversed(list(present.values()))]
        for statement in drop_roles(order):
            self._run(statement)
        return [f"role {role}" for role in order]

    def close_held(self) -> None:
        """Close Connection T; `DROP DATABASE` refuses while it is open."""
        if self.held is not None:
            self.held.close()
            self.held = None

    def _drain(self) -> None:
        """Step 4: refuse other sessions, or end them and refuse any that survive."""
        others = self._other_sessions()
        if not others:
            return
        if not self.options.terminate_sessions:
            msg = (
                f"Refusing: {len(others)} other session(s) are connected to "
                f"{self.names.database}. Close them, or pass --terminate-sessions."
            )
            raise PreflightError(msg)
        for pid in others:
            try:
                self.maintenance.execute(
                    catalog.TERMINATE_BACKEND,
                    {"pid": pid, "timeout_ms": _TERMINATE_TIMEOUT_MS},
                )
            except psycopg.Error as exc:
                msg = f"Could not end session {pid}: {exc.diag.message_primary}"
                raise ProvisioningError(msg) from exc
        survivors = self._other_sessions()
        if survivors:
            msg = (
                f"Refusing: session(s) {survivors} on {self.names.database} "
                "did not end."
            )
            raise PreflightError(msg)

    def _other_sessions(self) -> list[int]:
        held_pid = self.held.info.backend_pid if self.held is not None else 0
        rows = self.maintenance.execute(
            catalog.OTHER_SESSIONS,
            {"database": self.names.database, "exclude_pid": held_pid},
        ).fetchall()
        return [row.pid for row in rows]

    def _restore(self) -> None:
        """Restore connections, then give the owner back; stop if the first fails."""
        for statement in restore_statements(self.names, self.admin):
            try:
                self._run(statement)
            except ProvisioningError:
                logger.exception(
                    "Could not %s after a failed teardown", statement.purpose
                )
                return

    def _run(self, statement: Statement) -> None:
        execute(self.maintenance, statement, self.names.owner)


def require_empty(conn: psycopg.Connection, names: Names) -> None:
    """Refuse a database holding any relation or large object of its own.

    An extension's own relations are not data, except its configuration
    tables, which hold user rows: one counts once it has a row `pg_dump`
    would dump.

    Raises:
        PreflightError: Naming up to five relations found.
    """
    rows = conn.execute(catalog.SAMPLE_RELATIONS, {"limit": _SAMPLE_LIMIT}).fetchall()
    relations = [row.relation for row in rows]
    relations.extend(_extension_tables_with_rows(conn))
    large_objects = conn.execute(catalog.HAS_LARGE_OBJECTS).fetchone().found
    if not relations and not large_objects:
        return
    found = ", ".join(relations[:_SAMPLE_LIMIT]) if relations else "large objects"
    msg = (
        f"Refusing: database {names.database} holds data ({found}). Dropping a "
        "database with data is a deliberate manual step."
    )
    raise PreflightError(msg)


def _extension_tables_with_rows(conn: psycopg.Connection) -> list[str]:
    """Configuration tables with a row `pg_dump` would dump, or that cannot be read.

    With `row_security` off, a policy that would hide rows raises instead,
    so the table counts as unreadable rather than empty.
    """
    tables = conn.execute(catalog.EXTENSION_CONFIG_TABLES).fetchall()
    if tables:
        conn.execute("SET row_security = off")
    found: list[str] = []
    for table in tables:
        relation = f"{table.schema_name}.{table.table_name}"
        query = catalog.config_table_has_rows(
            table.schema_name, table.table_name, table.condition
        )
        try:
            has_rows = conn.execute(query).fetchone().found
        except psycopg.errors.InsufficientPrivilege:
            found.append(f"{relation} (unreadable)")
            continue
        if has_rows:
            found.append(relation)
    return found


def require_no_foreign_objects(
    conn: psycopg.Connection, names: Names, roles: Mapping[str, RoleState]
) -> None:
    """Refuse roles that own, or hold privileges on, anything outside the database.

    `DROP ROLE` would fail on them after the database is already gone.

    Raises:
        PreflightError: Naming the roles.
    """
    if not roles:
        return
    database = inspect_database(conn, names)
    database_oid = database.oid if database else None
    rows = conn.execute(
        catalog.ROLE_DEPENDENCIES, {"roles": [state.name for state in roles.values()]}
    ).fetchall()
    foreign = sorted(
        {
            row.rolname
            for row in rows
            if not _belongs_to(database_oid, row.dbid, row.class_name, row.objid)
        }
    )
    if foreign:
        msg = (
            f"Refusing: {', '.join(foreign)} own or hold privileges on objects "
            f"outside {names.database}. Reassign or drop them first."
        )
        raise PreflightError(msg)


def _belongs_to(
    database_oid: int | None, dbid: int, class_name: str, objid: int
) -> bool:
    """A dependency inside the database, or on the database itself."""
    if database_oid is None:
        return False
    return dbid == database_oid or (
        class_name == "pg_database" and objid == database_oid
    )


def _teardown_header(
    connector: Connector,
    facts: AdminFacts,
    names: Names,
    roles: Mapping[str, RoleState],
    database: DatabaseState | None,
) -> str:
    targets = [f"database {names.database}"] if database is not None else []
    targets.extend(state.name for state in roles.values())
    return header(
        connector.target, facts, names.base, [("Will drop:", ", ".join(targets))]
    )


def _render_teardown(
    names: Names,
    admin: str,
    roles: Mapping[str, RoleState],
    database: DatabaseState | None,
) -> str:
    statements: list[Statement] = []
    if database is not None:
        statements.extend(
            [
                regrant_owner(names, admin),
                allow_connections(names, allowed=False),
                drop_database(names),
            ]
        )
    statements.extend(
        drop_roles([state.name for state in reversed(list(roles.values()))])
    )
    text = render([Phase(MAINTENANCE_DATABASE, statements)], names.owner, admin)
    if database is None:
        return text
    return (
        f"{text}"
        "-- Before the drop: refuse other sessions (or end them with "
        "--terminate-sessions), then recheck for data.\n"
        "-- On any failure before the drop: restore connections, then revoke the "
        "owner from the admin.\n"
    )
