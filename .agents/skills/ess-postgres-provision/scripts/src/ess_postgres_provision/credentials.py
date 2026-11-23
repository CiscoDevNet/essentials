"""Run the writes, then deliver the new credentials whatever happens.

Once a transaction that sets passwords may have committed, the passwords
may be live. From then on every failure, interrupt included, still delivers
them, labelled as from a failed run.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .connection import Target, connection_url
from .exceptions import (
    DeliveryError,
    InterruptedRunError,
    ProvisioningError,
    VerificationError,
)
from .interrupts import interrupt_exit_code, interrupts_ignored, sigterm_raises
from .naming import Names
from .passwords import RolePassword
from .sinks import (
    DeliveryReport,
    RoleSecret,
    SecretSink,
    SinkContext,
    deliver,
    fallback_sink,
)


@dataclass
class LiveFlag:
    """Set just before the commit that may make new passwords live."""

    may_be_live: bool = False

    def mark(self) -> None:
        """Record that the passwords may now be live."""
        self.may_be_live = True


@dataclass(frozen=True)
class Delivery:
    """Where one run's credentials go, on success and on failure.

    Attributes:
        sinks: The configured sinks, already checked.
        failed_sinks: The sinks for a failed run, from `build_failed_sinks`,
            already checked.
        context: The run being delivered.
        recovery: The command to print if the run fails.
    """

    sinks: Sequence[SecretSink]
    failed_sinks: Sequence[SecretSink]
    context: SinkContext
    recovery: str


def role_secrets(
    passwords: Mapping[str, RolePassword],
    target: Target,
    names: Names,
    sslmode: str | None,
) -> list[RoleSecret]:
    """The credentials to deliver, with a connection URL for each role."""
    return [
        RoleSecret(
            kind=kind,
            role=password.role,
            password=password.password,
            url=connection_url(
                target, password.role, password.password, names.database, sslmode
            ),
            entropy_bits=password.entropy_bits,
        )
        for kind, password in passwords.items()
    ]


def run_and_deliver(
    work: Callable[[LiveFlag], None],
    secrets: Sequence[RoleSecret],
    delivery: Delivery,
) -> DeliveryReport:
    """Run `work`, then deliver; on a failure after `mark()`, deliver anyway.

    Raises:
        DeliveryError: No sink received the credentials (exit 4).
        InterruptedRunError: SIGINT or SIGTERM after the passwords may be live.
        ProvisioningError: Any other failure after they may be live.
        VerificationError: Verification failed after they may be live.
    """
    flag = LiveFlag()
    with sigterm_raises():
        try:
            work(flag)
            with interrupts_ignored():
                return deliver(
                    delivery.sinks, secrets, lambda: fallback_sink(delivery.context)
                )
        except BaseException as exc:
            if not flag.may_be_live or isinstance(exc, DeliveryError):
                raise
            with interrupts_ignored():
                report = deliver(
                    delivery.failed_sinks,
                    secrets,
                    lambda: fallback_sink(delivery.context),
                )
            raise _failed_run_error(exc, report, delivery.recovery) from exc


def _failed_run_error(
    exc: BaseException, report: DeliveryReport, recovery: str
) -> ProvisioningError | VerificationError:
    code = interrupt_exit_code(exc)
    reason = "Interrupted" if code is not None else str(exc)
    msg = (
        f"{reason}\n"
        f"Credentials from this failed run: {'; '.join(report.messages)}.\n"
        f"Recover with: {recovery}"
    )
    if code is not None:
        return InterruptedRunError(msg, code)
    if isinstance(exc, VerificationError):
        return VerificationError(msg)
    return ProvisioningError(msg)
