"""`create`: phase order, the live flag, and a dry run that writes nothing."""

import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest

from ess_postgres_provision.conftest import (
    ADMIN,
    CLOSE,
    RUN_ID,
    FakeConnector,
    FakeServer,
    fresh_server,
    role_rows,
)
from ess_postgres_provision.credentials import LiveFlag
from ess_postgres_provision.exceptions import PreflightError, ProvisioningError
from ess_postgres_provision.naming import ROLE_KINDS, derive_names
from ess_postgres_provision.options import CreateOptions, DeliveryOptions
from ess_postgres_provision.passwords import RolePassword
from ess_postgres_provision.provision import _run_phases, create, create_phases
from ess_postgres_provision.sql import Phase, catalog
from ess_postgres_provision.sql.database import ReaderGuards, database_statements
from ess_postgres_provision.ui import Ui

_NAMES = derive_names("billing")
_GIVE_BACK = f'REVOKE "billing_owner" FROM "{ADMIN}"'


def _passwords() -> dict[str, RolePassword]:
    return {
        kind: RolePassword(
            kind=kind,
            role=_NAMES.role(kind),
            password=f"plain-{kind}",
            verifier=f"SCRAM-SHA-256$4096:{kind}",
            entropy_bits=64.0,
        )
        for kind in ROLE_KINDS
    }


def _phases() -> list[Phase]:
    return create_phases(
        _NAMES,
        ADMIN,
        _passwords(),
        RUN_ID,
        database_statements(_NAMES, [], ReaderGuards()),
    )


def _index(texts: list[str], prefix: str) -> int:
    return next(i for i, text in enumerate(texts) if text.startswith(prefix))


class _Recorder:
    """A `Ui` whose output lands in lists and whose prompt must not be reached."""

    def __init__(self, *, dry_run: bool) -> None:
        self.out: list[str] = []
        self.err: list[str] = []
        self.ui = Ui(
            echo=self.out.append,
            note=self.err.append,
            confirm=self._confirm,
            dry_run=dry_run,
        )

    @staticmethod
    def _confirm(question: str) -> None:
        msg = f"prompted: {question}"
        raise AssertionError(msg)

    @property
    def text(self) -> str:
        return "\n".join([*self.out, *self.err])


def test_phases_are_roles_then_database_then_schema_then_give_back() -> None:
    phases = _phases()

    assert [(phase.database, phase.transaction) for phase in phases] == [
        ("postgres", True),
        ("postgres", False),
        ("billing", False),
        ("postgres", False),
    ]
    assert [s.purpose for s in phases[1].statements] == [
        "create database billing",
        "grant connect",
        "revoke connect from public",
    ]
    assert [s.purpose for s in phases[-1].statements] == ["revoke owner from admin"]


def test_roles_commit_before_create_database_and_mark_the_run_live() -> None:
    server = FakeServer()
    connector = FakeConnector(server)
    flag = LiveFlag()

    with server.connect("postgres") as maintenance:
        _run_phases(connector, maintenance, _phases(), _NAMES.owner, flag)
    texts = server.texts()

    assert flag.may_be_live
    assert texts[0] == "BEGIN"
    assert _index(texts, "COMMIT") < _index(texts, "CREATE DATABASE")
    assert all(
        text.startswith(("CREATE ROLE", "COMMENT ON ROLE", "GRANT"))
        for text in texts[1 : _index(texts, "COMMIT")]
    )


def test_connection_2_closes_before_the_owner_is_given_back() -> None:
    server = FakeServer()
    connector = FakeConnector(server)

    with server.connect("postgres") as maintenance:
        _run_phases(connector, maintenance, _phases(), _NAMES.owner, LiveFlag())
    log = [(entry.dbname, entry.text) for entry in server.log]

    assert server.opened == ["postgres", "billing"]
    assert log.index(("billing", CLOSE)) < log.index(("postgres", _GIVE_BACK))
    assert log[-2] == ("postgres", _GIVE_BACK)


def test_a_failure_inside_the_role_transaction_rolls_back_and_is_not_live() -> None:
    server = FakeServer(
        failures={"COMMENT ON ROLE": psycopg.errors.InsufficientPrivilege("denied")}
    )
    flag = LiveFlag()

    with (
        server.connect("postgres") as maintenance,
        pytest.raises(ProvisioningError, match="mark role billing_owner"),
    ):
        _run_phases(FakeConnector(server), maintenance, _phases(), _NAMES.owner, flag)

    assert not flag.may_be_live
    assert "ROLLBACK" in server.texts()
    assert not [text for text in server.texts() if "CREATE DATABASE" in text]
    assert _GIVE_BACK not in server.texts()


def test_a_failure_after_the_commit_is_live_and_still_gives_the_owner_back() -> None:
    server = FakeServer(
        failures={"CREATE SCHEMA": psycopg.errors.InsufficientPrivilege("denied")}
    )
    flag = LiveFlag()

    with (
        server.connect("postgres") as maintenance,
        pytest.raises(ProvisioningError, match="create schema billing"),
    ):
        _run_phases(FakeConnector(server), maintenance, _phases(), _NAMES.owner, flag)

    log = [(entry.dbname, entry.text) for entry in server.log]

    assert flag.may_be_live
    assert log.index(("billing", CLOSE)) < log.index(("postgres", _GIVE_BACK))


def test_a_failed_give_back_after_a_failure_keeps_the_original_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = FakeServer(
        failures={
            "CREATE SCHEMA": psycopg.errors.InsufficientPrivilege("denied"),
            _GIVE_BACK: psycopg.errors.OperationalError("connection lost"),
        }
    )

    with (
        server.connect("postgres") as maintenance,
        pytest.raises(ProvisioningError, match="create schema billing"),
    ):
        _run_phases(
            FakeConnector(server), maintenance, _phases(), _NAMES.owner, LiveFlag()
        )

    assert "Could not revoke owner from admin after a failed create" in caplog.text


def test_dry_run_writes_nothing_and_shows_no_secret(private_data_home: Path) -> None:
    server = fresh_server()
    recorder = _Recorder(dry_run=True)

    result = create(FakeConnector(server), _NAMES, CreateOptions(), recorder.ui)

    assert result is None
    assert server.writes() == []
    assert len(server.plaintexts) == len(ROLE_KINDS)
    for plaintext in server.plaintexts:
        assert plaintext not in recorder.text
    assert "SCRAM-SHA-256$" not in recorder.text
    assert recorder.text.count("PASSWORD '***'") == len(ROLE_KINDS)
    assert not private_data_home.exists()


def test_dry_run_header_names_the_admin_target_and_destination() -> None:
    recorder = _Recorder(dry_run=True)

    create(FakeConnector(fresh_server()), _NAMES, CreateOptions(), recorder.ui)
    lines = [" ".join(line.split()) for line in recorder.err[0].splitlines()]

    assert lines[:3] == [
        f"Connecting as: {ADMIN} (superuser: no, createdb: yes, createrole: yes)",
        "Target: billing @ localhost:5432 (SSL: off (local))",
        "Will create: billing_owner, billing_migrations, billing_app, billing_reader",
    ]
    assert lines[3].endswith("ess-postgres-provision/localhost/billing.env")


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_create_refuses_a_failed_run_file_git_would_track(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    (repo / ".gitignore").write_text("billing.env\n", encoding="utf-8")
    server = fresh_server()
    options = CreateOptions(
        delivery=DeliveryOptions(sink_paths=(repo / "billing.env",))
    )

    with pytest.raises(PreflightError, match=r"billing\.failed-.*not ignored"):
        create(FakeConnector(server), _NAMES, options, _Recorder(dry_run=False).ui)

    assert server.writes() == []


def test_create_refuses_an_existing_role_before_any_write() -> None:
    server = fresh_server()
    server.responses[catalog.ROLES] = role_rows("billing")[2:3]

    with pytest.raises(
        PreflightError, match="Already exists: role billing_app"
    ) as raised:
        create(
            FakeConnector(server),
            _NAMES,
            CreateOptions(),
            _Recorder(dry_run=False).ui,
        )

    assert raised.value.exit_code == 3
    assert server.writes() == []
