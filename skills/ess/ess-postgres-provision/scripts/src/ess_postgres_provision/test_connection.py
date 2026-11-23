"""Connection URLs, the TLS rule, and password generation."""

from typing import Any

import psycopg
import pytest

from ess_postgres_provision.conftest import FakeConnection, FakeServer
from ess_postgres_provision.connection import (
    Connector,
    Target,
    connection_url,
    url_sslmode,
)
from ess_postgres_provision.exceptions import PreflightError, ProvisioningError
from ess_postgres_provision.naming import derive_names
from ess_postgres_provision.passwords import generate_role_passwords, scram_verifier


@pytest.mark.parametrize(
    ("host", "local"),
    [
        ("localhost", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("/var/run/postgresql", True),
        ("db.example.com", False),
    ],
)
def test_sockets_and_loopback_are_local(host: str, local: bool) -> None:
    assert Target(host, 5432, "admin").is_local is local


_REMOTE = Target("db.example.com", 5432, "admin")


@pytest.mark.parametrize(
    ("target", "pgsslmode", "expected"),
    [
        (_REMOTE, None, "require"),
        (_REMOTE, "prefer", "require"),
        (_REMOTE, "verify-full", "verify-full"),
        (Target("db.example.com", 5432, "admin", allow_insecure=True), "prefer", None),
        (Target("localhost", 5432, "admin"), None, None),
    ],
    ids=["unset", "weak", "stronger", "allow insecure", "local"],
)
def test_remote_connections_require_ssl_before_authenticating(
    monkeypatch: pytest.MonkeyPatch,
    target: Target,
    pgsslmode: str | None,
    expected: str | None,
) -> None:
    monkeypatch.delenv("PGSERVICE", raising=False)
    if pgsslmode is None:
        monkeypatch.delenv("PGSSLMODE", raising=False)
    else:
        monkeypatch.setenv("PGSSLMODE", pgsslmode)
    seen: dict[str, Any] = {}

    def connect(**params: Any) -> FakeConnection:
        seen.update(params)
        conn = FakeServer().connect(params["dbname"])
        conn.pgconn.ssl_in_use = True
        return conn

    monkeypatch.setattr(psycopg, "connect", connect)

    Connector(target).connect("postgres")

    assert seen.get("sslmode") == expected


@pytest.mark.parametrize("pgsslmode", ["", "prefer"], ids=["unset", "weak"])
def test_a_service_without_a_pgsslmode_requiring_ssl_is_refused(
    monkeypatch: pytest.MonkeyPatch, pgsslmode: str
) -> None:
    monkeypatch.setenv("PGSERVICE", "billing-prod")
    monkeypatch.setenv("PGSSLMODE", pgsslmode)

    with pytest.raises(PreflightError, match="PGSERVICE is set") as raised:
        _ = _REMOTE.required_sslmode

    assert raised.value.exit_code == 3
    assert Target("localhost", 5432, "admin").required_sslmode is None


def test_a_service_with_a_pgsslmode_requiring_ssl_uses_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PGSERVICE", "billing-prod")
    monkeypatch.setenv("PGSSLMODE", "verify-full")

    assert _REMOTE.required_sslmode == "verify-full"


def test_url_percent_encodes_every_component() -> None:
    url = connection_url(
        Target("db.example.com", 5432, "admin"),
        "billing_app",
        "p@ss:w/rd %?",
        "billing",
        "verify-full",
    )

    expected = (
        "postgresql://billing_app:p%40ss%3Aw%2Frd%20%25%3F"  # trufflehog:ignore
        "@db.example.com:5432/billing?sslmode=verify-full"
    )

    assert url == expected


def test_url_brackets_ipv6_and_moves_sockets_to_the_query() -> None:
    ipv6 = connection_url(Target("2001:db8::1", 5432, "a"), "r", "p", "d", None)
    socket = connection_url(
        Target("/var/run/postgresql", 5433, "a"), "r", "p", "d", None
    )
    expected_ipv6 = "postgresql://r:p@[2001:db8::1]:5432/d"  # trufflehog:ignore
    expected_socket = (
        "postgresql://r:p@/d?host=%2Fvar%2Frun%2Fpostgresql"  # trufflehog:ignore
        "&port=5433"
    )

    assert ipv6 == expected_ipv6
    assert socket == expected_socket


def test_remote_urls_carry_pgsslmode_and_local_ones_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeServer().connect("postgres")
    monkeypatch.setenv("PGSSLMODE", "verify-full")

    assert url_sslmode(conn, Target("db.example.com", 5432, "a")) == "verify-full"
    assert url_sslmode(conn, Target("localhost", 5432, "a")) is None


def test_a_weak_pgsslmode_never_reaches_a_url_when_provisioning_used_ssl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeServer().connect("postgres")
    conn.pgconn.ssl_in_use = True
    monkeypatch.setenv("PGSSLMODE", "prefer")

    assert url_sslmode(conn, _REMOTE) == "require"


def test_each_role_gets_an_independent_password_hashed_client_side() -> None:
    server = FakeServer()
    names = derive_names("billing")

    passwords = generate_role_passwords(
        server.connect("postgres"), names, ["app", "reader"], digits=6
    )

    assert list(passwords) == ["app", "reader"]
    assert passwords["app"].password != passwords["reader"].password
    assert passwords["app"].password[-6:].isdigit()
    assert server.plaintexts == [p.password for p in passwords.values()]
    for password in passwords.values():
        assert password.verifier.startswith("SCRAM-SHA-256$")
        assert password.password not in repr(password)
        assert password.verifier not in repr(password)


def test_a_non_scram_verifier_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = FakeServer().connect("postgres")
    monkeypatch.setattr(conn.pgconn, "encrypt_password", lambda *_args: b"md5abcdef")

    with pytest.raises(ProvisioningError, match="non-SCRAM verifier"):
        scram_verifier(conn, "billing_app", "pw")
