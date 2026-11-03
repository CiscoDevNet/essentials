"""Unit tests for SsoSite and headed-mode selection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from .auth import NAV_TIMEOUT_MS
from .session import default_profile_dir, profile_dir_display
from .site import SsoSite, should_use_headed_browser

SETTLE_MS = 1_500
TENANT_IDP_DOMAIN = "tenant.example.com"


class TestSsoSite:
    def test_login_target_defaults_to_url(self) -> None:
        site = SsoSite(url="https://app.example.com/")

        assert site.login_target == "https://app.example.com/"

    def test_login_target_prefers_explicit_callback_host(self) -> None:
        site = SsoSite(
            url="https://alias.example.com/goals",
            login_complete_url="https://app.example.com/",
        )

        assert site.login_target == "https://app.example.com/"

    def test_defaults(self) -> None:
        site = SsoSite(url="https://app.example.com/")

        assert site.settle_ms == 0
        assert site.nav_timeout_ms == NAV_TIMEOUT_MS
        assert site.extra_auth_domains == ()


class TestShouldUseHeadedBrowser:
    site = SsoSite(url="https://app.example.com/")

    def test_both_force_flags_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="both --headed and --headless"):
            should_use_headed_browser(
                self.site,
                profile_dir=tmp_path,
                force_headed=True,
                force_headless=True,
            )

    def test_force_headed_skips_the_probe(self, tmp_path: Path) -> None:
        with patch("ess_browser.site.is_sso_login_required") as probe:
            assert should_use_headed_browser(
                self.site,
                profile_dir=tmp_path,
                force_headed=True,
            )
        probe.assert_not_called()

    def test_force_headless_skips_the_probe(self, tmp_path: Path) -> None:
        with patch("ess_browser.site.is_sso_login_required") as probe:
            assert not should_use_headed_browser(
                self.site,
                profile_dir=tmp_path,
                force_headless=True,
            )
        probe.assert_not_called()

    def test_falls_back_to_the_probe(self, tmp_path: Path) -> None:
        with patch(
            "ess_browser.site.is_sso_login_required", return_value=True
        ) as probe:
            assert should_use_headed_browser(self.site, profile_dir=tmp_path)
        probe.assert_called_once()

    def test_probe_inherits_site_settle_and_domains(self, tmp_path: Path) -> None:
        """The probe must agree with the real run, or it picks the wrong mode."""
        site = SsoSite(
            url="https://app.example.com/",
            settle_ms=SETTLE_MS,
            extra_auth_domains=(TENANT_IDP_DOMAIN,),
        )

        with patch(
            "ess_browser.site.is_sso_login_required", return_value=False
        ) as probe:
            should_use_headed_browser(site, profile_dir=tmp_path)

        _, kwargs = probe.call_args
        assert kwargs["settle_timeout_ms"] == SETTLE_MS
        assert kwargs["extra_auth_domains"] == (TENANT_IDP_DOMAIN,)

    def test_zero_settle_uses_the_probe_default(self, tmp_path: Path) -> None:
        with patch(
            "ess_browser.site.is_sso_login_required", return_value=False
        ) as probe:
            should_use_headed_browser(self.site, profile_dir=tmp_path)

        _, kwargs = probe.call_args
        assert kwargs["settle_timeout_ms"] > 0


class TestProfileDirHelpers:
    def test_default_profile_dir_is_per_tool(self) -> None:
        result = default_profile_dir("my-tool")

        assert result.parent.name == ".my-tool"
        assert result.name == "browser-profile"

    def test_display_form_does_not_leak_the_home_path(self) -> None:
        assert profile_dir_display("my-tool") == "~/.my-tool/browser-profile"

    def test_display_form_matches_the_real_path(self) -> None:
        displayed = profile_dir_display("my-tool").replace("~", str(Path.home()), 1)

        assert Path(displayed) == default_profile_dir("my-tool")
