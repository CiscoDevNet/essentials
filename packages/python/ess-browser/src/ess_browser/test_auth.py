"""Unit tests for SSO auth helpers."""

from __future__ import annotations

from .auth import DUO_SKIP_UPDATE_SCRIPT, is_auth_redirect


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


class TestDuoSkipUpdateScript:
    """Verify the domain guard in the JS script."""

    def test_rejects_evil_subdomain(self):
        assert 'hostname !== "duosecurity.com"' in DUO_SKIP_UPDATE_SCRIPT
        assert 'hostname.endsWith(".duosecurity.com")' in DUO_SKIP_UPDATE_SCRIPT

    def test_uses_safe_observer_root(self):
        assert "document.body || document.documentElement" in DUO_SKIP_UPDATE_SCRIPT
