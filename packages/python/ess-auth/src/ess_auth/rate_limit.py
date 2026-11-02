"""Rate-limit awareness from HTTP response headers, for any API caller.

Many identity platforms report their remaining budget on every response,
success or failure::

    X-Rate-Limit-Limit: 60          # ceiling for this client/IP/device window
    X-Rate-Limit-Remaining: 35      # requests left in the current window
    X-Rate-Limit-Reset: 1516307596  # UTC epoch second the window resets

The quota is often counted per source identity, and a whole Kubernetes
cluster egresses through one NAT address, so ``Remaining`` reflects what the
*fleet* has spent, not one pod. Reading it lets every pod stop before the
shared budget runs out instead of discovering the limit by being refused --
and sustained refusals are what earn a shared egress address a reputation
block at the edge.

Nothing here performs I/O. Callers parse the headers they already received
and feed :func:`rate_limit_hold_secs` into their own
:class:`~ess_auth.cooldown.FailureCooldown` via ``hold()``, so the same policy
applies to the token helpers and to any other HTTP client that wants it.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from http import HTTPStatus

# Okta's spelling first; the hyphen-less variant is common elsewhere.
_LIMIT_HEADERS = ("x-rate-limit-limit", "x-ratelimit-limit")
_REMAINING_HEADERS = ("x-rate-limit-remaining", "x-ratelimit-remaining")
_RESET_HEADERS = ("x-rate-limit-reset", "x-ratelimit-reset")

# Headers worth keeping when a request fails. Identity-platform support will
# ask for a request or reference ID before it looks at a denial; without one,
# an escalation turns into days of exchanging evidence. Credentials and
# cookies are deliberately absent.
DIAGNOSTIC_HEADERS: tuple[str, ...] = (
    "x-okta-request-id",
    "x-request-id",
    "x-correlation-id",
    "akamai-grn",
    "x-akamai-request-id",
    "x-reference-error",
    "server-timing",
    *_LIMIT_HEADERS,
    *_REMAINING_HEADERS,
    *_RESET_HEADERS,
    "retry-after",
)
_DIAGNOSTIC_VALUE_MAX_CHARS = 200

_DEFAULT_RESERVE_FRACTION = 0.1
_DEFAULT_MAX_HOLD_SECS = 3600.0


def _read_env_fraction(name: str, default: float) -> float:
    """Return a fraction in ``[0, 1)`` from the environment, or *default*."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if 0.0 <= value < 1.0 else default


@dataclass(frozen=True)
class RateLimitStatus:
    """Budget reported by one response. Any field may be absent."""

    limit: int | None = None
    remaining: int | None = None
    reset_epoch: float | None = None
    retry_after_secs: float | None = None

    def is_reported(self) -> bool:
        """Whether the response carried any rate-limit information at all."""
        return any(
            value is not None
            for value in (
                self.limit,
                self.remaining,
                self.reset_epoch,
                self.retry_after_secs,
            )
        )


def _first_header(headers: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = headers.get(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _parse_finite(raw: str) -> float | None:
    """Parse *raw* as a finite float; ``inf``/``nan``/overflow are malformed."""
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = _parse_finite(raw)
    if value is None or value < 0:
        return None
    return int(value)


def _parse_retry_after(raw: str | None, now_epoch: float) -> float | None:
    """Parse ``Retry-After`` as delta-seconds or an HTTP date."""
    if raw is None:
        return None
    seconds = _parse_finite(raw)
    if seconds is not None:
        return max(0.0, seconds)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    return max(0.0, when.timestamp() - now_epoch)


def parse_rate_limit_headers(
    headers: Mapping[str, str], *, now_epoch: float | None = None
) -> RateLimitStatus:
    """Return the rate-limit budget described by *headers*.

    Args:
        headers: Response headers. ``httpx.Headers`` is case-insensitive; a
            plain dict must use lower-case names.
        now_epoch: Current UTC epoch seconds, for tests. Defaults to now.

    Returns:
        A status whose fields are ``None`` where a header was missing or
        unparseable. Never raises on malformed values.
    """
    now = time.time() if now_epoch is None else now_epoch
    reset = _parse_int(_first_header(headers, _RESET_HEADERS))
    return RateLimitStatus(
        limit=_parse_int(_first_header(headers, _LIMIT_HEADERS)),
        remaining=_parse_int(_first_header(headers, _REMAINING_HEADERS)),
        reset_epoch=float(reset) if reset is not None else None,
        retry_after_secs=_parse_retry_after(headers.get("retry-after"), now),
    )


def _reserve_for(limit: int, reserve_fraction: float) -> int:
    """Requests to keep in hand: at least one, else a fraction of the limit."""
    return max(1, math.ceil(limit * reserve_fraction))


def rate_limit_hold_secs(
    status: RateLimitStatus,
    *,
    status_code: int,
    now_epoch: float | None = None,
    reserve_fraction: float | None = None,
    max_hold_secs: float = _DEFAULT_MAX_HOLD_SECS,
) -> float:
    """Return how long to stop calling an API after this response.

    Two cases suppress further calls:

    * **Refused for rate.** On HTTP 429, wait for the longer of the time
      until the window resets and ``Retry-After``.
    * **Nearly exhausted.** On any status, when ``Remaining`` has fallen to
      the reserve, wait until the window resets. The reserve is
      ``API_RATE_LIMIT_RESERVE_FRACTION`` of the limit (default 10%), and
      never less than one request.

    Args:
        status: Parsed headers from :func:`parse_rate_limit_headers`.
        status_code: HTTP status of the response.
        now_epoch: Current UTC epoch seconds, for tests. Defaults to now.
        reserve_fraction: Override the reserve fraction.
        max_hold_secs: Ceiling on the returned hold, so a bogus reset time
            cannot park a caller indefinitely.

    Returns:
        Seconds to suppress calls, ``0.0`` when nothing suggests waiting.
    """
    now = time.time() if now_epoch is None else now_epoch
    until_reset = (
        max(0.0, status.reset_epoch - now) if status.reset_epoch is not None else None
    )
    fraction = (
        _read_env_fraction("API_RATE_LIMIT_RESERVE_FRACTION", _DEFAULT_RESERVE_FRACTION)
        if reserve_fraction is None
        else reserve_fraction
    )

    hold = 0.0
    if status_code == HTTPStatus.TOO_MANY_REQUESTS:
        # The longer of the two: a reset that is stale or skewed into the past
        # must not cancel an explicit Retry-After.
        hold = max(until_reset or 0.0, status.retry_after_secs or 0.0)
    elif (
        status.remaining is not None
        and status.limit
        and status.remaining <= _reserve_for(status.limit, fraction)
        and until_reset is not None
    ):
        hold = until_reset
    return min(hold, max_hold_secs)


def diagnostic_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Return the request-ID and rate-limit headers worth logging.

    Only names in :data:`DIAGNOSTIC_HEADERS` are copied, so credentials,
    cookies, and tokens can never leak through this path. Values are
    truncated to keep log lines bounded.
    """
    found: dict[str, str] = {}
    for name in DIAGNOSTIC_HEADERS:
        value = headers.get(name)
        if value:
            found[name] = value[:_DIAGNOSTIC_VALUE_MAX_CHARS]
    return found
