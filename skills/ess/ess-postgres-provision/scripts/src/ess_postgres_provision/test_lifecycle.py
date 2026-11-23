"""`teardown` and `rotate`: provenance, step order, and the restore on failure."""

import re
from collections.abc import Callable
from typing import Any

import psycopg
import pytest

from ess_postgres_provision import lifecycle
from ess_postgres_provision.conftest import (
    ADMIN,
    CLOSE,
    FakeConnector,
    FakeServer,
    admin_facts_row,
    fresh_server,
    role_rows,
    row,
)
from ess_postgres_provision.exceptions import PreflightError, ProvisioningError
from ess_postgres_provision.lifecycle import rotate, teardown
from ess_postgres_provision.naming import ROLE_KINDS, derive_names
from ess_postgres_provision.options import RotateOptions, TeardownOptions
from ess_postgres_provision.sinks import data_directory
from ess_postgres_provision.sql import catalog
from ess_postgres_provision.ui import Ui

_NAMES = derive_names("billing")
_REGRANT = f'GRANT "billing_owner" TO "{ADMIN}" WITH SET TRUE, INHERIT FALSE'
_BLOCK = 'ALTER DATABASE "billing" WITH ALLOW_CONNECTIONS false'
_RESTORE = 'ALTER DATABASE "billing" WITH ALLOW_CONNECTIONS true'
_GIVE_BACK = f'REVOKE "billing_owner" FROM "{ADMIN}"'
_DROP = 'DROP DATABASE "billing"'
_DROP_ROLES = [
    f'DROP ROLE "billing_{kind}"' for kind in ("reader", "app", "migrations", "owner")
]


def _ui(*, dry_run: bool = False) -> tuple[Ui, list[str]]:
    lines: list[str] = []
    return (
        Ui(
            echo=lines.append,
            note=lines.append,
            confirm=lambda _q: None,
            dry_run=dry_run,
        ),
        lines,
    )


def _database(*, owner: str = "billing_owner", allow: bool = True) -> list[Any]:
    return [row(oid=16384, owner=owner, datallowconn=allow, public_connect=False)]


def _sequence(*answers: list[Any]) -> Callable[[dict[str, Any] | None], list[Any]]:
    """Answer each call with the next list, repeating the last."""
    remaining = list(answers)

    def answer(_params: dict[str, Any] | None) -> list[Any]:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return answer


def _built_server(**responses: Any) -> FakeServer:
    """Everything `create` builds exists, empty, with no other sessions."""
    server = fresh_server()
    server.responses.update(
        {
            catalog.ADMIN_FACTS: [admin_facts_row(superuser=True)],
            catalog.ROLES: role_rows("billing"),
            catalog.DATABASE: _database(),
            catalog.HAS_LARGE_OBJECTS: [row(found=False)],
        }
    )
    for name, response in responses.items():
        server.responses[getattr(catalog, name)] = response
    return server


def _teardown(server: FakeServer, *, terminate: bool = False) -> list[str]:
    ui, _ = _ui()
    return teardown(FakeConnector(server), _NAMES, TeardownOptions(terminate), ui)


def _assert_in_order(server: FakeServer, expected: list[tuple[str, str]]) -> None:
    log = [(entry.dbname, entry.text) for entry in server.log]
    position = 0
    for item in expected:
        assert item in log[position:], f"{item} missing after entry {position}"
        position = log.index(item, position) + 1


def _assert_restored_after_block(server: FakeServer) -> None:
    _assert_in_order(
        server,
        [("postgres", _BLOCK), ("postgres", _RESTORE), ("postgres", _GIVE_BACK)],
    )
    assert _DROP not in server.texts()
    assert not set(_DROP_ROLES) & set(server.texts())


# === Teardown: the six steps ===


def test_teardown_runs_the_six_steps_in_order() -> None:
    server = _built_server()

    dropped = _teardown(server)

    _assert_in_order(
        server,
        [
            ("billing", catalog.SAMPLE_RELATIONS),
            ("postgres", _REGRANT),
            ("postgres", 'SET ROLE "billing_owner"'),
            ("postgres", _BLOCK),
            ("postgres", catalog.OTHER_SESSIONS),
            ("billing", catalog.SAMPLE_RELATIONS),
            ("billing", CLOSE),
            ("postgres", 'SET ROLE "billing_owner"'),
            ("postgres", _DROP),
            *[("postgres", drop) for drop in _DROP_ROLES],
        ],
    )
    assert _RESTORE not in server.texts()
    assert _GIVE_BACK not in server.texts()
    assert dropped == [
        "database billing",
        *[f"role billing_{kind}" for kind in ("reader", "app", "migrations", "owner")],
    ]


def test_teardown_excludes_its_own_connection_from_the_session_check() -> None:
    server = _built_server()

    _teardown(server)
    (check,) = [e for e in server.log if e.text == catalog.OTHER_SESSIONS]
    held_pid = server.opened.index("billing") + 1001

    assert check.params == {"database": "billing", "exclude_pid": held_pid}


def test_data_found_first_refuses_before_any_write() -> None:
    server = _built_server(SAMPLE_RELATIONS=[row(relation="billing.widgets")])

    with pytest.raises(PreflightError, match=r"holds data \(billing.widgets\)"):
        _teardown(server)

    assert server.writes() == []


_CONFIG_TABLE = row(
    schema_name="public", table_name="settings", condition="WHERE NOT builtin"
)
_CONFIG_ROWS = catalog.config_table_has_rows(
    "public", "settings", "WHERE NOT builtin"
).as_string()


@pytest.mark.parametrize(
    ("answer", "found"),
    [
        ([row(found=True)], "public.settings"),
        (
            psycopg.errors.InsufficientPrivilege("denied"),
            "public.settings (unreadable)",
        ),
    ],
    ids=["user rows", "unreadable"],
)
def test_user_rows_in_an_extension_config_table_refuse(answer: Any, found: str) -> None:
    server = _built_server(EXTENSION_CONFIG_TABLES=[_CONFIG_TABLE])
    if isinstance(answer, BaseException):
        server.failures[_CONFIG_ROWS] = answer
    else:
        server.responses[_CONFIG_ROWS] = answer

    with pytest.raises(PreflightError, match=rf"holds data \({re.escape(found)}\)"):
        _teardown(server)

    assert server.writes() == ["SET row_security = off"]


def test_an_extension_config_table_with_only_its_own_rows_is_not_data() -> None:
    server = _built_server(EXTENSION_CONFIG_TABLES=[_CONFIG_TABLE])
    server.responses[_CONFIG_ROWS] = [row(found=False)]

    _teardown(server)

    assert _DROP in server.texts()


def test_data_written_after_the_first_check_is_caught_by_the_final_one() -> None:
    server = _built_server(
        SAMPLE_RELATIONS=_sequence([], [row(relation="billing.late")])
    )

    with pytest.raises(PreflightError, match="billing.late"):
        _teardown(server)

    _assert_restored_after_block(server)


def test_other_sessions_refuse_and_restore_connections_then_the_owner() -> None:
    server = _built_server(OTHER_SESSIONS=[row(pid=4242)])

    with pytest.raises(PreflightError, match="1 other session"):
        _teardown(server)

    _assert_restored_after_block(server)


def test_terminate_sessions_ends_them_and_proceeds() -> None:
    server = _built_server(OTHER_SESSIONS=_sequence([row(pid=4242)], []))

    _teardown(server, terminate=True)
    (terminate,) = [e for e in server.log if e.text == catalog.TERMINATE_BACKEND]

    assert terminate.params == {"pid": 4242, "timeout_ms": 5000}
    assert _DROP in server.texts()


def test_sessions_that_survive_termination_refuse() -> None:
    server = _built_server(OTHER_SESSIONS=[row(pid=4242)])

    with pytest.raises(PreflightError, match="did not end"):
        _teardown(server, terminate=True)

    _assert_restored_after_block(server)


def test_terminate_sessions_needs_signal_backend_before_anything() -> None:
    server = _built_server(ADMIN_FACTS=[admin_facts_row(superuser=False)])

    with pytest.raises(PreflightError, match="pg_signal_backend"):
        _teardown(server, terminate=True)

    assert server.writes() == []


@pytest.mark.parametrize(
    "error",
    [psycopg.errors.ObjectInUse("database is being accessed"), KeyboardInterrupt()],
    ids=["server error", "interrupt"],
)
def test_a_failed_drop_restores_connections_then_the_owner(
    error: BaseException,
) -> None:
    server = _built_server()
    server.failures[_DROP] = error

    with pytest.raises((ProvisioningError, KeyboardInterrupt)):
        _teardown(server)

    _assert_in_order(
        server,
        [("postgres", _DROP), ("postgres", _RESTORE), ("postgres", _GIVE_BACK)],
    )
    assert not set(_DROP_ROLES) & set(server.texts())


def test_a_failed_restore_does_not_give_the_owner_back() -> None:
    server = _built_server(OTHER_SESSIONS=[row(pid=4242)])
    server.failures[_RESTORE] = psycopg.errors.InsufficientPrivilege("denied")

    with pytest.raises(PreflightError):
        _teardown(server)

    assert _GIVE_BACK not in server.texts()


def test_a_blocked_database_is_reopened_and_checked_before_it_is_dropped() -> None:
    server = _built_server(DATABASE=_database(allow=False))

    _teardown(server)

    _assert_in_order(
        server,
        [
            ("postgres", _REGRANT),
            ("postgres", _RESTORE),
            ("billing", catalog.SAMPLE_RELATIONS),
            ("postgres", _BLOCK),
            ("postgres", _DROP),
        ],
    )


# === Teardown: partial states and refusals ===


def test_roles_without_a_database_are_dropped_alone() -> None:
    server = _built_server(DATABASE=[])

    dropped = _teardown(server)

    assert server.writes() == _DROP_ROLES
    assert dropped[0] == "role billing_reader"


def test_nothing_to_do_writes_nothing() -> None:
    server = _built_server(DATABASE=[], ROLES=[])

    assert _teardown(server) == []
    assert server.writes() == []


def _unmarked() -> list[Any]:
    rows = role_rows("billing")
    return [rows[0]._replace(marker="made by hand"), *rows[1:]]


def _mixed_runs() -> list[Any]:
    return [*role_rows("billing")[:2], *role_rows("billing", "f" * 32)[2:]]


@pytest.mark.parametrize(
    ("responses", "message"),
    [
        ({"ROLES": _unmarked()}, "billing_owner exists but was not created"),
        ({"ROLES": _mixed_runs()}, "come from different runs"),
        ({"DATABASE": _database(owner="postgres")}, "owned by postgres"),
        (
            {"ROLES": [role_rows("billing")[0]._replace(rolsuper=True)]},
            r"billing_owner \(SUPERUSER\) holds cluster attributes",
        ),
        (
            {
                "ROLE_DEPENDENCIES": [
                    row(rolname="billing_app", dbid=1, class_name="pg_class", objid=1)
                ]
            },
            "billing_app own or hold privileges on objects outside billing",
        ),
    ],
    ids=["unmarked", "mixed runs", "foreign owner", "elevated", "foreign objects"],
)
def test_teardown_refuses_what_it_cannot_vouch_for(
    responses: dict[str, Any], message: str
) -> None:
    server = _built_server(**responses)

    with pytest.raises(PreflightError, match=message):
        _teardown(server)

    assert server.writes() == []


def test_teardown_dry_run_writes_nothing_and_lists_the_drops() -> None:
    server = _built_server()
    ui, lines = _ui(dry_run=True)

    assert teardown(FakeConnector(server), _NAMES, TeardownOptions(), ui) == []
    assert server.writes() == []
    assert "Will drop:" in lines[0]
    assert _DROP + ";" in lines[1]


# === Rotate ===


def test_rotate_sets_new_verifiers_in_one_transaction_and_writes_a_new_file() -> None:
    server = _built_server()
    ui, _ = _ui()

    report = rotate(
        FakeConnector(server), _NAMES, RotateOptions(kinds=("app", "app")), ui
    )

    begin, alter, commit, close = [
        t for t in server.texts() if not t.startswith("SELECT")
    ]
    (plaintext,) = server.plaintexts
    (rotated,) = data_directory("localhost").glob("billing.rotated-*.env")

    assert (begin, commit, close) == ("BEGIN", "COMMIT", CLOSE)
    assert alter.startswith('ALTER ROLE "billing_app" PASSWORD \'SCRAM-SHA-256$')
    assert plaintext not in alter
    rotated_text = rotated.read_text(encoding="utf-8")
    assert f"BILLING_APP_DATABASE_PASSWORD={plaintext}" in rotated_text
    assert report.messages[-1] == (
        "Now stale in earlier credential files: "
        "BILLING_APP_DATABASE_PASSWORD, BILLING_APP_DATABASE_URL"
    )


@pytest.mark.parametrize(
    ("kinds", "suffix"),
    [
        (("app", "reader"), f"--admin-user {ADMIN} --role app --role reader"),
        (ROLE_KINDS, f"--admin-user {ADMIN}"),
    ],
    ids=["some roles", "all four"],
)
def test_a_failed_rotate_recovers_only_the_roles_it_rotated(
    monkeypatch: pytest.MonkeyPatch, kinds: tuple[str, ...], suffix: str
) -> None:
    def commit_then_fail(*_args: Any, before_commit: Callable[[], None]) -> None:
        before_commit()
        raise ProvisioningError("connection lost")

    monkeypatch.setattr(lifecycle, "run_phase", commit_then_fail)
    ui, _ = _ui()

    with pytest.raises(ProvisioningError) as raised:
        rotate(FakeConnector(_built_server()), _NAMES, RotateOptions(kinds), ui)

    assert str(raised.value).splitlines()[-1].endswith(suffix)


def test_rotate_dry_run_shows_no_secret() -> None:
    server = _built_server()
    ui, lines = _ui(dry_run=True)

    assert rotate(FakeConnector(server), _NAMES, RotateOptions(), ui) is None
    text = "\n".join(lines)

    assert server.writes() == []
    assert "SCRAM-SHA-256$" not in text
    assert not [p for p in server.plaintexts if p in text]
    assert not list(data_directory("localhost").glob("*.env"))


@pytest.mark.parametrize(
    ("responses", "message"),
    [
        ({"DATABASE": []}, "run create first"),
        ({"ROLES": role_rows("billing")[:2]}, "Cannot rotate billing_app"),
        ({"ROLES": _unmarked()}, "not created by ess-postgres-provision"),
    ],
    ids=["no database", "missing role", "unmarked"],
)
def test_rotate_refuses_what_create_did_not_build(
    responses: dict[str, Any], message: str
) -> None:
    server = _built_server(**responses)
    ui, _ = _ui()

    with pytest.raises(PreflightError, match=message):
        rotate(FakeConnector(server), _NAMES, RotateOptions(), ui)

    assert server.writes() == []
