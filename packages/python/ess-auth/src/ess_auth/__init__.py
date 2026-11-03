"""OAuth2 client-credentials authentication and JWT verification utilities."""

from .async_token_helper import AsyncTokenHelper, TokenClientOptions
from .client_identity import client_identity_headers
from .cooldown import FailureCooldown
from .jwt import JWKSVerifier, decode_jwt, generate_jwt
from .rate_limit import (
    RateLimitStatus,
    diagnostic_headers,
    parse_rate_limit_headers,
    rate_limit_hold_secs,
)
from .token_helper import (
    AuthenticationError,
    TokenEndpointCoolingDownError,
    TokenHelper,
    TokenRequestFailedError,
)

__all__ = [
    "AsyncTokenHelper",
    "AuthenticationError",
    "FailureCooldown",
    "JWKSVerifier",
    "RateLimitStatus",
    "TokenClientOptions",
    "TokenEndpointCoolingDownError",
    "TokenHelper",
    "TokenRequestFailedError",
    "client_identity_headers",
    "decode_jwt",
    "diagnostic_headers",
    "generate_jwt",
    "parse_rate_limit_headers",
    "rate_limit_hold_secs",
]
