"""`create`: lock, preflight, write, verify, deliver."""

from __future__ import annotations

import logging
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import psycopg

from .connection import (
    MAINTENANCE_DATABASE,
    Connector,
    Target,
    ssl_description,
    url_sslmode,
)
from .credentials import Delivery, LiveFlag, role_secrets, run_and_deliver
from .exceptions import ProvisioningError
from .interrupts import interrupts_ignored
from .naming import ROLE_KINDS, Names
from .options import CreateOptions, VerifyOptions
from .passwords import RolePassword, generate_role_passwords
from .preflight import AdminFacts, acquire_lock, admin_facts, header, preflight_create
from .sinks import (
    DeliveryReport,
    Outcome,
    SinkContext,
    build_failed_sinks,
    build_sinks,
    describe,
)
from .sql import Phase, Statement, execute, render, run_phase
from .sql.database import database_statements
from .sql.maintenance import (
    connect_statements,
    create_database_statement,
    revoke_owner_from_admin,
    role_statements,
)
from .ui import Ui
from .verify import Check, render_table, require_passed, verify_catalog, verify_logins

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreateResult:
    """What a successful `create` produced."""

    report: DeliveryReport
    checks: list[Check]
    entropy_bits: float


def recovery_command(
    command: str, target: Target, names: Names, extra: Sequence[str] = ()
) -> str:
    """The exact command line to print for recovery, ending with `extra`."""
    return shlex.join(
        [
            "ess-postgres-provision",
            command,
            names.base,
            "--host",
            target.host,
            "--port",
            str(target.port),
            "--admin-user",
            target.admin_user,
            *extra,
        ]
    )


def create_phases(
    names: Names,
    admin: str,
    passwords: Mapping[str, RolePassword],
    run_id: str,
    in_database: Sequence[Statement],
) -> list[Phase]:
    """Every statement `create` sends, grouped by connection, in order.

    Args:
        names: The derived names.
        admin: The provisioning role.
        passwords: The generated password and verifier per role kind.
        run_id: The run ID stamped into every marker.
        in_database: Connection 2's statements, from `database_statements`.
    """
    verifiers = {kind: password.verifier for kind, password in passwords.items()}
    return [
        Phase(
            MAINTENANCE_DATABASE,
            role_statements(names, verifiers, run_id, admin),
            transaction=True,
        ),
        Phase(
            MAINTENANCE_DATABASE,
            [create_database_statement(names), *connect_statements(names, admin)],
        ),
        Phase(names.database, in_database),
        Phase(MAINTENANCE_DATABASE, [revoke_owner_from_admin(names, admin)]),
    ]


def create(
    connector: Connector, names: Names, options: CreateOptions, ui: Ui
) -> CreateResult | None:
    """Provision the database, schema, and four roles, then verify and deliver.

    Returns:
        None for a dry run, otherwise what was delivered and verified.

    Raises:
        PreflightError: A check refused; nothing was written.
        ProvisioningError: A write failed. Credentials were still delivered
            if they may be live.
        VerificationError: The result does not match the design.
        DeliveryError: No sink received the credentials.
    """
    target = connector.target
    context = SinkContext(
        base=names.base,
        host=target.host,
        target=target.display,
        run_id=uuid4().hex,
        outcome=Outcome.CREATED,
        timestamp=datetime.now(UTC),
    )
    delivery_options = options.delivery
    sinks = build_sinks(
        delivery_options.sink_names, delivery_options.sink_paths, context
    )
    failed_sinks = build_failed_sinks(
        delivery_options.sink_names, delivery_options.sink_paths, context
    )

    with connector.connect(MAINTENANCE_DATABASE) as maintenance:
        acquire_lock(maintenance, names)
        facts = admin_facts(maintenance, ssl_description(maintenance))
        extensions = preflight_create(
            maintenance, names, facts, options, [*sinks, *failed_sinks]
        )
        passwords = generate_role_passwords(
            maintenance, names, ROLE_KINDS, delivery_options.digits
        )
        phases = create_phases(
            names,
            facts.user,
            passwords,
            context.run_id,
            database_statements(names, extensions, options.guards),
        )
        ui.note(_create_header(target, facts, names, describe(sinks)))
        if ui.dry_run:
            ui.echo(render(phases, names.owner, facts.user))
            return None
        ui.confirm(
            f"Create database {names.database}, schema {names.schema}, and four "
            f"roles on {target.display}?"
        )

        checks: list[Check] = []
        verify_options = VerifyOptions(options.extensions, options.guards.read_only)

        def work(flag: LiveFlag) -> None:
            _run_phases(connector, maintenance, phases, names.owner, flag)
            checks.extend(_verify_new(connector, names, passwords, verify_options))
            ui.echo(render_table(checks))
            require_passed(checks)

        report = run_and_deliver(
            work,
            role_secrets(passwords, target, names, url_sslmode(maintenance, target)),
            Delivery(
                sinks=sinks,
                failed_sinks=failed_sinks,
                context=context,
                recovery=(
                    f"{recovery_command('teardown', target, names)}, then rerun create"
                ),
            ),
        )
    entropy = min(password.entropy_bits for password in passwords.values())
    return CreateResult(report, checks, entropy)


def _create_header(
    target: Target, facts: AdminFacts, names: Names, destinations: str
) -> str:
    return header(
        target,
        facts,
        names.base,
        [("Will create:", ", ".join(names.roles)), ("Credentials to:", destinations)],
    )


def _run_phases(
    connector: Connector,
    maintenance: psycopg.Connection,
    phases: Sequence[Phase],
    owner: str,
    flag: LiveFlag,
) -> None:
    """Run each phase in order; the last, on Connection 1, gives the owner back.

    Once the roles may exist, the owner is given back even when an earlier
    phase fails, so a failed run never leaves the admin able to become it.
    """
    *steps, give_back = phases
    try:
        _run_steps(connector, maintenance, steps, owner, flag)
    except BaseException:
        if flag.may_be_live:
            _give_back_after_failure(maintenance, give_back, owner)
        raise
    run_phase(maintenance, give_back, owner)


def _give_back_after_failure(
    maintenance: psycopg.Connection, give_back: Phase, owner: str
) -> None:
    with interrupts_ignored():
        for statement in give_back.statements:
            try:
                execute(maintenance, statement, owner)
            except ProvisioningError:
                logger.exception(
                    "Could not %s after a failed create", statement.purpose
                )


def _run_steps(
    connector: Connector,
    maintenance: psycopg.Connection,
    phases: Sequence[Phase],
    owner: str,
    flag: LiveFlag,
) -> None:
    """Run each phase on its connection; close Connection 2 before returning to 1."""
    database_conn: psycopg.Connection | None = None
    try:
        for phase in phases:
            if phase.database == MAINTENANCE_DATABASE:
                if database_conn is not None:
                    database_conn.close()
                    database_conn = None
                conn = maintenance
            else:
                database_conn = database_conn or connector.connect(phase.database)
                conn = database_conn
            run_phase(
                conn,
                phase,
                owner,
                before_commit=flag.mark if phase.transaction else None,
            )
    finally:
        if database_conn is not None:
            database_conn.close()


def _verify_new(
    connector: Connector,
    names: Names,
    passwords: Mapping[str, RolePassword],
    options: VerifyOptions,
) -> list[Check]:
    with connector.connect(names.database) as conn:
        checks = verify_catalog(conn, names, options)
    plaintext = {kind: password.password for kind, password in passwords.items()}
    checks.extend(verify_logins(connector, names, plaintext, options))
    return checks
