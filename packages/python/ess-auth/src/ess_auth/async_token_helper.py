"""Async OAuth2 client-credentials token helper.

The async counterpart to :class:`ess_auth.TokenHelper`, for callers running
under an event loop. It exists separately rather than as an ``async`` method
on the sync helper because it needs per-event-loop lock state that has no
meaning in synchronous code.

Why the per-loop locks
----------------------
An ``asyncio.Lock`` binds to the running event loop the first time a coroutine
has to *wait* on a held lock (uncontended acquire/release never reaches that
path, which is why this only surfaces under concurrent refreshes). Frameworks
that create a fresh loop per request -- LangGraph among them -- leave a token
helper cached at module scope outliving the loop it first ran on, so once
contention has bound a shared lock to one loop, a second loop's contended
acquire raises::

    RuntimeError: <asyncio.locks.Lock object ...> is bound to a different event loop

This helper therefore caches one lock per running loop in a
``WeakKeyDictionary``. The values are weak references to the locks rather than
the locks themselves: once bound, a lock holds a *strong* reference to its
loop, and a strong value pointing back at its own weak key pins that key
forever, so the cache would grow with every request loop instead of shrinking.
A lock survives for as long as a caller is inside its ``async with``, which is
the only window where lock identity matters. Entries whose loop has been
closed are dropped on access so eviction does not wait for a collection cycle.

An ``id()``-keyed dict would be unsafe because CPython reuses ``id`` values
after a loop is garbage collected.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import weakref
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from .client_identity import client_identity_headers
from .config import EXPIRATION_WINDOW
from .cooldown import FailureCooldown
from .rate_limit import diagnostic_headers
from .token_helper import (
    MIN_CACHE_LIFETIME_SECS,
    STALE_TOKEN_SAFETY_SECS,
    TokenEndpointCoolingDownError,
    TokenRequestFailedError,
    apply_rate_limit_headers,
    error_detail,
    parse_access_token,
    parse_expires_in,
)

logger = logging.getLogger(__name__)

# Bounds lock wait plus network so a hung endpoint cannot stall a backlog of
# queued callers indefinitely.
_DEFAULT_TOTAL_TIMEOUT_SECS = 35.0
_DEFAULT_REQUEST_TIMEOUT_SECS = 30.0


@dataclass(frozen=True)
class TokenClientOptions:
    """Optional behaviour for a token helper.

    Grouped into one object so the constructor stays readable as the number
    of knobs grows.

    Attributes
    ----------
    refresh_margin:
        Seconds before expiry to trigger a proactive refresh.
    scope:
        OAuth2 scope, sent only when non-empty. Authorization servers differ
        on whether an empty ``scope`` is acceptable.
    credentials_in_body:
        Send ``client_id``/``client_secret`` as form fields instead of HTTP
        Basic auth. Both are valid client authentication methods and servers
        differ on which they accept, so this is explicit rather than assumed.
    cooldown_secs:
        Override the failure cooldown window. See :mod:`ess_auth.cooldown`.
    label:
        Short name distinguishing this helper in log lines.
    request_headers:
        Extra headers for the token POST. ``None`` (the default) sends the
        identification header configured in the environment; see
        :mod:`ess_auth.client_identity`.

    Notes
    -----
    The cooldown bounds attempts **per event loop**, not per process. The
    locks are per-loop by necessity (an ``asyncio.Lock`` cannot be shared
    across loops), so callers on different loops can pass the cooldown check
    concurrently before the first failure records it. The worst case is one
    in-flight attempt per live loop per window rather than a strict one, which
    still collapses the per-request amplification this exists to stop. Making
    it strict would need process-wide coordination that blocks event loops, so
    it is deliberately not done here.
    """

    refresh_margin: int = EXPIRATION_WINDOW
    scope: str = ""
    credentials_in_body: bool = False
    cooldown_secs: float | None = None
    label: str = "OAuth"
    request_headers: Mapping[str, str] | None = None


class AsyncTokenHelper:
    """Manages OAuth2 client-credentials tokens for async callers.

    Uses ``threading.Lock`` for the cache read and token write (both
    instantaneous) and a per-loop ``asyncio.Lock`` to serialise refreshes, so
    waiting callers yield the event loop rather than blocking a thread.

    A token is refreshed ``refresh_margin`` seconds early. If that refresh
    fails or is suppressed, the cached token keeps being served until it
    actually expires, so one failed refresh never costs a still-valid token.
    Rate-limit headers on any token response extend the cooldown; see
    :mod:`ess_auth.rate_limit`.

    Parameters
    ----------
    client_id:
        OAuth2 client ID.
    secret:
        OAuth2 client secret.
    token_url:
        Token endpoint URL.
    options:
        Optional behaviour; see :class:`TokenClientOptions`.
    """

    def __init__(
        self,
        client_id: str,
        secret: str,
        *,
        token_url: str,
        options: TokenClientOptions | None = None,
    ) -> None:
        opts = options or TokenClientOptions()
        self._client_id = client_id
        self._secret = secret
        self._token_url = token_url
        self._refresh_margin = opts.refresh_margin
        self._scope = opts.scope
        self._credentials_in_body = opts.credentials_in_body
        self._label = opts.label
        self._request_headers = dict(
            client_identity_headers()
            if opts.request_headers is None
            else opts.request_headers
        )
        self._cooldown = FailureCooldown(opts.cooldown_secs)

        self._access_token: str | None = None
        # ``_expires_at`` is when to refresh; ``_valid_until`` is when the
        # token actually dies, which bounds how long a stale one is served.
        self._expires_at: float = 0.0
        self._valid_until: float = 0.0
        self._lock = threading.Lock()
        self._async_locks: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, weakref.ref[asyncio.Lock]
        ] = weakref.WeakKeyDictionary()

    @property
    def scope(self) -> str:
        """The configured OAuth2 scope, empty when unscoped."""
        return self._scope

    @property
    def token_url(self) -> str:
        """The token endpoint URL, for caller-side diagnostics."""
        return self._token_url

    @property
    def label(self) -> str:
        """Short name distinguishing this helper in caller logs."""
        return self._label

    def _evict_closed_loops(self) -> None:
        """Drop cache entries whose loop has been closed.

        Callers must hold ``self._lock``.
        """
        closed = [loop for loop in self._async_locks if loop.is_closed()]
        for loop in closed:
            del self._async_locks[loop]

    def _get_async_lock(self) -> asyncio.Lock:
        """Return the ``asyncio.Lock`` bound to the running loop.

        The caller must keep the returned lock referenced for as long as it
        needs it; the cache holds it weakly. See the module docstring.
        """
        loop = asyncio.get_running_loop()
        with self._lock:
            self._evict_closed_loops()
            cached = self._async_locks.get(loop)
            lock = cached() if cached is not None else None
            if lock is None:
                lock = asyncio.Lock()
                self._async_locks[loop] = weakref.ref(lock)
            return lock

    def _cached_token(self) -> str | None:
        """Return the cached token when it is still inside its refresh window."""
        with self._lock:
            if self._access_token and time.monotonic() < self._expires_at:
                return self._access_token
        return None

    def _stale_token(self) -> str | None:
        """Return the cached token if it outlives a failed or suppressed refresh."""
        with self._lock:
            token = self._access_token
            valid_for = self._valid_until - time.monotonic()
        if token is None or valid_for <= STALE_TOKEN_SAFETY_SECS:
            return None
        logger.warning(
            "OAUTH_TOKEN_STALE_SERVED label=%s valid_for_s=%.0f token_url=%s",
            self._label,
            valid_for,
            self._token_url,
        )
        return token

    async def fetch_token(self) -> str:
        """Return a valid access token, refreshing if necessary.

        Raises
        ------
        TokenEndpointCoolingDownError
            When a recent failure is still suppressing requests.
        TokenRequestFailedError
            When the token endpoint rejects or fails the request.
        """
        cached = self._cached_token()
        if cached is not None:
            return cached
        return await self.refresh()

    async def refresh(self) -> str:
        """Perform the client-credentials grant and cache the result."""
        try:
            return await asyncio.wait_for(
                self._refresh_locked(), timeout=_DEFAULT_TOTAL_TIMEOUT_SECS
            )
        except TimeoutError as exc:
            logger.warning(
                "%s token refresh exceeded %ss; abandoning attempt",
                self._label,
                _DEFAULT_TOTAL_TIMEOUT_SECS,
            )
            # ``wait_for`` fires outside ``_do_refresh``, so without this the
            # breaker stays closed and the next caller immediately starts a
            # fresh attempt against an endpoint already known to be stuck --
            # the amplification path this class exists to close. Re-raised as
            # the documented failure type so a hang reaches callers as an
            # ``AuthenticationError`` like every other token failure.
            self._log_cooldown()
            stale = self._stale_token()
            if stale is not None:
                return stale
            raise TokenRequestFailedError(
                f"{self._label} token refresh exceeded "
                f"{_DEFAULT_TOTAL_TIMEOUT_SECS:.0f}s"
            ) from exc

    async def _refresh_locked(self) -> str:
        async with self._get_async_lock():
            # Re-check: a concurrent caller may have refreshed while we waited.
            cached = self._cached_token()
            if cached is not None:
                return cached

            cooling_for = self._cooldown.remaining()
            if cooling_for > 0:
                stale = self._stale_token()
                if stale is not None:
                    return stale
                raise TokenEndpointCoolingDownError(
                    f"{self._label} token endpoint is cooling down for "
                    f"{cooling_for:.0f}s after a recent failure; not retrying "
                    f"({self._token_url})"
                )

            try:
                return await self._do_refresh()
            except TokenRequestFailedError:
                stale = self._stale_token()
                if stale is None:
                    raise
                return stale

    def _build_request_kwargs(self) -> dict:
        """Return the form data and auth for the token POST."""
        data = {"grant_type": "client_credentials"}
        if self._scope:
            data["scope"] = self._scope
        if self._credentials_in_body:
            data["client_id"] = self._client_id
            data["client_secret"] = self._secret
            return {"data": data}
        return {"data": data, "auth": (self._client_id, self._secret)}

    def _log_cooldown(self, response: httpx.Response | None = None) -> None:
        """Open the breaker and record the window, which grows per failure.

        When the failed *response* is available, its rate-limit headers can
        extend the window and its request-ID headers are logged.
        """
        window = self._cooldown.start()
        diagnostics: dict[str, str] = {}
        status: int | str = "none"
        if response is not None:
            apply_rate_limit_headers(self._cooldown, response, label=self._label)
            diagnostics = diagnostic_headers(response.headers)
            status = response.status_code
        # One line per failed attempt, including ones absorbed by serving a
        # stale token, so this is the authoritative denial count.
        logger.warning(
            "OAUTH_TOKEN_COOLDOWN label=%s status=%s consecutive_failures=%d "
            "window_s=%.0f token_url=%s diagnostics=%s",
            self._label,
            status,
            self._cooldown.consecutive_failures,
            window,
            self._token_url,
            diagnostics,
        )

    async def _do_refresh(self) -> str:
        """Execute the token request, starting the cooldown on any failure."""
        try:
            async with httpx.AsyncClient(
                timeout=_DEFAULT_REQUEST_TIMEOUT_SECS
            ) as client:
                response = await client.post(
                    self._token_url,
                    headers=self._request_headers,
                    **self._build_request_kwargs(),
                )
                response.raise_for_status()
                payload = response.json()
                access_token = parse_access_token(payload)
                expires_in = parse_expires_in(payload)
        except httpx.HTTPStatusError as exc:
            self._log_cooldown(exc.response)
            raise TokenRequestFailedError(
                f"{self._label} token request failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                detail=error_detail(exc.response),
                diagnostics=diagnostic_headers(exc.response.headers),
            ) from exc
        except httpx.HTTPError as exc:
            self._log_cooldown()
            raise TokenRequestFailedError(
                f"{self._label} token request failed: {exc}"
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            # A malformed body would otherwise retry as hard as a denial.
            # Carry status and detail like the HTTP paths do: a 2xx with an
            # unusable body is exactly the case where a caller logging
            # status=None and an empty detail has nothing to go on.
            self._log_cooldown(response)
            raise TokenRequestFailedError(
                f"{self._label} token response was not usable: {exc}",
                status_code=response.status_code,
                detail=error_detail(response),
                diagnostics=diagnostic_headers(response.headers),
            ) from exc

        now = time.monotonic()
        with self._lock:
            self._access_token = access_token
            self._expires_at = now + max(
                expires_in - self._refresh_margin, MIN_CACHE_LIFETIME_SECS
            )
            self._valid_until = now + expires_in
        self._cooldown.clear()
        # After clear(): a granted token can still report a nearly spent
        # shared budget, and the hold must survive the reset.
        apply_rate_limit_headers(self._cooldown, response, label=self._label)

        logger.info("%s token refreshed (expires_in=%ds)", self._label, expires_in)
        return access_token
