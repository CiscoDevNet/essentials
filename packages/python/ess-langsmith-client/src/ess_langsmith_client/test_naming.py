"""Tests for the deployment/tracing-project naming convention."""

from datetime import datetime, timezone

import pytest

from ess_langsmith_client.naming import (
    choose_deploy_name,
    compute_base_name,
    resolve_deploy_base,
    resolve_env,
    sanitize_name_component,
)

_NOW = datetime(2026, 5, 29, 10, 47, 8, tzinfo=timezone.utc)


class TestSanitizeNameComponent:
    def test_passthrough_clean(self):
        assert sanitize_name_component("hello-agent") == "hello-agent"

    def test_replaces_invalid_chars(self):
        assert sanitize_name_component("hello/agent@v1") == "hello-agent-v1"

    def test_trims_leading_trailing_hyphens(self):
        assert sanitize_name_component(" hello.agent ") == "hello-agent"


class TestResolveEnv:
    def test_explicit_wins(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "prod")
        assert resolve_env("dev") == "dev"

    def test_falls_back_to_app_env(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "prod")
        assert resolve_env(None) == "prod"

    def test_defaults_to_dev(self, monkeypatch):
        monkeypatch.delenv("APP_ENV", raising=False)
        assert resolve_env(None) == "dev"

    def test_sanitizes(self, monkeypatch):
        monkeypatch.delenv("APP_ENV", raising=False)
        assert resolve_env("Staging/East") == "Staging-East"


class TestComputeBaseName:
    def test_basic(self, monkeypatch):
        monkeypatch.delenv("APP_ENV", raising=False)
        assert compute_base_name("hello-agent", "dev") == "hello-agent-dev"

    def test_uses_env_fallback(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "prod")
        assert compute_base_name("hello-agent") == "hello-agent-prod"


class TestResolveDeployBase:
    def test_uses_explicit_deployment(self):
        assert (
            resolve_deploy_base(deployment="my-agent-prod-dev") == "my-agent-prod-dev"
        )

    def test_builds_from_service_and_env(self, monkeypatch):
        monkeypatch.delenv("APP_ENV", raising=False)
        base = resolve_deploy_base(service="hello-agent", env="prod")
        assert base == "hello-agent-prod"

    def test_requires_service_when_deployment_omitted(self):
        with pytest.raises(ValueError, match="service is required"):
            resolve_deploy_base()


class TestChooseDeployName:
    def test_canonical_when_free(self):
        name = choose_deploy_name("hello-agent-dev", set(), "3f9a2c")
        assert name == "hello-agent-dev"

    def test_sha_rescue_when_canonical_taken(self):
        name = choose_deploy_name("hello-agent-dev", {"hello-agent-dev"}, "3f9a2c")
        assert name == "hello-agent-dev-3f9a2c"

    def test_time_tiebreak_when_sha_also_taken(self):
        name = choose_deploy_name(
            "hello-agent-dev",
            {"hello-agent-dev", "hello-agent-dev-3f9a2c"},
            "3f9a2c",
            now=_NOW,
        )
        assert name == "hello-agent-dev-3f9a2c-1047"

    def test_timestamp_rescue_without_sha(self):
        name = choose_deploy_name(
            "hello-agent-dev",
            {"hello-agent-dev"},
            git_sha=None,
            now=_NOW,
        )
        assert name == "hello-agent-dev-20260529-1047"

    def test_raises_when_all_candidates_taken(self):
        taken = {
            "hello-agent-dev",
            "hello-agent-dev-3f9a2c",
            "hello-agent-dev-3f9a2c-1047",
        }
        with pytest.raises(RuntimeError):
            choose_deploy_name("hello-agent-dev", taken, "3f9a2c", now=_NOW)
