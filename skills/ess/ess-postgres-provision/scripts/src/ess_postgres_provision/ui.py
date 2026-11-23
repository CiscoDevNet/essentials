"""How the run functions talk to the operator, without depending on Click."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Ui:
    """Output and consent, supplied by the CLI.

    Attributes:
        echo: Writes a line to stdout: rendered SQL, tables, results.
        note: Writes a line to stderr: headers and progress.
        confirm: Asks before a write; raises to abort.
        dry_run: Stop after rendering, before any write.
    """

    echo: Callable[[str], None]
    note: Callable[[str], None]
    confirm: Callable[[str], None]
    dry_run: bool = False
