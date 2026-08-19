"""Tests for agent_test URL resolution."""

import click
import pytest

from ess_langsmith_client.agent_test.resolution import (
    join_host_with_custom_url,
    resolve_base_url,
)
from ess_langsmith_client.client import ControlPlaneClient

_CREDS_PATCH = {
    "api_key": "test-key",
    "workspace_id": "test-ws",
}


def _stub_deployments(monkeypatch, resources):
    def _fake_list_deployments(self, name_contains=None):
        return {"resources": resources}

    monkeypatch.setattr(ControlPlaneClient, "list_deployments", _fake_list_deployments)


def _deployment(name, custom_url):
    return {
        "name": name,
        "id": "d1",
        "status": "DEPLOYED",
        "source_config": {"custom_url": custom_url},
    }


class TestJoinHostWithCustomUrl:
    def test_replaces_host_keeps_path(self):
        joined = join_host_with_custom_url(
            "https://agents.example.com",
            "https://agents.internal.example.com/lgp/hello-agent-dev-abc",
        )
        assert joined == "https://agents.example.com/lgp/hello-agent-dev-abc"

    def test_missing_path_raises(self):
        with pytest.raises(click.ClickException, match="no mount path"):
            join_host_with_custom_url(
                "https://agents.example.com",
                "https://agents.internal.example.com",
            )


class TestResolveBaseUrl:
    def test_prefix_mode_uses_port_forward_default(self):
        base = resolve_base_url(
            "hello-agent",
            url=None,
            prefix="/lgp/abc",
            use_kubectl=False,
            deployment=None,
            env="dev",
            region="us",
        )
        assert base == "http://localhost:8000/lgp/abc"

    def test_prefix_mode_honors_url(self):
        base = resolve_base_url(
            "hello-agent",
            url="http://127.0.0.1:9000",
            prefix="/lgp/abc",
            use_kubectl=False,
            deployment=None,
            env="dev",
            region="us",
        )
        assert base == "http://127.0.0.1:9000/lgp/abc"

    def test_prefix_mode_adds_leading_slash(self):
        base = resolve_base_url(
            "hello-agent",
            url=None,
            prefix="lgp/abc",
            use_kubectl=False,
            deployment=None,
            env="dev",
            region="us",
        )
        assert base == "http://localhost:8000/lgp/abc"

    def test_control_plane_returns_custom_url(self, monkeypatch):
        custom = "https://agents.internal.example.com/lgp/hello-agent-dev-abc"
        _stub_deployments(monkeypatch, [_deployment("hello-agent-dev", custom)])
        monkeypatch.setenv("LANGSMITH_API_KEY", _CREDS_PATCH["api_key"])
        monkeypatch.setenv("LANGSMITH_WORKSPACE_ID", _CREDS_PATCH["workspace_id"])
        base = resolve_base_url(
            "hello-agent",
            url=None,
            prefix=None,
            use_kubectl=False,
            deployment=None,
            env="dev",
            region="us",
        )
        assert base == custom

    def test_control_plane_joins_friendly_host(self, monkeypatch):
        custom = "https://agents.internal.example.com/lgp/hello-agent-dev-abc"
        _stub_deployments(monkeypatch, [_deployment("hello-agent-dev", custom)])
        monkeypatch.setenv("LANGSMITH_API_KEY", _CREDS_PATCH["api_key"])
        monkeypatch.setenv("LANGSMITH_WORKSPACE_ID", _CREDS_PATCH["workspace_id"])
        base = resolve_base_url(
            "hello-agent",
            url="https://agents.example.com",
            prefix=None,
            use_kubectl=False,
            deployment=None,
            env="dev",
            region="us",
        )
        assert base == "https://agents.example.com/lgp/hello-agent-dev-abc"
