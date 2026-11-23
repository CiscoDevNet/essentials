"""Open admin and role connections with the TLS policy applied."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote

import psycopg
from psycopg.rows import namedtuple_row

from .exceptions import PreflightError
from .sql import catalog

MAINTENANCE_DATABASE = "postgres"

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_APPLICATION_NAME = "ess-postgres-provision"
_CONNECT_TIMEOUT_SECONDS = 10
_LIBPQ_MISSING_SECRET_ERROR = "no password supplied"
_SSL_REQUIRING_MODES = frozenset({"require", "verify-ca", "verify-full"})


@dataclass(frozen=True)
class Target:
    """Where to connect, and as whom.

    Attributes:
        host: Hostname, IP address, or Unix socket directory.
        port: Server port.
        admin_user: The provisioning role. Its password resolves through
            libpq (`PGPASSWORD`, `~/.pgpass`) or a prompt.
        allow_insecure: Permit a non-local host without SSL.
    """

    host: str
    port: int
    admin_user: str
    allow_insecure: bool = False

    @property
    def is_local(self) -> bool:
        """A Unix socket or a loopback address, both exempt from the TLS rule."""
        return self.host.startswith("/") or self.host in _LOCAL_HOSTS

    @property
    def display(self) -> str:
        """`host:port`, for messages."""
        return f"{self.host}:{self.port}"

    @property
    def required_sslmode(self) -> str | None:
        """The `sslmode` every connection must use, or None to leave libpq's default.

        A non-local host without `--allow-insecure` needs SSL before it
        authenticates: `PGSSLMODE` when it requires SSL, otherwise `require`.

        Raises:
            PreflightError: `PGSERVICE` is set without such a `PGSSLMODE`. A
                service file's `sslmode` overrides `PGSSLMODE`, and passing
                `require` would override a stricter one there.
        """
        if self.is_local or self.allow_insecure:
            return None
        configured = os.environ.get("PGSSLMODE", "")
        if configured in _SSL_REQUIRING_MODES:
            return configured
        if os.environ.get("PGSERVICE"):
            msg = (
                "PGSERVICE is set, and its service file may set an sslmode this "
                "tool cannot see. Set PGSSLMODE to match it (require, verify-ca, "
                "or verify-full), or unset PGSERVICE."
            )
            raise PreflightError(msg)
        return "require"


class Connector:
    """Opens connections to one server, remembering a prompted admin password."""

    def __init__(
        self, target: Target, prompt_password: Callable[[str], str] | None = None
    ) -> None:
        self.target = target
        self._prompt_password = prompt_password
        self._admin_password: str | None = None

    def connect(self, dbname: str) -> psycopg.Connection:
        """Connect as the admin, in autocommit mode.

        Raises:
            PreflightError: The connection failed or would not use SSL.
        """
        try:
            conn = self._open(self.target.admin_user, self._admin_password, dbname)
        except psycopg.OperationalError as exc:
            if not self._should_prompt(exc):
                raise self._connect_error(self.target.admin_user, dbname, exc) from exc
            prompt = f"Password for {self.target.admin_user}@{self.target.display}"
            self._admin_password = self._prompt_password(prompt)
            try:
                conn = self._open(self.target.admin_user, self._admin_password, dbname)
            except psycopg.OperationalError as retry_exc:
                raise self._connect_error(
                    self.target.admin_user, dbname, retry_exc
                ) from retry_exc
        self._require_tls(conn)
        return conn

    def connect_as(self, role: str, password: str, dbname: str) -> psycopg.Connection:
        """Connect as a provisioned role with its new password.

        Raises:
            PreflightError: The connection failed or would not use SSL.
        """
        try:
            conn = self._open(role, password, dbname)
        except psycopg.OperationalError as exc:
            raise self._connect_error(role, dbname, exc) from exc
        self._require_tls(conn)
        return conn

    def _open(self, user: str, password: str | None, dbname: str) -> psycopg.Connection:
        params: dict[str, str | int] = {
            "host": self.target.host,
            "port": self.target.port,
            "user": user,
            "dbname": dbname,
            "application_name": _APPLICATION_NAME,
            "connect_timeout": _CONNECT_TIMEOUT_SECONDS,
        }
        if password is not None:
            params["password"] = password
        sslmode = self.target.required_sslmode
        if sslmode is not None:
            params["sslmode"] = sslmode
        return psycopg.connect(autocommit=True, row_factory=namedtuple_row, **params)

    def _should_prompt(self, exc: psycopg.OperationalError) -> bool:
        return (
            self._prompt_password is not None
            and self._admin_password is None
            and _LIBPQ_MISSING_SECRET_ERROR in str(exc)
        )

    def _connect_error(
        self, user: str, dbname: str, exc: psycopg.OperationalError
    ) -> PreflightError:
        msg = (
            f"Cannot connect to database {dbname!r} on {self.target.display} "
            f"as {user!r}: {str(exc).strip()}"
        )
        return PreflightError(msg)

    def _require_tls(self, conn: psycopg.Connection) -> None:
        if self.target.is_local or self.target.allow_insecure:
            return
        if conn.pgconn.ssl_in_use:
            return
        conn.close()
        msg = (
            f"The connection to {self.target.display} is not using SSL. Set "
            "PGSSLMODE (for example `require` or `verify-full`), or pass "
            "--allow-insecure to proceed without it."
        )
        raise PreflightError(msg)


def ssl_description(conn: psycopg.Connection) -> str:
    """`TLSv1.3` or similar, or `off`."""
    row = conn.execute(catalog.SSL_VERSION).fetchone()
    return row.version if row and row.version else "off"


def url_sslmode(conn: psycopg.Connection, target: Target) -> str | None:
    """The `sslmode` a connection URL should carry, or None for local hosts.

    A URL never allows a plaintext fallback when provisioning used SSL.
    """
    if target.is_local:
        return None
    configured = os.environ.get("PGSSLMODE", "")
    if configured in _SSL_REQUIRING_MODES:
        return configured
    return "require" if conn.pgconn.ssl_in_use else configured or None


def connection_url(
    target: Target, role: str, password: str, dbname: str, sslmode: str | None
) -> str:
    """A libpq connection URL for one role, with every component percent-encoded."""
    userinfo = f"{quote(role, safe='')}:{quote(password, safe='')}"
    query: list[str] = []
    if target.host.startswith("/"):
        authority = f"{userinfo}@"
        query.extend([f"host={quote(target.host, safe='')}", f"port={target.port}"])
    else:
        host = f"[{target.host}]" if ":" in target.host else target.host
        authority = f"{userinfo}@{host}:{target.port}"
    if sslmode:
        query.append(f"sslmode={quote(sslmode, safe='')}")
    suffix = f"?{'&'.join(query)}" if query else ""
    return f"postgresql://{authority}/{quote(dbname, safe='')}{suffix}"
