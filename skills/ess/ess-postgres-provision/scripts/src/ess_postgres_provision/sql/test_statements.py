"""Who runs each statement, in what order, and what a dry run shows."""

import psycopg
import pytest

from ess_postgres_provision.conftest import ADMIN, RUN_ID, FakeServer
from ess_postgres_provision.exceptions import ProvisioningError
from ess_postgres_provision.naming import ROLE_KINDS, derive_names
from ess_postgres_provision.sql import (
    REDACTED,
    Phase,
    Runner,
    Statement,
    execute,
    render,
)
from ess_postgres_provision.sql.database import (
    Extension,
    ReaderGuards,
    database_statements,
    default_privilege_statements,
)
from ess_postgres_provision.sql.lifecycle import (
    allow_connections,
    drop_database,
    drop_roles,
    regrant_owner,
    restore_statements,
    rotate_statements,
)
from ess_postgres_provision.sql.maintenance import (
    connect_statements,
    create_database_statement,
    revoke_owner_from_admin,
    role_statements,
)

_NAMES = derive_names("billing")
_VERIFIER = "SCRAM-SHA-256$4096:c2FsdA==$c3RvcmVkS2V5:c2VydmVyS2V5"
_VERIFIERS = dict.fromkeys(ROLE_KINDS, _VERIFIER)
_EXTENSIONS = [Extension("pg_trgm", trusted=True), Extension("vector", trusted=False)]

_A = Runner.ADMIN
_O = Runner.OWNER

# The runner table from the design, one row per statement `create` sends.
_CREATE_RUNNERS = {
    **{f"create role billing_{kind}": _A for kind in ROLE_KINDS},
    **{f"mark role billing_{kind}": _A for kind in ROLE_KINDS},
    "grant migrations to owner": _A,
    "grant owner to admin": _A,
    "create database billing": _A,
    "grant connect": _O,
    "revoke connect from public": _O,
    "create schema billing": _O,
    "revoke create on public": _O,
    "create extension pg_trgm in billing": _O,
    "create extension vector in billing": _A,
    "grant schema to migrations": _O,
    "grant schema usage to app and reader": _O,
    **{f"set search_path for billing_{kind}": _A for kind in ROLE_KINDS},
    "default privileges: app tables": _O,
    "default privileges: reader tables": _O,
    "default privileges: app sequences": _O,
    "default privileges: functions from public": _O,
    "default privileges: app functions": _O,
    "set default_transaction_read_only for billing_reader": _A,
    "set idle_in_transaction_session_timeout for billing_reader": _A,
    "set statement_timeout for billing_reader": _A,
    "revoke owner from admin": _A,
}


def _create_statements() -> list[Statement]:
    return [
        *role_statements(_NAMES, _VERIFIERS, RUN_ID, ADMIN),
        create_database_statement(_NAMES),
        *connect_statements(_NAMES, ADMIN),
        *database_statements(_NAMES, _EXTENSIONS, ReaderGuards()),
        revoke_owner_from_admin(_NAMES, ADMIN),
    ]


def _purposes(statements: list[Statement]) -> list[str]:
    return [statement.purpose for statement in statements]


def test_create_statements_match_the_runner_table() -> None:
    runners = {s.purpose: s.runner for s in _create_statements()}

    assert runners == _CREATE_RUNNERS


def test_teardown_and_rotate_statements_match_the_runner_table() -> None:
    statements = [
        *rotate_statements(_NAMES, _VERIFIERS),
        regrant_owner(_NAMES, ADMIN),
        allow_connections(_NAMES, allowed=False),
        drop_database(_NAMES),
        *drop_roles(list(_NAMES.roles)),
    ]
    runners = {s.purpose: s.runner for s in statements}

    assert runners == {
        **{f"rotate password for billing_{kind}": _A for kind in ROLE_KINDS},
        "grant owner to admin": _A,
        "block connections": _O,
        "drop database billing": _O,
        **{f"drop role billing_{kind}": _A for kind in ROLE_KINDS},
    }


def test_every_role_is_marked_with_the_run_id_inside_the_role_transaction() -> None:
    statements = role_statements(_NAMES, _VERIFIERS, RUN_ID, ADMIN)
    marks = [s.query.as_string() for s in statements if s.purpose.startswith("mark")]

    marker = f"'ess-postgres-provision:billing:{RUN_ID}'"
    assert marks == [
        f'COMMENT ON ROLE "billing_{kind}" IS {marker}' for kind in ROLE_KINDS
    ]
    assert _purposes(statements)[-2:] == [
        "grant migrations to owner",
        "grant owner to admin",
    ]


def test_membership_grants_state_every_option() -> None:
    statements = role_statements(_NAMES, _VERIFIERS, RUN_ID, ADMIN)
    grants = [s.query.as_string() for s in statements[-2:]]

    assert grants == [
        'GRANT "billing_migrations" TO "billing_owner" WITH INHERIT TRUE, SET TRUE',
        f'GRANT "billing_owner" TO "{ADMIN}" WITH SET TRUE, INHERIT FALSE',
    ]


def test_admin_connect_is_granted_before_public_is_revoked() -> None:
    grant, revoke = connect_statements(_NAMES, ADMIN)

    assert f'"{ADMIN}"' in grant.query.as_string()
    assert (
        revoke.query.as_string() == 'REVOKE CONNECT ON DATABASE "billing" FROM PUBLIC'
    )


def test_database_is_copied_from_template0() -> None:
    statement = create_database_statement(_NAMES)

    assert statement.query.as_string() == (
        'CREATE DATABASE "billing" OWNER "billing_owner" TEMPLATE template0'
    )


def test_function_revoke_is_global_and_every_grant_is_in_the_schema() -> None:
    texts = {
        s.purpose: s.query.as_string() for s in default_privilege_statements(_NAMES)
    }
    revoke = texts.pop("default privileges: functions from public")

    assert revoke == (
        'ALTER DEFAULT PRIVILEGES FOR ROLE "billing_migrations" '
        "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
    )
    for text in texts.values():
        assert text.startswith(
            'ALTER DEFAULT PRIVILEGES FOR ROLE "billing_migrations" IN SCHEMA "billing"'
        )


def test_reader_gets_no_sequences_and_no_functions() -> None:
    texts = [s.query.as_string() for s in default_privilege_statements(_NAMES)]

    assert [text for text in texts if '"billing_reader"' in text] == [
        'ALTER DEFAULT PRIVILEGES FOR ROLE "billing_migrations" IN SCHEMA "billing" '
        'GRANT SELECT ON TABLES TO "billing_reader"'
    ]


def test_public_revoke_on_schema_public_is_conditional() -> None:
    statement = next(
        s
        for s in database_statements(_NAMES, [], ReaderGuards())
        if s.purpose == "revoke create on public"
    )

    assert statement.only_if is not None


def test_reader_guards_can_each_be_turned_off() -> None:
    guards = ReaderGuards(
        read_only=False, idle_in_transaction_timeout=None, statement_timeout=None
    )
    purposes = _purposes(database_statements(_NAMES, [], guards))

    assert [p for p in purposes if p.endswith("for billing_reader")] == [
        "set search_path for billing_reader"
    ]


def test_teardown_restore_reopens_connections_before_giving_the_owner_back() -> None:
    assert _purposes(restore_statements(_NAMES, ADMIN)) == [
        "restore connections",
        "revoke owner from admin",
    ]


@pytest.mark.parametrize(
    "statements",
    [
        role_statements(_NAMES, _VERIFIERS, RUN_ID, ADMIN),
        rotate_statements(_NAMES, _VERIFIERS),
    ],
    ids=["create", "rotate"],
)
def test_verifiers_are_sent_but_never_displayed(statements: list[Statement]) -> None:
    with_password = [s for s in statements if s.display is not None]
    rendered = render([Phase("postgres", statements)], _NAMES.owner, ADMIN)

    assert len(with_password) == len(ROLE_KINDS)
    assert all(_VERIFIER in s.query.as_string() for s in with_password)
    assert _VERIFIER not in rendered
    assert rendered.count(f"PASSWORD '{REDACTED}'") == len(ROLE_KINDS)


def test_a_rejected_statement_names_the_step_but_not_the_statement() -> None:
    server = FakeServer(
        failures={"CREATE ROLE": psycopg.errors.DuplicateObject("role exists")}
    )
    statement = role_statements(_NAMES, _VERIFIERS, RUN_ID, ADMIN)[0]

    with pytest.raises(ProvisioningError) as raised:
        execute(server.connect("postgres"), statement, _NAMES.owner)

    assert str(raised.value) == "Step 'create role billing_owner' failed: role exists"
    assert _VERIFIER not in str(raised.value)


def test_owner_statements_run_under_set_role_and_reset_after() -> None:
    server = FakeServer()
    grant, _ = connect_statements(_NAMES, ADMIN)

    execute(server.connect("postgres"), grant, _NAMES.owner)

    assert server.texts() == [
        'SET ROLE "billing_owner"',
        grant.query.as_string(),
        "RESET ROLE",
    ]


def test_render_wraps_owner_statements_and_shows_transactions() -> None:
    text = render(
        [Phase("postgres", connect_statements(_NAMES, ADMIN), transaction=True)],
        _NAMES.owner,
        ADMIN,
    )

    assert text.splitlines()[:3] == [
        f"-- Connected to postgres as {ADMIN}",
        "BEGIN;",
        'SET ROLE "billing_owner";',
    ]
    assert text.rstrip().endswith("COMMIT;")
