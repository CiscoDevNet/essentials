"""Read-only checks and the advisory lock."""

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from ess_postgres_provision.conftest import (
    ADMIN,
    FakeConnector,
    FakeServer,
    admin_facts_row,
    fresh_server,
    row,
)
from ess_postgres_provision.exceptions import PreflightError
from ess_postgres_provision.lifecycle import rotate, teardown
from ess_postgres_provision.naming import derive_names
from ess_postgres_provision.options import (
    CreateOptions,
    RotateOptions,
    TeardownOptions,
)
from ess_postgres_provision.preflight import (
    AdminFacts,
    admin_facts,
    lock_key,
    neutralize_self_grant,
    require_capability,
    require_version,
    resolve_extensions,
)
from ess_postgres_provision.provision import create
from ess_postgres_provision.sql import catalog
from ess_postgres_provision.ui import Ui

_NAMES = derive_names("billing")
_UI = Ui(echo=lambda _line: None, note=lambda _line: None, confirm=lambda _q: None)
_FACTS = AdminFacts(
    user=ADMIN,
    superuser=False,
    createdb=True,
    createrole=True,
    managed_superuser=False,
    signal_backend=False,
    server_version=170011,
    server_version_text="17.11",
    ssl="off",
    createrole_self_grant="",
)


# === The lock ===


def _lock_key_in_subprocess(hash_seed: str) -> int:
    code = (
        "from ess_postgres_provision.preflight import lock_key; "
        "print(lock_key('billing'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
    )
    return int(result.stdout)


def test_lock_key_is_stable_across_processes_and_hash_seeds() -> None:
    keys = {_lock_key_in_subprocess(seed) for seed in ("1", "2")}

    assert keys == {lock_key("billing")}


def test_lock_key_is_a_signed_64_bit_integer_unique_per_base() -> None:
    key = lock_key("billing")

    assert -(2**63) <= key < 2**63
    assert key != lock_key("billing2")


_COMMANDS: dict[str, Callable[[FakeConnector], object]] = {
    "create": lambda c: create(c, _NAMES, CreateOptions(), _UI),
    "rotate": lambda c: rotate(c, _NAMES, RotateOptions(), _UI),
    "teardown": lambda c: teardown(c, _NAMES, TeardownOptions(), _UI),
}


@pytest.mark.parametrize("command", _COMMANDS.values(), ids=_COMMANDS)
def test_every_write_takes_the_lock_in_postgres_before_anything_else(
    command: Callable[[FakeConnector], object],
) -> None:
    server = fresh_server(lock=False)

    with pytest.raises(PreflightError, match="Another run is provisioning 'billing'"):
        command(FakeConnector(server))

    assert server.opened == ["postgres"]
    first = server.log[0]
    assert first.text == catalog.TRY_ADVISORY_LOCK
    assert first.params == {"key": lock_key("billing")}
    assert len(server.log) == 2  # the lock, then the close


# === The admin ===


def test_admin_facts_count_superuser_as_holding_signal_backend() -> None:
    server = fresh_server()
    server.responses[catalog.ADMIN_FACTS] = [admin_facts_row(superuser=True)]

    facts = admin_facts(server.connect("postgres"), "off")

    assert facts.signal_backend
    assert facts.server_version == 170000


@pytest.mark.parametrize(
    ("superuser", "createdb", "createrole", "allowed"),
    [
        (True, False, False, True),
        (False, True, True, True),
        (False, True, False, False),
        (False, False, True, False),
    ],
)
def test_capability_needs_superuser_or_createdb_and_createrole(
    superuser: bool, createdb: bool, createrole: bool, allowed: bool
) -> None:
    facts = replace(
        _FACTS, superuser=superuser, createdb=createdb, createrole=createrole
    )

    if allowed:
        require_capability(facts)
    else:
        with pytest.raises(PreflightError, match="needs SUPERUSER"):
            require_capability(facts)


@pytest.mark.parametrize(("version", "allowed"), [(150012, False), (160000, True)])
def test_version_floor_is_16(version: int, allowed: bool) -> None:
    facts = replace(_FACTS, server_version=version, server_version_text="x")

    if allowed:
        require_version(facts)
    else:
        with pytest.raises(PreflightError, match="PostgreSQL 16 or later"):
            require_version(facts)


@pytest.mark.parametrize(("self_grant", "statements"), [("", 0), ("set, inherit", 1)])
def test_createrole_self_grant_is_cleared_only_when_set(
    self_grant: str, statements: int
) -> None:
    server = fresh_server()

    neutralize_self_grant(
        server.connect("postgres"), replace(_FACTS, createrole_self_grant=self_grant)
    )

    assert server.texts() == ["SET createrole_self_grant = ''"][:statements]


# === Extensions ===


def _extensions_server() -> FakeServer:
    server = fresh_server()

    def trusted(params: dict[str, Any] | None) -> list[Any]:
        known = {"pg_trgm": True, "pageinspect": False}
        name = (params or {})["name"]
        return [row(trusted=known[name])] if name in known else []

    server.responses[catalog.EXTENSION_TRUSTED] = trusted
    return server


def test_trusted_extension_runs_as_the_owner_for_any_admin() -> None:
    conn = _extensions_server().connect("postgres")

    extensions = resolve_extensions(conn, ["pg_trgm", "pg_trgm"], _FACTS)

    assert [(e.name, e.trusted) for e in extensions] == [("pg_trgm", True)]


def test_untrusted_extension_needs_a_superuser_or_managed_admin() -> None:
    conn = _extensions_server().connect("postgres")

    with pytest.raises(PreflightError, match="'pageinspect' is not trusted"):
        resolve_extensions(conn, ["pageinspect"], _FACTS)
    managed = resolve_extensions(
        conn, ["pageinspect"], replace(_FACTS, managed_superuser=True)
    )

    assert [(e.name, e.trusted) for e in managed] == [("pageinspect", False)]


def test_unavailable_extension_is_refused() -> None:
    conn = _extensions_server().connect("postgres")

    with pytest.raises(PreflightError, match="'vector' is not available"):
        resolve_extensions(conn, ["vector"], replace(_FACTS, superuser=True))
