"""Domain exceptions, each carrying the exit code the CLI reports for it."""

from __future__ import annotations

import signal

EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_UNDELIVERED = 4
EXIT_INTERRUPTED = 128 + signal.SIGINT
EXIT_TERMINATED = 128 + signal.SIGTERM


class ProvisionError(Exception):
    """Base class for every error raised by this package."""

    exit_code = EXIT_FAILED


class InvalidNameError(ProvisionError):
    """The base name cannot be used to derive a database, schema, and roles."""

    exit_code = EXIT_USAGE


class PreflightError(ProvisionError):
    """A preflight or safety check refused the run before anything was written."""

    exit_code = EXIT_REFUSED


class ProvisioningError(ProvisionError):
    """A write failed after credentials may already be live."""


class VerificationError(ProvisionError):
    """The catalog or a login does not match what was provisioned."""


class DeliveryError(ProvisionError):
    """No sink, the fallback file included, received the credentials."""

    exit_code = EXIT_UNDELIVERED


class InterruptedRunError(ProvisioningError):
    """SIGINT or SIGTERM arrived after credentials may already be live."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class Terminated(BaseException):  # noqa: N818 -- mirrors KeyboardInterrupt, not an error
    """Raised by the SIGTERM handler so `finally` blocks and delivery still run."""
