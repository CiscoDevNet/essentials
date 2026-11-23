"""Print credentials to an interactive terminal, and nowhere else."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from ..exceptions import PreflightError
from .base import RoleSecret, SinkContext, render_env


class TerminalSink:
    """Prints credentials, but only when stdout is a TTY.

    Agents run without a TTY, so this refuses there and passwords never
    reach a transcript.
    """

    name = "terminal"

    def __init__(self, context: SinkContext) -> None:
        self.context = context

    def check(self) -> None:
        """Refuse unless stdout is an interactive terminal.

        Raises:
            PreflightError: stdout is not a TTY.
        """
        if not sys.stdout.isatty():
            msg = (
                "--sink terminal needs an interactive terminal, and stdout is not "
                "one. Use the default file sink instead."
            )
            raise PreflightError(msg)

    def deliver(self, secrets: Sequence[RoleSecret]) -> str:
        """Print the `.env` text to stdout."""
        sys.stdout.write(render_env(self.context, secrets))
        sys.stdout.flush()
        return "Credentials printed to the terminal above"
