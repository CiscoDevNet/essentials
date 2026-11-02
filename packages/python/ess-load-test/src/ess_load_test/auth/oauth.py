"""OAuth2 client-credentials token fetch for load test targets."""

import os
import shlex

from ess_auth import AuthenticationError, TokenHelper

from ess_load_test.app_config import OAuthSettings


class OAuthCredentialsError(ValueError):
    """Raised when OAuth client credentials are missing or invalid."""


def _first_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def resolve_oauth_credentials(oauth: OAuthSettings) -> tuple[str, str, str]:
    """Resolve client ID, secret, and token URL from environment variables."""
    client_id = _first_env((oauth.client_id_env, *oauth.client_id_fallback_envs))
    client_secret = _first_env(
        (oauth.client_secret_env, *oauth.client_secret_fallback_envs)
    )
    token_url = (
        _first_env((oauth.token_url_env, *oauth.token_url_fallback_envs))
        or oauth.default_token_url
    )
    if not client_id or not client_secret:
        msg = (
            f"OAuth client credentials are not set. Provide {oauth.client_id_env} "
            f"and {oauth.client_secret_env} in the environment."
        )
        raise OAuthCredentialsError(msg)
    if not token_url:
        msg = (
            f"OAuth token URL is not set. Provide {oauth.token_url_env} in the "
            "environment, or set OAuthSettings.default_token_url in your shell."
        )
        raise OAuthCredentialsError(msg)
    return client_id, client_secret, token_url


def fetch_bearer_token(oauth: OAuthSettings) -> str:
    """Fetch an access token via client credentials."""
    client_id, client_secret, token_url = resolve_oauth_credentials(oauth)
    helper = TokenHelper(client_id, client_secret, token_url=token_url)
    try:
        return helper.fetch_token()
    except AuthenticationError as exc:
        raise OAuthCredentialsError(str(exc)) from exc


def format_auth_header(token: str) -> str:
    """Format a token as an Authorization header value for Locust."""
    stripped = token.strip()
    if stripped.lower().startswith("bearer "):
        return f"Authorization: {stripped}"
    if ":" in stripped:
        return stripped
    return f"Authorization: Bearer {stripped}"


def write_auth_header_env_file(path: str, token: str) -> None:
    """Write a shell-exportable LOAD_TEST_AUTH_HEADER assignment."""
    header = format_auth_header(token)
    content = f"export LOAD_TEST_AUTH_HEADER={shlex.quote(header)}\n"
    with open(path, "w", encoding="utf-8") as env_file:
        env_file.write(content)
    os.chmod(path, 0o600)
