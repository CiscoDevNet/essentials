"""The real CLI against a real server.

Skipped unless `ESS_POSTGRES_PROVISION_TEST_DSN` names a superuser connection.
Every test uses a fresh random base name, and cleans up after itself as that
superuser even when it fails. The superuser also creates the non-superuser
provisioners, so their paths run for real.

Local servers usually authenticate with `trust`, so a wrong password still
logs in there; the password tests read the stored verifiers instead.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from click.testing import CliRunner, Result
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from ess_postgres_provision import lifecycle
from ess_postgres_provision.__main__ import main
from ess_postgres_provision.naming import ROLE_KINDS
from ess_postgres_provision.preflight import lock_key
from ess_postgres_provision.sinks import data_directory

_DSN = os.environ.get("ESS_POSTGRES_PROVISION_TEST_DSN", "")

pytestmark = pytest.mark.skipif(
    not _DSN, reason="set ESS_POSTGRES_PROVISION_TEST_DSN to a superuser DSN"
)

_SUPERUSER = "superuser"
_CREATEROLE = "createrole"
_NOINHERIT = "noinherit"
_ADMIN_ATTRIBUTES = {
    _CREATEROLE: "LOGIN NOSUPERUSER CREATEDB CREATEROLE INHERIT",
    _NOINHERIT: "LOGIN NOSUPERUSER CREATEDB CREATEROLE NOINHERIT",
}


def _superuser_connect(dbname: str = "postgres") -> psycopg.Connection:
    return psycopg.connect(_DSN, dbname=dbname, autocommit=True)


@dataclass
class Env:
    """One test's server, provisioner, and base name."""

    su: psycopg.Connection
    host: str
    port: int
    admin: str
    kind: str
    base: str

    def run(self, command: str, *args: str, dry_run: bool = False) -> Result:
        """Invoke the CLI in-process, exactly as an operator would."""
        argv = [
            *(["--dry-run"] if dry_run else []),
            command,
            self.base,
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--admin-user",
            self.admin,
            *args,
        ]
        return CliRunner().invoke(main, argv)

    def ok(self, command: str, *args: str) -> Result:
        """Run a command that must succeed."""
        result = self.run(command, *args)
        assert result.exit_code == 0, result.output
        return result

    def credentials_file(self) -> Path:
        """Where `create` wrote this base's credentials."""
        return data_directory(self.host) / f"{self.base}.env"

    def passwords(self, path: Path | None = None) -> dict[str, str]:
        """Each role kind's password, from a credentials file."""
        text = (path or self.credentials_file()).read_text(encoding="utf-8")
        values = dict(
            line.split("=", 1)
            for line in text.splitlines()
            if line and not line.startswith("#")
        )
        return {
            kind: values[f"{self.base}_{kind}_DATABASE_PASSWORD".upper()]
            for kind in ROLE_KINDS
            if f"{self.base}_{kind}_DATABASE_PASSWORD".upper() in values
        }

    def connect(self, kind: str, dbname: str | None = None) -> psycopg.Connection:
        """Log in as one of the provisioned roles with its delivered password."""
        return psycopg.connect(
            host=self.host,
            port=self.port,
            user=f"{self.base}_{kind}",
            password=self.passwords()[kind],
            dbname=dbname or self.base,
            autocommit=True,
        )

    def scalar(self, query: str, *params: Any) -> Any:
        """One value, read as the superuser."""
        row = self.su.execute(query, params).fetchone()
        return row[0] if row else None

    def exists(self) -> tuple[bool, list[str]]:
        """Whether the database exists, and which derived roles do."""
        database = self.scalar(
            "SELECT 1 FROM pg_database WHERE datname = %s", self.base
        )
        rows = self.su.execute(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s) ORDER BY rolname",
            [[f"{self.base}_{kind}" for kind in ROLE_KINDS]],
        ).fetchall()
        return database is not None, [name for (name,) in rows]

    def verifiers(self) -> dict[str, str]:
        """The stored password hash of each derived role."""
        rows = self.su.execute(
            "SELECT rolname, rolpassword FROM pg_authid WHERE rolname = ANY(%s)",
            [[f"{self.base}_{kind}" for kind in ROLE_KINDS]],
        ).fetchall()
        return dict(rows)


def _drop_everything(su: psycopg.Connection, base: str) -> None:
    su.execute(
        sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(base))
    )
    for kind in ROLE_KINDS:
        su.execute(
            sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(f"{base}_{kind}"))
        )


@pytest.fixture(scope="module")
def su() -> Iterator[psycopg.Connection]:
    with _superuser_connect() as conn:
        if not conn.execute(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        ).fetchone()[0]:
            pytest.fail("ESS_POSTGRES_PROVISION_TEST_DSN must connect as a superuser")
        yield conn


@pytest.fixture
def admin(
    request: pytest.FixtureRequest,
    su: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, str]]:
    """The provisioning role: the DSN's superuser, or a fresh non-superuser."""
    kind = getattr(request, "param", _SUPERUSER)
    dsn_password = conninfo_to_dict(_DSN).get("password")
    if kind == _SUPERUSER:
        if dsn_password:
            monkeypatch.setenv("PGPASSWORD", str(dsn_password))
        yield su.info.user, kind
        return
    name = f"it_prov_{uuid4().hex[:10]}"
    password = uuid4().hex
    su.execute(
        sql.SQL("CREATE ROLE {} {} PASSWORD {}").format(
            sql.Identifier(name),
            sql.SQL(_ADMIN_ATTRIBUTES[kind]),
            sql.Literal(password),
        )
    )
    monkeypatch.setenv("PGPASSWORD", password)
    try:
        yield name, kind
    finally:
        su.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))


@pytest.fixture
def env(su: psycopg.Connection, admin: tuple[str, str]) -> Iterator[Env]:
    base = f"it_{uuid4().hex[:12]}"
    try:
        yield Env(su, su.info.host, su.info.port, admin[0], admin[1], base)
    finally:
        _drop_everything(su, base)


_EVERY_ADMIN = pytest.mark.parametrize(
    "admin", [_SUPERUSER, _CREATEROLE, _NOINHERIT], indirect=True
)
_NON_SUPERUSERS = pytest.mark.parametrize(
    "admin", [_CREATEROLE, _NOINHERIT], indirect=True
)


# === The end-to-end scenario ===


@_EVERY_ADMIN
def test_create_migrate_use_and_teardown(env: Env) -> None:
    env.ok("create", "--yes")
    env.ok("verify")

    with env.connect("migrations") as conn:
        conn.execute("CREATE TABLE widgets (id serial PRIMARY KEY, name text)")
    with env.connect("app") as conn:
        conn.execute("INSERT INTO widgets (name) VALUES ('first')")
        assert conn.execute("SELECT name FROM widgets").fetchall() == [("first",)]
    with env.connect("reader") as conn:
        assert conn.execute("SELECT count(*) FROM widgets").fetchone() == (1,)
        conn.execute("SET default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO widgets (name) VALUES ('second')")
    env.ok("verify")

    if env.kind != _SUPERUSER:
        can_become_owner = env.scalar(
            "SELECT pg_has_role(%s, %s, 'SET')", env.admin, f"{env.base}_owner"
        )
        assert can_become_owner is False

    with env.connect("migrations") as conn:
        conn.execute("DROP TABLE widgets")
    env.ok("teardown", "--yes")

    assert env.exists() == (False, [])


def test_dry_run_creates_nothing(env: Env) -> None:
    result = env.run("create", dry_run=True)

    assert result.exit_code == 0, result.output
    assert "PASSWORD '***'" in result.output
    assert env.exists() == (False, [])
    assert not env.credentials_file().exists()


def test_verify_catches_privileges_granted_after_create(env: Env) -> None:
    env.ok("create", "--yes")
    with env.connect("migrations") as conn:
        conn.execute("CREATE TABLE widgets (id int)")
        conn.execute(f"GRANT UPDATE ON widgets TO {env.base}_reader")
        conn.execute(f"GRANT TRUNCATE ON widgets TO {env.base}_app")

    result = env.run("verify")

    assert result.exit_code == 1
    assert "reader cannot write any table" in result.output
    assert "app cannot truncate any table" in result.output


@pytest.mark.parametrize("missing", ["schema", "reader"])
def test_verify_reports_a_missing_schema_or_role_in_its_table(
    env: Env, missing: str
) -> None:
    env.ok("create", "--yes")
    reader = sql.Identifier(f"{env.base}_reader")
    with _superuser_connect(env.base) as conn:
        if missing == "schema":
            conn.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(env.base))
            )
        else:
            conn.execute(sql.SQL("DROP OWNED BY {}").format(reader))
            conn.execute(sql.SQL("DROP ROLE {}").format(reader))
    absent = f"schema {env.base}" if missing == "schema" else f"{env.base}_reader"

    result = env.run("verify")

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), result.exception
    assert f"FAIL  skipped: {absent} missing" in result.output


# === The lock ===


@pytest.mark.parametrize("command", ["create", "rotate", "teardown"])
def test_a_run_in_progress_refuses_every_write(env: Env, command: str) -> None:
    with _superuser_connect() as holder:
        holder.execute("SELECT pg_advisory_lock(%s)", [lock_key(env.base)])
        result = env.run(command, "--yes")

    assert result.exit_code == 3
    assert "Another run is provisioning" in result.output


# === Extensions ===


def _require_extension(env: Env, name: str) -> None:
    if (
        env.scalar("SELECT 1 FROM pg_available_extensions WHERE name = %s", name)
        is None
    ):
        pytest.skip(f"{name} is not available on this server")


@pytest.mark.parametrize("admin", [_SUPERUSER, _CREATEROLE], indirect=True)
def test_trusted_extension_installs_for_any_admin(env: Env) -> None:
    _require_extension(env, "pg_trgm")

    env.ok("create", "--yes", "--extension", "pg_trgm")
    env.ok("verify", "--extension", "pg_trgm")


@pytest.mark.parametrize("admin", [_SUPERUSER, _CREATEROLE], indirect=True)
def test_untrusted_extension_needs_a_superuser(env: Env) -> None:
    _require_extension(env, "pageinspect")

    result = env.run("create", "--yes", "--extension", "pageinspect")

    if env.kind == _SUPERUSER:
        assert result.exit_code == 0, result.output
    else:
        assert result.exit_code == 3
        assert "'pageinspect' is not trusted" in result.output
        assert env.exists() == (False, [])


# === Teardown from partial states ===


def test_teardown_drops_roles_left_without_a_database(env: Env) -> None:
    env.ok("create", "--yes")
    env.su.execute(
        sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(env.base))
    )

    env.ok("teardown", "--yes")

    assert env.exists() == (False, [])


@_NON_SUPERUSERS
def test_open_session_refuses_and_leaves_the_app_working(env: Env) -> None:
    env.ok("create", "--yes")
    with env.connect("app"):
        result = env.run("teardown", "--yes")

    assert result.exit_code == 3
    assert "other session(s)" in result.output
    assert env.scalar(
        "SELECT datallowconn FROM pg_database WHERE datname = %s", env.base
    )
    assert (
        env.scalar("SELECT pg_has_role(%s, %s, 'SET')", env.admin, f"{env.base}_owner")
        is False
    )
    with env.connect("app") as conn:
        assert conn.execute("SELECT 1").fetchone() == (1,)
    env.ok("verify")


def test_terminate_sessions_ends_them_and_drops(env: Env) -> None:
    env.ok("create", "--yes")
    held = env.connect("app")

    env.ok("teardown", "--yes", "--terminate-sessions")

    assert env.exists() == (False, [])
    with pytest.raises(psycopg.OperationalError):
        held.execute("SELECT 1")
    held.close()


@_NON_SUPERUSERS
def test_terminate_sessions_needs_signal_backend(env: Env) -> None:
    env.ok("create", "--yes")

    result = env.run("teardown", "--yes", "--terminate-sessions")

    assert result.exit_code == 3
    assert "pg_signal_backend" in result.output


def test_a_login_during_the_drain_is_refused(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    env.ok("create", "--yes")
    refused: list[str] = []
    original = lifecycle._Teardown._drain

    def drain_after_trying_to_log_in(self: Any) -> None:
        with pytest.raises(psycopg.OperationalError) as raised:
            env.connect("app").close()
        refused.append(str(raised.value))
        original(self)

    monkeypatch.setattr(lifecycle._Teardown, "_drain", drain_after_trying_to_log_in)

    env.ok("teardown", "--yes")

    assert len(refused) == 1
    assert "not currently accepting connections" in refused[0]


def test_teardown_refuses_a_database_with_data(env: Env) -> None:
    env.ok("create", "--yes")
    with env.connect("migrations") as conn:
        conn.execute("CREATE TABLE widgets (id int)")

    result = env.run("teardown", "--yes")

    assert result.exit_code == 3
    assert f"holds data ({env.base}.widgets)" in result.output
    with env.connect("app") as conn:
        assert conn.execute("SELECT count(*) FROM widgets").fetchone() == (0,)


def _add_config_table(env: Env) -> psycopg.Connection:
    """Give pg_trgm a configuration table, as an extension script would."""
    _require_extension(env, "pg_trgm")
    env.ok("create", "--yes", "--extension", "pg_trgm")
    conn = _superuser_connect(env.base)
    conn.execute("CREATE TABLE public.trgm_settings (builtin boolean)")
    conn.execute("ALTER EXTENSION pg_trgm ADD TABLE public.trgm_settings")
    conn.execute(
        "UPDATE pg_extension SET "
        "extconfig = ARRAY['public.trgm_settings'::regclass::oid], "
        "extcondition = ARRAY['WHERE NOT builtin'] WHERE extname = 'pg_trgm'"
    )
    return conn


def test_teardown_refuses_user_rows_in_an_extension_config_table(env: Env) -> None:
    with _add_config_table(env) as conn:
        conn.execute("INSERT INTO public.trgm_settings VALUES (false)")

    refused = env.run("teardown", "--yes")
    with _superuser_connect(env.base) as conn:
        conn.execute("UPDATE public.trgm_settings SET builtin = true")
    env.ok("teardown", "--yes")

    assert refused.exit_code == 3
    assert "holds data (public.trgm_settings)" in refused.output
    assert env.exists() == (False, [])


@_NON_SUPERUSERS
def test_teardown_refuses_config_rows_hidden_by_row_level_security(env: Env) -> None:
    with _add_config_table(env) as conn:
        conn.execute("ALTER TABLE public.trgm_settings ENABLE ROW LEVEL SECURITY")
        conn.execute("CREATE POLICY hide_all ON public.trgm_settings USING (false)")
        conn.execute("GRANT SELECT ON public.trgm_settings TO PUBLIC")
        conn.execute("INSERT INTO public.trgm_settings VALUES (false)")

    result = env.run("teardown", "--yes")

    assert result.exit_code == 3
    assert "holds data (public.trgm_settings (unreadable))" in result.output
    assert env.exists()[0]


def test_an_unmarked_role_is_never_adopted_or_dropped(env: Env) -> None:
    env.su.execute(
        sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(f"{env.base}_app"))
    )

    created = env.run("create", "--yes")
    torn_down = env.run("teardown", "--yes")

    assert created.exit_code == 3
    assert f"Already exists: role {env.base}_app" in created.output
    assert torn_down.exit_code == 3
    assert "no marker" in torn_down.output
    assert env.exists() == (False, [f"{env.base}_app"])


def test_a_database_owned_by_someone_else_is_refused(env: Env) -> None:
    env.su.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(env.base)))

    result = env.run("teardown", "--yes")

    assert result.exit_code == 3
    assert f"owned by {env.su.info.user}" in result.output
    assert env.exists() == (True, [])


# === The reader's write paths ===


def test_reader_cannot_write_through_a_security_definer_function(env: Env) -> None:
    env.ok("create", "--yes")
    with env.connect("migrations") as conn:
        conn.execute("CREATE TABLE widgets (name text)")
        conn.execute(
            sql.SQL(
                "CREATE FUNCTION add_widget(n text) RETURNS void LANGUAGE sql "
                "SECURITY DEFINER AS $$ INSERT INTO {}.widgets VALUES (n) $$"
            ).format(sql.Identifier(env.base))
        )

    with env.connect("app") as conn:
        conn.execute("SELECT add_widget('from app')")
    with env.connect("reader") as conn:
        conn.execute("SET default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT add_widget('from reader')")
    with env.connect("app") as conn:
        assert conn.execute("SELECT name FROM widgets").fetchall() == [("from app",)]
    env.ok("verify")


# === Passwords and settings ===


def test_md5_password_encryption_still_stores_scram(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PGOPTIONS", "-c password_encryption=md5")

    env.ok("create", "--yes")

    verifiers = env.verifiers()
    assert len(verifiers) == 4
    assert all(value.startswith("SCRAM-SHA-256$") for value in verifiers.values())


def test_search_path_stays_in_the_new_database(env: Env) -> None:
    env.ok("create", "--yes")

    with env.connect("app") as conn:
        inside = conn.execute("SHOW search_path").fetchone()[0]
    with env.connect("app", dbname="postgres") as conn:
        outside = conn.execute("SHOW search_path").fetchone()[0]

    assert inside.replace('"', "") == f"{env.base}, public"
    assert outside == '"$user", public'


def test_a_session_on_template1_does_not_block_create(env: Env) -> None:
    with _superuser_connect("template1"):
        env.ok("create", "--yes")


def test_rotate_twice_in_a_row_with_the_default_sink(env: Env) -> None:
    env.ok("create", "--yes")
    created = env.verifiers()

    env.ok("rotate", "--yes", "--role", "app")
    once = env.verifiers()
    env.ok("rotate", "--yes", "--role", "app")
    twice = env.verifiers()

    rotated = sorted(data_directory(env.host).glob(f"{env.base}.rotated-*.env"))
    app = f"{env.base}_app"
    assert len(rotated) == 2
    assert len({created[app], once[app], twice[app]}) == 3
    assert {k: v for k, v in twice.items() if k != app} == {
        k: v for k, v in created.items() if k != app
    }
    assert set(env.passwords(rotated[-1])) == {"app"}
