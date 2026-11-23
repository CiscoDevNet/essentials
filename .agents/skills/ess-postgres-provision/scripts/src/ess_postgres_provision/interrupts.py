"""Turn SIGTERM into an exception, and hold off interrupts during delivery.

Only `SIGKILL` can skip credential delivery once roles may be live.
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType

from .exceptions import EXIT_INTERRUPTED, EXIT_TERMINATED, Terminated


def _on_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


def _raise_terminated(_signum: int, _frame: FrameType | None) -> None:
    raise Terminated


@contextmanager
def sigterm_raises() -> Iterator[None]:
    """Raise `Terminated` on SIGTERM, so `except BaseException` and `finally` run."""
    if not _on_main_thread():
        yield
        return
    previous = signal.signal(signal.SIGTERM, _raise_terminated)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


@contextmanager
def interrupts_ignored() -> Iterator[None]:
    """Ignore SIGINT and SIGTERM until the block finishes."""
    if not _on_main_thread():
        yield
        return
    previous_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
    previous_term = signal.signal(signal.SIGTERM, signal.SIG_IGN)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)


def interrupt_exit_code(exc: BaseException) -> int | None:
    """130 for SIGINT, 143 for SIGTERM, None for anything else."""
    if isinstance(exc, KeyboardInterrupt):
        return EXIT_INTERRUPTED
    if isinstance(exc, Terminated):
        return EXIT_TERMINATED
    return None
