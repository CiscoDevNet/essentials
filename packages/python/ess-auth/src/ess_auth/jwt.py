"""JWT token generation, decoding, and JWKS verification."""

from __future__ import annotations

import logging
import time

import jwt as pyjwt

try:
    from jwt import PyJWKClient as _PyJWKClient
except ImportError:
    _PyJWKClient = None  # type: ignore[assignment,misc]

from .token_helper import AuthenticationError

logger = logging.getLogger(__name__)

_DEFAULT_ALGORITHM = "HS256"
_SECONDS_PER_DAY = 86400


def generate_jwt(
    subject: str,
    secret: str,
    *,
    expires_days: int = 30,
    algorithm: str = _DEFAULT_ALGORITHM,
    **extra_claims: object,
) -> str:
    """Generate an HS256 JWT.

    Parameters
    ----------
    subject:
        The ``sub`` claim — identifies the token holder (e.g., a user ID).
    secret:
        The signing secret (must match ``AUTH_SECRET`` on the server).
    expires_days:
        Token lifetime in days (default: 30).
    algorithm:
        JWT algorithm (default: HS256).
    **extra_claims:
        Additional claims merged into the payload.

    Returns
    -------
    str
        The encoded JWT string.
    """
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_days * _SECONDS_PER_DAY,
        **extra_claims,
    }
    return pyjwt.encode(payload, secret, algorithm=algorithm)


def decode_jwt(
    token: str,
    secret: str,
    *,
    algorithm: str = _DEFAULT_ALGORITHM,
) -> dict:
    """Decode and verify an HS256 JWT.

    Parameters
    ----------
    token:
        The encoded JWT string.
    secret:
        The signing secret used to verify the signature.
    algorithm:
        Expected JWT algorithm (default: HS256).

    Returns
    -------
    dict
        The decoded payload.

    Raises
    ------
    jwt.InvalidTokenError
        If the token is invalid, expired, or the signature doesn't match.
    """
    return pyjwt.decode(token, secret, algorithms=[algorithm])


class JWKSVerifier:
    """Verify JWTs against a JWKS endpoint (RS256) with optional HS256 fallback.

    Parameters
    ----------
    jwks_uri:
        URL of the JWKS endpoint for RS256 public key discovery.
    issuer:
        Expected ``iss`` claim value.
    audience:
        Expected ``aud`` claim value.
    hs256_secret:
        Optional shared secret for HS256 fallback. When *None*, only RS256
        is attempted.
    """

    def __init__(
        self,
        jwks_uri: str,
        issuer: str,
        audience: str,
        *,
        hs256_secret: str | None = None,
    ) -> None:
        if _PyJWKClient is None:
            msg = (
                "JWKS verification requires the 'cryptography' package. "
                "Install it with: pip install 'ess-auth[jwks]'"
            )
            raise ImportError(msg)
        self._jwks_client = _PyJWKClient(jwks_uri, cache_keys=True)
        self._issuer = issuer
        self._audience = audience
        self._hs256_secret = hs256_secret or None

    def verify(self, token: str) -> dict:
        """Decode and verify a JWT token.

        Tries RS256 (JWKS) first. If that fails and an HS256 secret is
        configured, falls back to HS256 verification.

        Returns
        -------
        dict
            The decoded JWT payload.

        Raises
        ------
        AuthenticationError
            If verification fails for all configured methods.
        """
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            return pyjwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except (pyjwt.InvalidTokenError, pyjwt.PyJWKClientError):
            logger.debug("RS256 verification failed, trying fallback", exc_info=True)

        if self._hs256_secret:
            try:
                return pyjwt.decode(token, self._hs256_secret, algorithms=["HS256"])
            except pyjwt.InvalidTokenError:
                pass

        raise AuthenticationError("Invalid token")

    @staticmethod
    def extract_token(
        headers: dict[bytes, bytes],
        authorization: str | None = None,
    ) -> str:
        """Extract raw JWT from HTTP headers.

        Checks ``authorization`` first (parsed ``Authorization: Bearer`` value),
        then falls back to the ``x-api-key`` header.

        Raises
        ------
        AuthenticationError
            If no token is found.
        """
        token_value = authorization
        if not token_value:
            api_key = headers.get(b"x-api-key", b"").decode()
            if api_key:
                token_value = api_key
        if not token_value:
            raise AuthenticationError("Missing authorization")
        scheme, _, value = token_value.strip().partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
        return token_value.strip()
