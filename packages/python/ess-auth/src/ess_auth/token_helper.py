"""OAuth2 Client Credentials token helper with automatic caching and refresh."""

from __future__ import annotations

import logging
import threading
import time

import httpx

from .client_identity import client_identity_headers
from .config import EXPIRATION_WINDOW
from .cooldown import FailureCooldown
from .rate_limit import (
    diagnostic_headers,
    parse_rate_limit_headers,
    rate_limit_hold_secs,
)

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when a token request fails."""


class TokenEndpointCoolingDownError(AuthenticationError):
    """Raised when a token request is suppressed after a recent failure.

    Distinct from a live rejection so callers can tell "we did not ask" from
    "we asked and were refused". Consumers that must not crash on this should
    catch it explicitly; see ``ess_auth.cooldown`` for why the suppression
    exists.
    """


class TokenRequestFailedError(AuthenticationError):
    """Raised when the token endpoint rejects or fails a request.

    Carries the HTTP status and a short response excerpt so callers can log
    their own context-rich diagnostics without re-reading the response.

    Attributes
    ----------
    status_code:
        HTTP status returned by the token endpoint, when there was one.
    detail:
        Truncated response body, useful for distinguishing an OAuth JSON
        error from an HTML denial emitted by an edge proxy.
    diagnostics:
        Request-ID and rate-limit response headers (see
        :data:`ess_auth.rate_limit.DIAGNOSTIC_HEADERS`). Identity-platform
        support needs the request ID to trace a denial.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: str = "",
        diagnostics: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.diagnostics = diagnostics or {}


# Cap on token-endpoint error text copied into exceptions and logs.
_ERROR_DETAIL_MAX_CHARS = 300

# Floor on how long a freshly issued token stays cached. Subtracting the
# refresh margin from a token whose lifetime is at or below that margin would
# otherwise place the expiry at or before now, so every caller would refresh
# on every call -- the per-request amplification the cooldown exists to stop,
# reintroduced through the cache. Shared with the async helper.
MIN_CACHE_LIFETIME_SECS = 1.0

# A cached token is refreshed ``refresh_margin`` seconds before it expires.
# When that refresh fails, the old token is still good until real expiry and
# is served instead of failing the caller. This margin keeps a token from
# being handed out so close to expiry that it dies in flight.
STALE_TOKEN_SAFETY_SECS = 5.0


def apply_rate_limit_headers(
    cooldown: FailureCooldown, response: httpx.Response, *, label: str
) -> None:
    """Suppress further token requests when *response* says to wait.

    Shared by the sync and async helpers. See :mod:`ess_auth.rate_limit`.
    """
    status = parse_rate_limit_headers(response.headers)
    if not status.is_reported():
        return
    hold = rate_limit_hold_secs(status, status_code=response.status_code)
    if hold <= 0:
        return
    cooldown.hold(hold)
    logger.warning(
        "OAUTH_RATE_LIMIT_HOLD label=%s status=%d limit=%s remaining=%s hold_s=%.0f",
        label,
        response.status_code,
        status.limit,
        status.remaining,
        hold,
    )


def parse_access_token(payload: dict) -> str:
    """Return the access token from *payload*, rejecting unusable values.

    A missing key is already a ``KeyError``, but an empty string, ``null``,
    or a number is not: it would be cached, clear the cooldown, and leave
    callers sending ``Bearer`` with nothing useful after it. Call from
    inside the body-parsing ``try`` so the ``ValueError`` lands on the
    malformed-response path.

    Raises:
        ValueError: If the token is not a non-empty string.
    """
    access_token = payload["access_token"]
    if not isinstance(access_token, str) or not access_token:
        raise ValueError(
            f"access_token was {type(access_token).__name__}, "
            "expected a non-empty string"
        )
    return access_token


def parse_expires_in(payload: dict) -> int:
    """Return the token lifetime from *payload*, rejecting dead tokens.

    A non-positive ``expires_in`` describes a token that has already
    expired. Caching it -- even for the one-second floor -- would send a
    dead credential upstream, so it is treated as an unusable response.
    Call from inside the body-parsing ``try`` so the ``ValueError`` lands
    on the malformed-response path that opens the failure cooldown.

    Raises:
        ValueError: If ``expires_in`` is not a positive integer.
    """
    expires_in = int(payload.get("expires_in", 3600))
    if expires_in <= 0:
        raise ValueError(f"expires_in was {expires_in}, expected a positive lifetime")
    return expires_in


def error_detail(response: httpx.Response) -> str:
    """Summarize a token-endpoint error response for logging.

    Prefers the OAuth2 ``error``/``error_description`` fields and falls back
    to raw text, which is what an edge proxy returning HTML will produce.
    """
    try:
        body = response.json()
    except ValueError:
        body = None

    fields = ""
    if isinstance(body, dict):
        fields = f"{body.get('error', '')} {body.get('error_description', '')}"

    detail = " ".join(fields.split()) or " ".join(response.text.split())
    return detail[:_ERROR_DETAIL_MAX_CHARS]


class TokenHelper:
    """Manages OAuth2 client-credentials tokens with caching and auto-refresh.

    Tokens are cached and transparently refreshed when they are within
    ``refresh_margin`` seconds of expiry.

    Parameters
    ----------
    client_id:
        OAuth2 client ID.
    secret:
        OAuth2 client secret.
    token_url:
        Token endpoint URL.
    refresh_margin:
        Seconds before expiry to trigger a proactive refresh.
    scope:
        Optional OAuth2 scope. Sent only when non-empty, so authorization
        servers that reject an empty ``scope`` parameter are unaffected.
    Notes
    -----
    The failure cooldown window is read from
    ``OAUTH_TOKEN_FAILURE_COOLDOWN_SECS``; see :mod:`ess_auth.cooldown`.
    Rate-limit response headers extend it; see :mod:`ess_auth.rate_limit`.
    When a proactive refresh fails, the cached token is served until it
    actually expires, so a token is used for its full lifetime. The token
    POST carries the identification header configured in the environment;
    see :mod:`ess_auth.client_identity`.
    """

    def __init__(
        self,
        client_id: str,
        secret: str,
        *,
        token_url: str,
        refresh_margin: int = EXPIRATION_WINDOW,
        scope: str = "",
    ) -> None:
        self._client_id = client_id
        self._secret = secret
        self._token_url = token_url
        self._refresh_margin = refresh_margin
        self._scope = scope
        self._request_headers = client_identity_headers()
        self._cooldown = FailureCooldown()
        self._lock = threading.Lock()

        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._usable_until: float = 0.0

    @property
    def token(self) -> str | None:
        """The current cached access token, or ``None`` if not yet fetched."""
        return self._access_token

    @property
    def is_expired(self) -> bool:
        """Whether the cached token is missing or within the refresh window."""
        return self._access_token is None or time.monotonic() >= self._usable_until

    def fetch_token(self, http: httpx.Client | None = None) -> str:
        """Return a valid access token, refreshing if necessary.

        Parameters
        ----------
        http:
            Optional ``httpx.Client`` to reuse. A short-lived client is
            created automatically when *None*.
        """
        # The cooldown check and the refresh have to be atomic: two worker
        # threads arriving on a cold or expired cache can otherwise both see
        # a closed breaker before either failure opens it, and both reach the
        # endpoint the cooldown exists to shield. The cached read stays
        # outside the lock so it never queues behind an in-flight refresh.
        if self.is_expired:
            with self._lock:
                if self.is_expired:
                    try:
                        self._refresh_guarded(http)
                    except AuthenticationError:
                        stale = self._stale_token()
                        if stale is None:
                            raise
                        return stale

        assert self._access_token is not None  # noqa: S101  # nosec B101  # narrowing assertion after None check
        return self._access_token

    def _stale_token(self) -> str | None:
        """Return the cached token if it outlives a failed refresh.

        Callers must hold ``self._lock``.
        """
        valid_for = self._expires_at - time.monotonic()
        if self._access_token is None or valid_for <= STALE_TOKEN_SAFETY_SECS:
            return None
        logger.warning(
            "OAUTH_TOKEN_STALE_SERVED label=TokenHelper valid_for_s=%.0f token_url=%s",
            valid_for,
            self._token_url,
        )
        return self._access_token

    def fetch_token_info(self, http: httpx.Client | None = None) -> tuple[str, float]:
        """Return ``(token, expires_at_monotonic)``."""
        token = self.fetch_token(http)
        with self._lock:
            return token, self._expires_at

    def _refresh_guarded(self, http: httpx.Client | None) -> None:
        """Refresh once unless the failure cooldown is still open.

        Callers must hold ``self._lock``.
        """
        cooling_for = self._cooldown.remaining()
        if cooling_for > 0:
            raise TokenEndpointCoolingDownError(
                f"Token endpoint is cooling down for {cooling_for:.0f}s after a "
                f"recent failure; not retrying ({self._token_url})"
            )

        if http is not None:
            self._refresh(http)
        else:
            with httpx.Client(timeout=30.0) as client:
                self._refresh(client)

    def _refresh(self, http: httpx.Client) -> None:
        logger.info("Refreshing OAuth2 access token from %s", self._token_url)
        data = {"grant_type": "client_credentials"}
        if self._scope:
            data["scope"] = self._scope
        try:
            response = http.post(
                self._token_url,
                data=data,
                auth=(self._client_id, self._secret),
                headers=self._request_headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._cooldown.start()
            apply_rate_limit_headers(self._cooldown, exc.response, label="TokenHelper")
            raise TokenRequestFailedError(
                f"Token request failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                detail=error_detail(exc.response),
                diagnostics=diagnostic_headers(exc.response.headers),
            ) from exc
        except httpx.HTTPError as exc:
            self._cooldown.start()
            raise TokenRequestFailedError(f"Token request failed: {exc}") from exc

        try:
            payload = response.json()
            access_token = parse_access_token(payload)
            expires_in = parse_expires_in(payload)
        except (ValueError, KeyError, TypeError) as exc:
            # A malformed body would otherwise retry as hard as a denial.
            self._cooldown.start()
            apply_rate_limit_headers(self._cooldown, response, label="TokenHelper")
            raise TokenRequestFailedError(
                f"Token response was not usable: {exc}",
                status_code=response.status_code,
                detail=error_detail(response),
                diagnostics=diagnostic_headers(response.headers),
            ) from exc

        now = time.monotonic()
        self._access_token = access_token
        self._expires_at = now + expires_in
        self._usable_until = now + max(
            expires_in - self._refresh_margin, MIN_CACHE_LIFETIME_SECS
        )
        self._cooldown.clear()
        # After clear(): a granted token can still report a nearly spent
        # shared budget, and the hold must survive the reset.
        apply_rate_limit_headers(self._cooldown, response, label="TokenHelper")
        logger.info("Token acquired, expires in %ds", expires_in)
