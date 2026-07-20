# ruff: noqa: S106, PLR2004 -- test credentials are not real secrets; magic numbers expected
"""Tests for the OAuth 2.0 Authorization Code Flow."""

from __future__ import annotations

import threading
import time
from http import HTTPStatus
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import httpx
import pytest

from ess_hello_jwt_auth_code.main import (
    _AuthCodeError,
    _capture_callback,
    _exchange_code,
    _generate_pkce,
    _OidcClient,
)

_TEST_STATE = "test-state-abc123"


def _make_client(**overrides: str) -> _OidcClient:
    defaults = {
        "authorize_url": "https://idp.example.com/authorize",
        "token_url": "https://idp.example.com/token",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "redirect_uri": "http://localhost:8900/auth/callback",
        "scope": "openid",
    }
    defaults.update(overrides)
    return _OidcClient(**defaults)


class TestGeneratePkce:
    def test_returns_verifier_and_challenge(self):
        verifier, challenge = _generate_pkce()
        assert len(verifier) > 40
        assert len(challenge) > 20

    def test_verifier_is_url_safe(self):
        verifier, _ = _generate_pkce()
        assert all(c.isalnum() or c in "-_" for c in verifier)

    def test_challenge_is_url_safe_base64(self):
        _, challenge = _generate_pkce()
        assert "=" not in challenge
        assert all(c.isalnum() or c in "-_" for c in challenge)

    def test_generates_unique_values(self):
        pairs = [_generate_pkce() for _ in range(5)]
        verifiers = [v for v, _ in pairs]
        assert len(set(verifiers)) == 5


class TestCaptureCallback:
    _RETRY_INTERVAL = 0.05
    _RETRY_TIMEOUT = 5.0

    def _send_callback(
        self,
        port: int,
        query_params: dict,
        *,
        wait_for: threading.Event | None = None,
        done_event: threading.Event | None = None,
    ):
        """Send a GET to the callback server, retrying until it connects."""
        url = f"http://localhost:{port}/auth/callback?{urlencode(query_params)}"

        def _request():
            if wait_for:
                wait_for.wait(timeout=self._RETRY_TIMEOUT)
            deadline = time.monotonic() + self._RETRY_TIMEOUT
            while time.monotonic() < deadline:
                try:
                    httpx.get(url, timeout=2)
                    if done_event:
                        done_event.set()
                    return
                except httpx.ConnectError:
                    time.sleep(self._RETRY_INTERVAL)
                except httpx.RequestError:
                    if done_event:
                        done_event.set()
                    pass

        thread = threading.Thread(target=_request, daemon=True)
        thread.start()
        return thread

    def test_success(self):
        port = 18901
        self._send_callback(port, {"state": _TEST_STATE, "code": "auth-code-xyz"})
        result = _capture_callback(port, expected_state=_TEST_STATE)
        assert result == "auth-code-xyz"

    def test_state_mismatch_keeps_serving(self):
        """Wrong-state requests keep the server alive for the next valid one."""
        port = 18902
        bad_done = threading.Event()
        self._send_callback(
            port,
            {"state": "wrong-state", "code": "bad"},
            done_event=bad_done,
        )
        self._send_callback(
            port,
            {"state": _TEST_STATE, "code": "good-code"},
            wait_for=bad_done,
        )
        result = _capture_callback(port, expected_state=_TEST_STATE)
        assert result == "good-code"

    def test_idp_error_raises(self):
        port = 18903
        self._send_callback(
            port,
            {
                "state": _TEST_STATE,
                "error": "access_denied",
                "error_description": "User cancelled",
            },
        )
        with pytest.raises(_AuthCodeError, match="access_denied: User cancelled"):
            _capture_callback(port, expected_state=_TEST_STATE)

    def test_timeout_raises(self):
        port = 18904
        with (
            patch("ess_hello_jwt_auth_code.main._CALLBACK_TIMEOUT", 0.1),
            pytest.raises(_AuthCodeError, match="No callback received"),
        ):
            _capture_callback(port, expected_state=_TEST_STATE)

    def test_response_is_plain_text(self):
        """Verify the response uses text/plain, preventing XSS."""
        port = 18905
        response_holder: list[httpx.Response] = []
        url = (
            f"http://localhost:{port}/auth/callback?"
            f"{urlencode({'state': _TEST_STATE, 'code': 'c'})}"
        )

        def _request():
            deadline = time.monotonic() + self._RETRY_TIMEOUT
            while time.monotonic() < deadline:
                try:
                    resp = httpx.get(url, timeout=2)
                    response_holder.append(resp)
                    return
                except httpx.ConnectError:
                    time.sleep(self._RETRY_INTERVAL)
                except httpx.RequestError:
                    pass

        thread = threading.Thread(target=_request, daemon=True)
        thread.start()
        _capture_callback(port, expected_state=_TEST_STATE)
        thread.join(timeout=2)

        assert response_holder, "No response captured"
        content_type = response_holder[0].headers.get("content-type", "")
        assert "text/plain" in content_type
        assert "<h2>" not in response_holder[0].text


class TestExchangeCode:
    @staticmethod
    def _setup_mock_client(mock_client_cls, mock_response):
        mock_post = MagicMock(return_value=mock_response)
        mock_http = MagicMock(post=mock_post)
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        return mock_post

    def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = HTTPStatus.OK
        mock_response.json.return_value = {
            "access_token": "jwt-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("ess_hello_jwt_auth_code.main.httpx.Client") as mock_client_cls:
            mock_post = self._setup_mock_client(mock_client_cls, mock_response)
            result = _exchange_code(_make_client(), "auth-code", "test-verifier")

        assert result["access_token"] == "jwt-token"
        assert result["expires_in"] == 3600

        mock_post.assert_called_once()
        call_data = mock_post.call_args.kwargs["data"]
        assert call_data["grant_type"] == "authorization_code"
        assert call_data["client_id"] == "test-client-id"
        assert call_data["code"] == "auth-code"
        assert call_data["code_verifier"] == "test-verifier"

    def test_failure_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = HTTPStatus.BAD_REQUEST
        mock_response.text = "invalid_grant"

        with patch("ess_hello_jwt_auth_code.main.httpx.Client") as mock_client_cls:
            mock_post = self._setup_mock_client(mock_client_cls, mock_response)

            with pytest.raises(_AuthCodeError, match="Token exchange failed"):
                _exchange_code(_make_client(), "bad-code", "verifier")

        mock_post.assert_called_once()
        call_data = mock_post.call_args.kwargs["data"]
        assert call_data["grant_type"] == "authorization_code"
        assert call_data["code"] == "bad-code"
