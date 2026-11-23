"""What each subcommand was asked to do, bundled for the run functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .naming import ROLE_KINDS
from .passwords import DEFAULT_DIGITS
from .sql.database import ReaderGuards


@dataclass(frozen=True)
class DeliveryOptions:
    """Where new credentials go.

    Attributes:
        sink_names: `--sink` values; empty means the default file sink.
        sink_paths: `--sink-path` values, each a file sink of its own.
        digits: Digits appended to each generated password.
    """

    sink_names: tuple[str, ...] = ()
    sink_paths: tuple[Path, ...] = ()
    digits: int = DEFAULT_DIGITS


@dataclass(frozen=True)
class CreateOptions:
    """`create` inputs beyond the base name and target."""

    extensions: tuple[str, ...] = ()
    guards: ReaderGuards = field(default_factory=ReaderGuards)
    delivery: DeliveryOptions = field(default_factory=DeliveryOptions)


@dataclass(frozen=True)
class RotateOptions:
    """`rotate` inputs: which role kinds, and where the new passwords go."""

    kinds: tuple[str, ...] = ROLE_KINDS
    delivery: DeliveryOptions = field(default_factory=DeliveryOptions)


@dataclass(frozen=True)
class TeardownOptions:
    """`teardown` inputs.

    Attributes:
        terminate_sessions: End other sessions on the database instead of refusing.
    """

    terminate_sessions: bool = False


@dataclass(frozen=True)
class VerifyOptions:
    """What `verify` should expect beyond the fixed layout."""

    extensions: tuple[str, ...] = ()
    reader_read_only: bool = True
