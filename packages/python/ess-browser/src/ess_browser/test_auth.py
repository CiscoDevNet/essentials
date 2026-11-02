"""Unit tests for SSO auth helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from .auth import DUO_SKIP_UPDATE_SCRIPT, is_auth_redirect, is_sso_login_required
from .session import BrowserSession


class TestIsAuthRedirect:
    def test_same_host_is_not_redirect(self):
        assert not is_auth_redirect(
            "https://app.example.com/page",
            "https://app.example.com/",
        )

    def test_sso_host_is_redirect(self):
        assert is_auth_redirect(
            "https://sso.example.com/login",
            "https://app.example.com/",
        )

    def test_duo_host_is_redirect(self):
        assert is_auth_redirect(
            "https://login.duosecurity.com/frame",
            "https://app.example.com/",
        )

    def test_unrelated_host_is_not_redirect(self):
        assert not is_auth_redirect(
            "https://example.com/",
            "https://app.example.com/",
        )

    def test_company_idp_needs_extra_auth_domains(self):
        # Company login hosts belong to the caller, not to AUTH_DOMAINS.
        assert not is_auth_redirect(
            "https://login.corp.example.net/authorize",
            "https://app.example.com/",
        )
        assert is_auth_redirect(
            "https://login.corp.example.net/authorize",
            "https://app.example.com/",
            extra_auth_domains=("login.corp.example.net",),
        )

    def test_browser_session_wrapper_honors_extra_auth_domains(self):
        assert BrowserSession.is_auth_redirect(
            "https://login.corp.example.net/authorize",
            "https://app.example.com/",
            extra_auth_domains=("login.corp.example.net",),
        )


class TestDuoSkipUpdateScript:
    """Verify the domain guard in the JS script."""

    def test_rejects_evil_subdomain(self):
        assert 'hostname !== "duosecurity.com"' in DUO_SKIP_UPDATE_SCRIPT
        assert 'hostname.endsWith(".duosecurity.com")' in DUO_SKIP_UPDATE_SCRIPT

    def test_uses_safe_observer_root(self):
        assert "document.body || document.documentElement" in DUO_SKIP_UPDATE_SCRIPT


class TestIsSsoLoginRequired:
    @patch("ess_browser.session.BrowserSession")
    def test_missing_profile_dir_requires_login(
        self, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        profile_dir = tmp_path / "nonexistent-ess-browser-profile-test"

        assert is_sso_login_required(
            "https://app.example.com/",
            profile_dir=profile_dir,
        )
        mock_session_cls.assert_not_called()

    @patch("ess_browser.session.BrowserSession")
    def test_auth_redirect_requires_login(
        self, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_page = MagicMock()
        mock_session.new_page.return_value = mock_page
        mock_page.url = "https://login.duosecurity.com/frame"

        profile_dir = tmp_path / "ess-browser-profile-with-data"
        with patch("ess_browser.auth._is_profile_empty", return_value=False):
            assert is_sso_login_required(
                "https://app.example.com/",
                profile_dir=profile_dir,
            )

    @patch("ess_browser.session.BrowserSession")
    def test_valid_session_does_not_require_login(
        self, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_page = MagicMock()
        mock_session.new_page.return_value = mock_page
        mock_page.url = "https://app.example.com/dashboard"

        profile_dir = tmp_path / "ess-browser-profile-with-data"
        with patch("ess_browser.auth._is_profile_empty", return_value=False):
            assert not is_sso_login_required(
                "https://app.example.com/",
                profile_dir=profile_dir,
            )

    @patch("ess_browser.session.BrowserSession")
    def test_probe_failure_assumes_session_valid(
        self, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_session_cls.side_effect = RuntimeError("Timeout 30000ms exceeded")

        profile_dir = tmp_path / "ess-browser-profile-with-data"
        with patch("ess_browser.auth._is_profile_empty", return_value=False):
            assert not is_sso_login_required(
                "https://app.example.com/",
                profile_dir=profile_dir,
            )

    @patch("ess_browser.session.BrowserSession")
    def test_unreadable_profile_assumes_session_valid(
        self, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        profile_dir = tmp_path / "ess-browser-profile-with-data"
        with patch(
            "ess_browser.auth._is_profile_empty",
            side_effect=OSError("Permission denied"),
        ):
            assert not is_sso_login_required(
                "https://app.example.com/",
                profile_dir=profile_dir,
            )
        mock_session_cls.assert_not_called()
