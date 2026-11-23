"""Validate a base name and derive the database, schema, and role names from it."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .exceptions import InvalidNameError

ROLE_KINDS = ("owner", "migrations", "app", "reader")

MARKER_TOOL = "ess-postgres-provision"

# The longest suffix is "_migrations" (11 bytes); 41 + 11 stays under 63.
_BASE_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,40}")
_RESERVED_NAMES = frozenset(
    {"public", "postgres", "template0", "template1", "information_schema"}
)
_RUN_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True)
class Names:
    """Every name derived from one base name.

    Attributes:
        base: The validated base name, which is also the database and schema.
    """

    base: str

    @property
    def database(self) -> str:
        """The database name."""
        return self.base

    @property
    def schema(self) -> str:
        """The dedicated schema that holds the application's tables."""
        return self.base

    @property
    def owner(self) -> str:
        """Owns the database and schema."""
        return self.role("owner")

    @property
    def migrations(self) -> str:
        """Creates and owns every table."""
        return self.role("migrations")

    @property
    def app(self) -> str:
        """Reads and writes rows."""
        return self.role("app")

    @property
    def reader(self) -> str:
        """Reads rows."""
        return self.role("reader")

    @property
    def roles(self) -> tuple[str, ...]:
        """All four role names, in `ROLE_KINDS` order."""
        return tuple(self.role(kind) for kind in ROLE_KINDS)

    def role(self, kind: str) -> str:
        """The role name for one of `ROLE_KINDS`."""
        if kind not in ROLE_KINDS:
            msg = (
                f"Unknown role kind {kind!r}; expected one of {', '.join(ROLE_KINDS)}."
            )
            raise ValueError(msg)
        return f"{self.base}_{kind}"

    def kind_of(self, role: str) -> str:
        """The kind of one of the four derived role names."""
        for kind in ROLE_KINDS:
            if self.role(kind) == role:
                return kind
        msg = f"{role!r} is not a role derived from {self.base!r}."
        raise ValueError(msg)

    def marker(self, run_id: str) -> str:
        """The provenance comment stamped on every role of one run."""
        return f"{MARKER_TOOL}:{self.base}:{run_id}"

    def run_id_from_marker(self, comment: str | None) -> str | None:
        """The run ID in a role comment, or None if it is not this base's marker."""
        if comment is None:
            return None
        prefix = f"{MARKER_TOOL}:{self.base}:"
        if not comment.startswith(prefix):
            return None
        run_id = comment.removeprefix(prefix)
        return run_id if _RUN_ID_PATTERN.fullmatch(run_id) else None


def derive_names(base: str) -> Names:
    """Validate `base` and derive every name from it.

    Args:
        base: Lowercase letters, digits, and underscores, starting with a
            letter, at most 41 characters.

    Returns:
        The derived names.

    Raises:
        InvalidNameError: The name does not match the pattern, is reserved,
            or starts with `pg_`.
    """
    if not _BASE_NAME_PATTERN.fullmatch(base):
        msg = (
            f"{base!r} is not a valid base name: use 1 to 41 lowercase letters, "
            "digits, and underscores, starting with a letter."
        )
        raise InvalidNameError(msg)
    if base in _RESERVED_NAMES or base.startswith("pg_"):
        msg = f"{base!r} is reserved by PostgreSQL; choose another base name."
        raise InvalidNameError(msg)
    return Names(base)
