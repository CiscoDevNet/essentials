"""Tests for ControlPlaneClient.delete_project (control-plane projects)."""

from http import HTTPStatus
from typing import Any

import pytest

from ess_langsmith_client import client as client_module
from ess_langsmith_client.client import ControlPlaneClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        return self._payload


@pytest.fixture(autouse=True)
def _clear_workspace_env(monkeypatch):
    # Keep construction deterministic: a stray LANGSMITH_WORKSPACE_ID in the
    # environment must not leak a default workspace into these tests.
    monkeypatch.delenv("LANGSMITH_WORKSPACE_ID", raising=False)


@pytest.fixture
def client() -> ControlPlaneClient:
    # No workspace at construction: the API key authorizes; workspace is
    # selected per operation.
    return ControlPlaneClient(api_key="test-key")


class TestConstruction:
    def test_workspace_is_optional(self):
        """The client instantiates with only an API key (no workspace)."""
        instance = ControlPlaneClient(api_key="test-key")
        assert instance.workspace_id is None
        assert "X-Tenant-Id" not in instance.headers

    def test_api_key_still_required(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        with pytest.raises(ValueError, match="LANGSMITH_API_KEY is required"):
            ControlPlaneClient(api_key=None, workspace_id="ws")

    def test_constructor_workspace_sets_tenant_header(self):
        instance = ControlPlaneClient(api_key="test-key", workspace_id="ws-1")
        assert instance.headers["X-Tenant-Id"] == "ws-1"


class TestDeleteProject:
    def _capture_delete(self, monkeypatch) -> dict[str, Any]:
        captured: dict[str, Any] = {}

        def _fake_delete(url, *, headers, params, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return _FakeResponse(HTTPStatus.OK)

        monkeypatch.setattr(client_module.requests, "delete", _fake_delete)
        return captured

    def test_builds_control_plane_url(self, client, monkeypatch):
        captured = self._capture_delete(monkeypatch)
        client.delete_project("abc", workspace_id="ws-test")
        assert captured["url"].endswith("/v1/projects/abc")
        assert "api.host.langchain.com" in captured["url"]
        assert "/api-host/" not in captured["url"]
        assert "/v2/" not in captured["url"]

    def test_eu_region_uses_eu_control_plane_host(self, monkeypatch):
        captured = self._capture_delete(monkeypatch)
        eu_client = ControlPlaneClient(api_key="test-key", region="eu")
        eu_client.delete_project("abc", workspace_id="ws-test")
        assert "eu.api.host.langchain.com" in captured["url"]
        assert captured["url"].endswith("/v1/projects/abc")

    def test_default_params_preserve_traces(self, client, monkeypatch):
        captured = self._capture_delete(monkeypatch)
        client.delete_project("abc", workspace_id="ws-test")
        assert captured["params"] == {
            "force": "true",
            "delete_tracing_project": "false",
        }

    def test_params_reflect_overrides(self, client, monkeypatch):
        captured = self._capture_delete(monkeypatch)
        client.delete_project(
            "abc", workspace_id="ws-test", force=False, delete_tracing_project=True
        )
        assert captured["params"] == {
            "force": "false",
            "delete_tracing_project": "true",
        }

    def test_sends_api_key_header(self, client, monkeypatch):
        captured = self._capture_delete(monkeypatch)
        client.delete_project("abc", workspace_id="ws-test")
        assert captured["headers"]["X-Api-Key"] == "test-key"

    def test_raises_without_workspace(self, client):
        """SaaS control-plane deletes require X-Tenant-Id; fail fast when missing."""
        with pytest.raises(ValueError, match="workspace is required"):
            client.delete_project("abc")

    def test_runtime_workspace_scopes_request(self, client, monkeypatch):
        """A workspace passed at call time sets X-Tenant-Id for that request."""
        captured = self._capture_delete(monkeypatch)
        client.delete_project("abc", workspace_id="ws-runtime")
        assert captured["headers"]["X-Tenant-Id"] == "ws-runtime"

    def test_runtime_workspace_overrides_client_default(self, monkeypatch):
        captured = self._capture_delete(monkeypatch)
        instance = ControlPlaneClient(api_key="test-key", workspace_id="ws-default")
        instance.delete_project("abc", workspace_id="ws-runtime")
        assert captured["headers"]["X-Tenant-Id"] == "ws-runtime"

    def test_falls_back_to_client_workspace(self, monkeypatch):
        captured = self._capture_delete(monkeypatch)
        instance = ControlPlaneClient(api_key="test-key", workspace_id="ws-default")
        instance.delete_project("abc")
        assert captured["headers"]["X-Tenant-Id"] == "ws-default"

    def test_returns_true_on_ok(self, client, monkeypatch):
        monkeypatch.setattr(
            client_module.requests,
            "delete",
            lambda *a, **k: _FakeResponse(HTTPStatus.OK),
        )
        assert client.delete_project("abc", workspace_id="ws-test") is True

    def test_raises_on_error_with_body(self, client, monkeypatch):
        monkeypatch.setattr(
            client_module.requests,
            "delete",
            lambda *a, **k: _FakeResponse(HTTPStatus.FORBIDDEN, text="Forbidden"),
        )
        with pytest.raises(RuntimeError, match="Forbidden"):
            client.delete_project("abc", workspace_id="ws-test")
