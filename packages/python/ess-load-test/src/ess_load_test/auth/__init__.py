"""Authentication helpers for load test targets."""

from ess_load_test.auth.browser import (
    BrowserAuthError,
    establish_browser_session,
    fetch_auth_header_via_browser,
)
from ess_load_test.auth.oauth import (
    OAuthCredentialsError,
    fetch_bearer_token,
    format_auth_header,
    resolve_oauth_credentials,
    write_auth_header_env_file,
)

__all__ = [
    "BrowserAuthError",
    "OAuthCredentialsError",
    "establish_browser_session",
    "fetch_auth_header_via_browser",
    "fetch_bearer_token",
    "format_auth_header",
    "resolve_oauth_credentials",
    "write_auth_header_env_file",
]
