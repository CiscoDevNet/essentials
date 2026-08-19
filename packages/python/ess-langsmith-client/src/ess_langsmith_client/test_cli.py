"""Tests for ess_langsmith_client.cli helpers."""

import click
import pytest

from ess_langsmith_client import (
    resolve_deployment_base_url,
    resolve_live_deployment_record,
)
from ess_langsmith_client.client import ControlPlaneClient

_CREDS = {"api_key": "test-key", "workspace_id": "test-ws"}


def _stub_resources(monkeypatch, resources):
    """Make every ControlPlaneClient list deployments return ``resources``."""

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


class TestResolveLiveDeploymentRecord:
    def test_returns_live_deployment(self, monkeypatch):
        resource = _deployment("hello-agent-dev", "https://a.example/lgp/x")
        _stub_resources(monkeypatch, [resource])
        client = ControlPlaneClient(**_CREDS)
        live = resolve_live_deployment_record(client, service="hello-agent", env="dev")
        assert live is not None
        assert live["id"] == "d1"
        assert live["name"] == "hello-agent-dev"

    def test_returns_none_when_missing(self, monkeypatch):
        _stub_resources(monkeypatch, [])
        client = ControlPlaneClient(**_CREDS)
        assert (
            resolve_live_deployment_record(client, service="hello-agent", env="dev")
            is None
        )


class TestResolveDeploymentBaseUrl:
    def test_returns_custom_url_for_canonical_name(self, monkeypatch):
        url = "https://a.example/lgp/hello-agent-dev-abc"
        _stub_resources(monkeypatch, [_deployment("hello-agent-dev", url)])
        assert resolve_deployment_base_url("hello-agent", env="dev", **_CREDS) == url

    def test_explicit_deployment_overrides_service(self, monkeypatch):
        url = "https://a.example/lgp/hello-agent-prod-dev-xyz"
        _stub_resources(monkeypatch, [_deployment("hello-agent-prod-dev", url)])
        resolved = resolve_deployment_base_url(
            "hello-agent", deployment="hello-agent-prod-dev", **_CREDS
        )
        assert resolved == url

    def test_no_deployment_raises(self, monkeypatch):
        _stub_resources(monkeypatch, [])
        with pytest.raises(click.ClickException, match="No live deployment"):
            resolve_deployment_base_url("hello-agent", env="dev", **_CREDS)

    def test_missing_custom_url_raises(self, monkeypatch):
        _stub_resources(monkeypatch, [_deployment("hello-agent-dev", None)])
        with pytest.raises(click.ClickException, match="no custom_url"):
            resolve_deployment_base_url("hello-agent", env="dev", **_CREDS)
