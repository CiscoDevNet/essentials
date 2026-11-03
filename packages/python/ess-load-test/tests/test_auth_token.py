"""Tests for OAuth token helpers."""

import os
from unittest.mock import MagicMock, patch

import pytest
from ess_load_test.app_config import OAuthSettings
from ess_load_test.auth.oauth import (
    OAuthCredentialsError,
    fetch_bearer_token,
    format_auth_header,
    resolve_oauth_credentials,
)

_OAUTH = OAuthSettings(
    default_token_url="https://idp.example.com/oauth2/default/v1/token",
    client_id_fallback_envs=("APP_SSO_CLIENT_ID",),
    client_secret_fallback_envs=("APP_SSO_CLIENT_SECRET",),
    token_url_fallback_envs=("APP_SSO_TOKEN_URL",),
)


def test_format_auth_header_adds_bearer_prefix() -> None:
    assert format_auth_header("abc123") == "Authorization: Bearer abc123"


def test_format_auth_header_preserves_full_header() -> None:
    assert format_auth_header("X-API-KEY: secret") == "X-API-KEY: secret"


def test_resolve_oauth_credentials_prefers_load_test_env() -> None:
    env = {
        "LOAD_TEST_OAUTH_CLIENT_ID": "load-id",
        "LOAD_TEST_OAUTH_CLIENT_SECRET": "load-secret",
        "APP_SSO_CLIENT_ID": "app-id",
        "APP_SSO_CLIENT_SECRET": "app-secret",
        "LOAD_TEST_OAUTH_TOKEN_URL": "https://idp.example.com/oauth2/v1/token",
    }
    with patch.dict(os.environ, env, clear=True):
        client_id, client_secret, token_url = resolve_oauth_credentials(_OAUTH)
    assert client_id == "load-id"
    assert client_secret == "load-secret"
    assert token_url == "https://idp.example.com/oauth2/v1/token"


def test_resolve_oauth_credentials_missing_raises() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(OAuthCredentialsError):
            resolve_oauth_credentials(_OAUTH)


def test_resolve_oauth_credentials_uses_default_token_url() -> None:
    env = {"LOAD_TEST_OAUTH_CLIENT_ID": "id", "LOAD_TEST_OAUTH_CLIENT_SECRET": "s"}
    with patch.dict(os.environ, env, clear=True):
        _, _, token_url = resolve_oauth_credentials(_OAUTH)
    assert token_url == "https://idp.example.com/oauth2/default/v1/token"


def test_resolve_oauth_credentials_requires_a_token_url() -> None:
    env = {"LOAD_TEST_OAUTH_CLIENT_ID": "id", "LOAD_TEST_OAUTH_CLIENT_SECRET": "s"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(OAuthCredentialsError, match="LOAD_TEST_OAUTH_TOKEN_URL"):
            resolve_oauth_credentials(OAuthSettings())


@patch("ess_load_test.auth.oauth.TokenHelper")
def test_fetch_bearer_token_returns_access_token(mock_helper_cls: MagicMock) -> None:
    mock_helper = MagicMock()
    mock_helper.fetch_token.return_value = "token-value"
    mock_helper_cls.return_value = mock_helper

    env = {
        "LOAD_TEST_OAUTH_CLIENT_ID": "id",
        "LOAD_TEST_OAUTH_CLIENT_SECRET": "secret",
    }
    with patch.dict(os.environ, env, clear=True):
        assert fetch_bearer_token(_OAUTH) == "token-value"

    mock_helper_cls.assert_called_once()
    mock_helper.fetch_token.assert_called_once()
