"""Tests for browser-based SSO auth."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ess_load_test.auth.browser import (
    BrowserAuthError,
    _authorization_from_request,
    _cookies_to_header,
    _has_auth_session,
    fetch_auth_header_via_browser,
)

_PROFILE_DIR = Path.home() / ".ess-load-test-test-profile"


def test_authorization_from_request_matches_target_host() -> None:
    request = MagicMock()
    request.url = "https://app.example.com/api/chat"
    request.headers = {"authorization": "Bearer user-token"}

    header = _authorization_from_request(request, "app.example.com")
    assert header == "Authorization: Bearer user-token"


def test_authorization_from_request_ignores_other_hosts() -> None:
    request = MagicMock()
    request.url = "https://other.example.com/api/chat"
    request.headers = {"authorization": "Bearer user-token"}

    assert _authorization_from_request(request, "app.example.com") is None


def test_authorization_from_request_ignores_parent_domain() -> None:
    request = MagicMock()
    request.url = "https://example.com/api/chat"
    request.headers = {"authorization": "Bearer user-token"}

    assert _authorization_from_request(request, "app.example.com") is None


def test_cookies_to_header_formats_cookie_header() -> None:
    page = MagicMock()
    page.context.cookies.return_value = [
        {"name": "session", "value": "abc"},
        {"name": "csrf", "value": "xyz"},
    ]

    header = _cookies_to_header(page, "https://app.example.com")
    assert header == "Cookie: session=abc; csrf=xyz"


def test_has_auth_session_detects_nextauth_cookie() -> None:
    page = MagicMock()
    page.context.cookies.return_value = [
        {"name": "__Secure-next-auth.session-token", "value": "token"},
    ]

    assert _has_auth_session(page, "https://app.example.com") is True


def test_has_auth_session_ignores_unrelated_cookies() -> None:
    page = MagicMock()
    page.context.cookies.return_value = [{"name": "analytics", "value": "x"}]

    assert _has_auth_session(page, "https://app.example.com") is False


@patch("ess_load_test.auth.browser.BrowserSession")
def test_fetch_auth_header_via_browser_prefers_captured_bearer(
    mock_session_cls: MagicMock,
) -> None:
    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_page = MagicMock()
    mock_session.new_page.return_value = mock_page
    mock_page.url = "https://app.example.com/"
    mock_page.context.cookies.return_value = []

    with patch("ess_load_test.auth.browser._wait_for_target_session") as wait_mock:

        def mark_captured(
            _page, _url, *, headed, captured_headers, extra_auth_domains
        ) -> None:
            captured_headers.append("Authorization: Bearer captured")

        wait_mock.side_effect = mark_captured

        header = fetch_auth_header_via_browser(
            "https://app.example.com",
            profile_dir=_PROFILE_DIR,
            headed=True,
        )

    assert header == "Authorization: Bearer captured"
    mock_session_cls.assert_called_once()
    launch_kwargs = mock_session_cls.call_args.kwargs
    assert launch_kwargs["headed"] is True


@patch("ess_load_test.auth.browser.BrowserSession")
def test_fetch_auth_header_via_browser_prefers_captured_bearer_from_requests(
    mock_session_cls: MagicMock,
) -> None:
    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_page = MagicMock()
    mock_session.new_page.return_value = mock_page
    mock_page.url = "https://app.example.com/"
    mock_page.context.cookies.return_value = []

    def register_request(handler) -> None:
        request = MagicMock()
        request.url = "https://app.example.com/api/health"
        request.headers = {"authorization": "Bearer captured"}
        handler(request)

    mock_page.on.side_effect = lambda _event, handler: register_request(handler)

    with patch("ess_load_test.auth.browser._wait_for_target_session"):
        header = fetch_auth_header_via_browser(
            "https://app.example.com",
            profile_dir=_PROFILE_DIR,
            headed=True,
        )

    assert header == "Authorization: Bearer captured"


@patch("ess_load_test.auth.browser.BrowserSession")
def test_fetch_auth_header_via_browser_falls_back_to_cookies(
    mock_session_cls: MagicMock,
) -> None:
    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_page = MagicMock()
    mock_session.new_page.return_value = mock_page
    mock_page.context.cookies.return_value = [{"name": "session", "value": "abc"}]

    with patch("ess_load_test.auth.browser._wait_for_target_session"):
        header = fetch_auth_header_via_browser(
            "https://app.example.com",
            profile_dir=_PROFILE_DIR,
            headed=True,
        )

    assert header == "Cookie: session=abc"


@patch("ess_load_test.auth.browser.time.sleep")
@patch("ess_load_test.auth.browser.BrowserSession")
def test_extra_auth_domains_mark_the_login_page_as_sso(
    mock_session_cls: MagicMock,
    _sleep: MagicMock,
) -> None:
    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    mock_page = MagicMock()
    mock_session.new_page.return_value = mock_page
    mock_page.url = "https://login.corp.example.net/authorize"
    mock_session_cls.is_auth_redirect.side_effect = lambda *args, **kwargs: (
        "login.corp.example.net" in kwargs["extra_auth_domains"]
    )

    with pytest.raises(BrowserAuthError, match="headless"):
        fetch_auth_header_via_browser(
            "https://app.example.com",
            profile_dir=_PROFILE_DIR,
            headed=False,
            extra_auth_domains=("login.corp.example.net",),
        )


def test_fetch_auth_header_via_browser_requires_target_url() -> None:
    with pytest.raises(BrowserAuthError, match="Target URL is required"):
        fetch_auth_header_via_browser("  ", profile_dir=_PROFILE_DIR)
