"""Fakes shared by the unit tests: a scripted server, its connections, and rows.

`FakeServer` answers each catalog query from `responses`, raises from
`failures` when a statement contains a given text, and logs every statement
from every connection in one list, so tests can assert order across
connections.
"""

from __future__ import annotations

import hashlib
from collections import namedtuple
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from psycopg import sql
from psycopg.pq import TransactionStatus

from ess_postgres_provision.connection import Target
from ess_postgres_provision.sql import catalog

ADMIN = "db_provisioner"
CLOSE = "-- close"
RUN_ID = "0123456789abcdef0123456789abcdef"

type Response = Sequence[Any] | Callable[[dict[str, Any] | None], Sequence[Any]]


def row(**fields: Any) -> Any:
    """A row read by field name, like psycopg's `namedtuple_row`."""
    return namedtuple("Row", fields)(**fields)


@dataclass(frozen=True)
class Executed:
    """One statement as a fake connection received it."""

    dbname: str
    text: str
    params: dict[str, Any] | None = None


class FakeCursor:
    """The result of one `execute`."""

    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = list(rows)

    def fetchone(self) -> Any:
        """The first row, or None."""
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        """Every row."""
        return list(self._rows)


class FakePgConn:
    """The libpq handle: hashes passwords and records each plaintext it saw."""

    ssl_in_use = False

    def __init__(self, server: FakeServer) -> None:
        self._server = server

    def encrypt_password(self, password: bytes, user: bytes, algorithm: bytes) -> bytes:
        """A deterministic stand-in for a SCRAM verifier."""
        self._server.plaintexts.append(password.decode())
        digest = hashlib.sha256(user + b":" + password).hexdigest()
        prefix = b"SCRAM-SHA-256$" if algorithm == b"scram-sha-256" else b"md5"
        return prefix + f"4096:{digest}".encode()


class FakeConnection:
    """A connection to one database on a `FakeServer`."""

    def __init__(self, server: FakeServer, dbname: str, backend_pid: int) -> None:
        self.server = server
        self.dbname = dbname
        self.closed = False
        self.pgconn = FakePgConn(server)
        self.info = SimpleNamespace(
            transaction_status=TransactionStatus.IDLE,
            backend_pid=backend_pid,
            encoding="utf-8",
            server_version=server.server_version,
        )

    def execute(
        self, query: str | sql.Composable, params: dict[str, Any] | None = None
    ) -> FakeCursor:
        """Log the statement, then raise or answer as the server is scripted."""
        text = query if isinstance(query, str) else query.as_string()
        self.server.log.append(Executed(self.dbname, text, params))
        for needle, error in self.server.failures.items():
            if needle in text:
                raise error
        response = self.server.responses.get(text, [])
        return FakeCursor(response(params) if callable(response) else response)

    @contextmanager
    def transaction(self, force_rollback: bool = False) -> Iterator[None]:
        """Log `BEGIN`, then `COMMIT` or `ROLLBACK`."""
        self.server.log.append(Executed(self.dbname, "BEGIN"))
        try:
            yield
        except BaseException:
            self.server.log.append(Executed(self.dbname, "ROLLBACK"))
            raise
        end = "ROLLBACK" if force_rollback else "COMMIT"
        self.server.log.append(Executed(self.dbname, end))

    def close(self) -> None:
        """Log the close once."""
        if not self.closed:
            self.closed = True
            self.server.log.append(Executed(self.dbname, CLOSE))

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


@dataclass
class FakeServer:
    """A scripted server shared by every connection a test opens."""

    responses: dict[str, Response] = field(default_factory=dict)
    failures: dict[str, BaseException] = field(default_factory=dict)
    log: list[Executed] = field(default_factory=list)
    opened: list[str] = field(default_factory=list)
    plaintexts: list[str] = field(default_factory=list)
    server_version: int = 170000
    _next_pid: int = 1000

    def connect(self, dbname: str) -> FakeConnection:
        """Open a connection, recording which database it is on."""
        self.opened.append(dbname)
        self._next_pid += 1
        return FakeConnection(self, dbname, self._next_pid)

    def texts(self, dbname: str | None = None) -> list[str]:
        """Every statement sent, optionally only those on one database."""
        return [
            entry.text for entry in self.log if dbname is None or entry.dbname == dbname
        ]

    def writes(self) -> list[str]:
        """Statements other than reads, transaction control, and closes."""
        reads = {"BEGIN", "COMMIT", "ROLLBACK", CLOSE}
        return [
            text
            for text in self.texts()
            if text not in reads and not text.startswith("SELECT")
        ]


class FakeConnector:
    """Stands in for `Connector`, opening every connection on one `FakeServer`."""

    def __init__(self, server: FakeServer, target: Target | None = None) -> None:
        self.server = server
        self.target = target or Target("localhost", 5432, ADMIN)

    def connect(self, dbname: str) -> FakeConnection:
        """Connect as the admin."""
        return self.server.connect(dbname)

    def connect_as(self, _role: str, _password: str, dbname: str) -> FakeConnection:
        """Connect as a provisioned role."""
        return self.server.connect(dbname)


def admin_facts_row(*, superuser: bool = False, self_grant: str = "") -> Any:
    """What `ADMIN_FACTS` returns for a `CREATEDB CREATEROLE` admin, or a superuser."""
    return row(
        rolname=ADMIN,
        rolsuper=superuser,
        rolcreatedb=True,
        rolcreaterole=True,
        managed_superuser=False,
        signal_backend=superuser,
        server_version="17.11",
        createrole_self_grant=self_grant,
    )


def role_rows(base: str, run_id: str = RUN_ID) -> list[Any]:
    """`ROLES` rows for all four derived roles, each carrying the marker."""
    return [
        row(
            rolname=f"{base}_{kind}",
            rolcanlogin=True,
            rolsuper=False,
            rolcreatedb=False,
            rolcreaterole=False,
            rolreplication=False,
            rolbypassrls=False,
            marker=f"ess-postgres-provision:{base}:{run_id}",
        )
        for kind in ("owner", "migrations", "app", "reader")
    ]


def fresh_server(*, lock: bool = True) -> FakeServer:
    """A server where nothing exists yet and the admin can provision."""
    return FakeServer(
        responses={
            catalog.TRY_ADVISORY_LOCK: [row(acquired=lock)],
            catalog.ADMIN_FACTS: [admin_facts_row()],
            catalog.TEMPLATE0_ENCODING: [row(encoding="UTF8")],
        }
    )


@pytest.fixture(autouse=True)
def private_data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Send every default credential file under `tmp_path`, never the real home."""
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    return data_home
