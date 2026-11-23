"""The sink protocol and the values every sink receives."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class Outcome(StrEnum):
    """Why credentials are being delivered."""

    CREATED = "created"
    ROTATED = "rotated"
    FAILED = "failed"


@dataclass(frozen=True)
class RoleSecret:
    """One role's new credential.

    Attributes:
        kind: `owner`, `migrations`, `app`, or `reader`.
        role: The role name.
        password: The plaintext password. Never logged or shown in a repr.
        url: A connection URL embedding the password.
        entropy_bits: Strength of the scheme that generated the password.
    """

    kind: str
    role: str
    password: str = field(repr=False)
    url: str = field(repr=False)
    entropy_bits: float = 0.0


@dataclass(frozen=True)
class SinkContext:
    """What a sink needs to know about the run it delivers for.

    Attributes:
        base: The base name.
        host: The server host, used to group credential files.
        target: `host:port`, for headers.
        run_id: The run ID, for headers.
        outcome: Why the credentials are being delivered.
        timestamp: When the run started, in UTC.
        path: An explicit destination from `--sink-path`, for the file sink.
        notes: Extra header lines, such as which earlier lines are stale.
    """

    base: str
    host: str
    target: str
    run_id: str
    outcome: Outcome
    timestamp: datetime
    path: Path | None = None
    notes: tuple[str, ...] = ()


class SecretSink(Protocol):
    """Somewhere credentials can be delivered."""

    name: str

    def check(self) -> None:
        """Refuse early, raising `PreflightError`, if delivery cannot succeed."""

    def deliver(self, secrets: Sequence[RoleSecret]) -> str:
        """Deliver the credentials and return one line for the operator."""


def env_names(base: str, kind: str) -> tuple[str, str]:
    """The password and URL variable names for one role, e.g. `BILLING_APP_...`."""
    prefix = f"{base}_{kind}".upper()
    return f"{prefix}_DATABASE_PASSWORD", f"{prefix}_DATABASE_URL"


def render_env(context: SinkContext, secrets: Sequence[RoleSecret]) -> str:
    """The `.env` text every sink writes: a header, then two lines per role."""
    stamp = context.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"# ess-postgres-provision: {context.base} on {context.target}",
        f"# Run {context.run_id}, {context.outcome.value} {stamp}",
    ]
    if context.outcome is Outcome.FAILED:
        lines.append(
            "# FAILED RUN: these roles may or may not exist. Run teardown before "
            "relying on them."
        )
    lines.extend(f"# {note}" for note in context.notes)
    for secret in secrets:
        password_name, url_name = env_names(context.base, secret.kind)
        lines.append(f"{password_name}={secret.password}")
        lines.append(f"{url_name}={secret.url}")
    return "\n".join(lines) + "\n"
