"""OAuth2 Client Credentials token helper with automatic caching and refresh."""

from __future__ import annotations

import logging
import time

import httpx

from .config import EXPIRATION_WINDOW

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when a token request fails."""


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
    """

    def __init__(
        self,
        client_id: str,
        secret: str,
        *,
        token_url: str,
        refresh_margin: int = EXPIRATION_WINDOW,
    ) -> None:
        self._client_id = client_id
        self._secret = secret
        self._token_url = token_url
        self._refresh_margin = refresh_margin

        self._access_token: str | None = None
        self._expires_at: float = 0.0

    @property
    def token(self) -> str | None:
        """The current cached access token, or ``None`` if not yet fetched."""
        return self._access_token

    @property
    def is_expired(self) -> bool:
        """Whether the cached token is missing or within the refresh window."""
        return self._access_token is None or time.monotonic() >= (
            self._expires_at - self._refresh_margin
        )

    def fetch_token(self, http: httpx.Client | None = None) -> str:
        """Return a valid access token, refreshing if necessary.

        Parameters
        ----------
        http:
            Optional ``httpx.Client`` to reuse. A short-lived client is
            created automatically when *None*.
        """
        if not self.is_expired:
            assert self._access_token is not None  # noqa: S101  # nosec B101  # narrowing assertion after None check
            return self._access_token

        if http is not None:
            self._refresh(http)
        else:
            with httpx.Client(timeout=30.0) as client:
                self._refresh(client)

        assert self._access_token is not None  # noqa: S101  # nosec B101  # narrowing assertion after None check
        return self._access_token

    def fetch_token_info(self, http: httpx.Client | None = None) -> tuple[str, float]:
        """Return ``(token, expires_at_monotonic)``."""
        token = self.fetch_token(http)
        return token, self._expires_at

    def _refresh(self, http: httpx.Client) -> None:
        logger.info("Refreshing OAuth2 access token from %s", self._token_url)
        try:
            response = http.post(
                self._token_url,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._secret),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AuthenticationError(
                f"Token request failed: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"Token request failed: {exc}") from exc

        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._expires_at = time.monotonic() + expires_in
        logger.info("Token acquired, expires in %ds", expires_in)
