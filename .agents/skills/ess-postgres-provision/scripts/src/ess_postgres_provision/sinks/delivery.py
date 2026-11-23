"""Deliver to every sink, falling back to a `failed` file when one fails."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from ..exceptions import DeliveryError
from .base import RoleSecret, SecretSink

logger = logging.getLogger(__name__)


@dataclass
class DeliveryReport:
    """What each sink reported.

    Attributes:
        messages: One line per sink that received the credentials.
        failures: One line per sink that did not.
    """

    messages: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def deliver(
    sinks: Sequence[SecretSink],
    secrets: Sequence[RoleSecret],
    fallback: Callable[[], SecretSink],
) -> DeliveryReport:
    """Check and deliver to each sink; if any fails, also write the fallback file.

    Raises:
        DeliveryError: No sink received the credentials, the fallback included.
    """
    report = DeliveryReport()
    for sink in sinks:
        _deliver_one(sink, secrets, report)
    if report.failures:
        try:
            backup = fallback()
            backup.check()
            report.messages.append(backup.deliver(secrets))
        except Exception as exc:
            logger.exception("Fallback credential file failed")
            report.failures.append(f"fallback file: {exc}")
    if not report.messages:
        msg = (
            "No sink received the new credentials, the fallback file included "
            f"({'; '.join(report.failures)}). The passwords are lost: run rotate "
            "to issue new ones."
        )
        raise DeliveryError(msg)
    return report


def _deliver_one(
    sink: SecretSink, secrets: Sequence[RoleSecret], report: DeliveryReport
) -> None:
    try:
        sink.check()
        report.messages.append(sink.deliver(secrets))
    except Exception as exc:
        logger.exception("Sink %s failed", sink.name)
        report.failures.append(f"{sink.name}: {exc}")
