"""Failure cooldown shared by the sync and async token helpers.

A denied token request is not cached, so without a cooldown the next caller
retries immediately. Where the token is fetched per outbound request -- for
example from an ``httpx`` event hook -- that turns one denial into one
upstream request per call.

That is a feedback loop rather than mere noise. Token endpoints commonly
rate-limit per source IP, and a whole Kubernetes cluster egresses through a
single NAT address, so retries escalate an intermittent denial into a
sustained one: the request rate climbs far above normal, denials come to
outnumber successes, and the endpoint can end up blocking the address
outright.

This is a circuit breaker, not a retry policy
---------------------------------------------
Nothing here sleeps, loops, or re-issues a request. A failure opens the
breaker; callers arriving while it is open fail fast without touching the
network, and the next caller after the window gets one attempt. That is the
opposite of ``tenacity``-style backoff, which keeps sending requests on a
schedule -- the behaviour this exists to stop.

The *window* does grow exponentially, which is where backoff genuinely
applies. A fixed window is weak during a sustained outage: at 60s, a 90-minute
block still admits ~90 attempts per event loop. Doubling to a cap of one hour
admits about 7 over the same period, while still recovering promptly from a
brief blip. Jitter keeps a fleet of pods that started together from
synchronising their probes.

There is no standard-library primitive for this, and pulling in a
circuit-breaker dependency is not worth it, so it is implemented here --
deliberately small.
"""

from __future__ import annotations

import os
import secrets
import threading
import time

_DEFAULT_COOLDOWN_SECS = 60.0
_DEFAULT_MAX_COOLDOWN_SECS = 3600.0
# Spread of the jitter applied to each window, as a fraction of its length.
_JITTER_FRACTION = 0.2


def _read_env_float(name: str, default: float) -> float:
    """Return a non-negative float from the environment, or *default*.

    Read from the environment so the windows can be retuned without a
    redeploy; consumers that roll a new release to change an environment
    variable pay a real cost for it.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


class FailureCooldown:
    """Tracks whether token requests are currently suppressed.

    The window doubles on each consecutive failure, from ``cooldown_secs`` up
    to ``max_cooldown_secs``, and resets on the first success.

    Thread-safe: the sync helper is called from worker threads and the async
    helper from event loops, and one instance may be shared by both.

    Parameters
    ----------
    cooldown_secs:
        First window, in seconds. Defaults to
        ``OAUTH_TOKEN_FAILURE_COOLDOWN_SECS`` or 60.
    max_cooldown_secs:
        Ceiling the window doubles towards. Defaults to
        ``OAUTH_TOKEN_FAILURE_MAX_COOLDOWN_SECS`` or 3600.
    """

    def __init__(
        self,
        cooldown_secs: float | None = None,
        max_cooldown_secs: float | None = None,
    ) -> None:
        self._base_secs = (
            _read_env_float("OAUTH_TOKEN_FAILURE_COOLDOWN_SECS", _DEFAULT_COOLDOWN_SECS)
            if cooldown_secs is None
            else cooldown_secs
        )
        self._max_secs = (
            _read_env_float(
                "OAUTH_TOKEN_FAILURE_MAX_COOLDOWN_SECS", _DEFAULT_MAX_COOLDOWN_SECS
            )
            if max_cooldown_secs is None
            else max_cooldown_secs
        )
        self._consecutive_failures = 0
        self._retry_not_before: float = 0.0
        self._lock = threading.Lock()

    @property
    def consecutive_failures(self) -> int:
        """Failures since the last success, for logging and tests."""
        with self._lock:
            return self._consecutive_failures

    def _window_for(self, failures: int) -> float:
        """Return the jittered window length after *failures* consecutive failures."""
        # Doubling is computed on the exponent rather than by repeated
        # multiplication so a long outage cannot drift the window.
        raw = self._base_secs * (2 ** max(0, failures - 1))
        window = min(raw, self._max_secs)
        # secrets rather than random: ruff flags the latter, and the quality
        # difference is irrelevant for jitter.
        jitter = (secrets.randbelow(1000) / 1000.0) * _JITTER_FRACTION
        return window * (1.0 + jitter)

    def remaining(self) -> float:
        """Return seconds left in the cooldown, or ``0.0`` when not cooling."""
        with self._lock:
            return max(0.0, self._retry_not_before - time.monotonic())

    def start(self) -> float:
        """Open (or re-open) the breaker after a failed token request.

        Returns:
            The window length just applied, in seconds.
        """
        with self._lock:
            self._consecutive_failures += 1
            window = self._window_for(self._consecutive_failures)
            self._retry_not_before = time.monotonic() + window
            return window

    def hold(self, seconds: float) -> None:
        """Suppress requests for at least *seconds* without counting a failure.

        Used when the upstream says how long to wait -- a rate-limit reset or
        ``Retry-After`` -- rather than when a request failed. An already
        longer window is kept, and escalation is left untouched so the next
        genuine failure still starts from where it would have.
        """
        if seconds <= 0:
            return
        with self._lock:
            self._retry_not_before = max(
                self._retry_not_before, time.monotonic() + seconds
            )

    def clear(self) -> None:
        """Close the breaker and reset escalation after a successful request."""
        with self._lock:
            self._consecutive_failures = 0
            self._retry_not_before = 0.0
