"""Tests for ControlPlaneClient deployment resolution and listener calls."""

from http import HTTPStatus

import pytest
import requests

from ess_langsmith_client import client as client_module
from ess_langsmith_client.client import ControlPlaneClient

_LISTENER_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def client() -> ControlPlaneClient:
    return ControlPlaneClient(api_key="test-key", workspace_id="test-ws", region="us")


class TestIsDeploymentHealthy:
    @pytest.mark.parametrize(
        "status",
        ["DEPLOYED", "DEPLOYING", "deployed", "", None],
    )
    def test_healthy_statuses(self, status):
        assert ControlPlaneClient.is_deployment_healthy({"status": status}) is True

    @pytest.mark.parametrize(
        "status",
        ["FAILED", "DEPLOY_FAILED", "ERROR", "DELETING"],
    )
    def test_unhealthy_statuses(self, status):
        assert ControlPlaneClient.is_deployment_healthy({"status": status}) is False


class TestFindDeploymentsByBase:
    def _stub_list(self, client, names):
        def _fake_list_deployments(name_contains=None):
            return {"resources": [{"name": n, "id": n} for n in names]}

        client.list_deployments = _fake_list_deployments  # type: ignore[method-assign]

    def test_anchored_prefix_match(self, client):
        self._stub_list(
            client,
            [
                "hello-agent-dev",
                "hello-agent-dev-3f9a2c",
                "hello-agent-prod",
                "hello-agent-development",
            ],
        )
        matches = {
            deployment["name"]
            for deployment in client.find_deployments_by_base("hello-agent-dev")
        }
        # Exact and "<base>-..." match; sibling envs and longer words do not.
        assert matches == {"hello-agent-dev", "hello-agent-dev-3f9a2c"}

    def test_no_matches(self, client):
        self._stub_list(client, ["other-service-dev"])
        assert client.find_deployments_by_base("hello-agent-dev") == []


class TestResolveLiveDeployment:
    def _stub(self, client, resources):
        def _fake_list_deployments(name_contains=None):
            return {"resources": resources}

        client.list_deployments = _fake_list_deployments  # type: ignore[method-assign]

    def test_returns_healthy(self, client):
        self._stub(
            client,
            [{"name": "hello-agent-dev", "id": "d1", "status": "DEPLOYED"}],
        )
        live = client.resolve_live_deployment("hello-agent-dev")
        assert live is not None and live["id"] == "d1"

    def test_skips_stuck_picks_rescue(self, client):
        self._stub(
            client,
            [
                {"name": "hello-agent-dev", "id": "stuck", "status": "FAILED"},
                {
                    "name": "hello-agent-dev-3f9a2c",
                    "id": "live",
                    "status": "DEPLOYED",
                    "created_at": "2026-05-29T10:00:00Z",
                },
            ],
        )
        live = client.resolve_live_deployment("hello-agent-dev")
        assert live is not None and live["id"] == "live"

    def test_prefers_newest_healthy(self, client):
        self._stub(
            client,
            [
                {
                    "name": "hello-agent-dev",
                    "id": "old",
                    "status": "DEPLOYED",
                    "created_at": "2026-05-01T00:00:00Z",
                },
                {
                    "name": "hello-agent-dev-3f9a2c",
                    "id": "new",
                    "status": "DEPLOYED",
                    "created_at": "2026-05-29T00:00:00Z",
                },
            ],
        )
        live = client.resolve_live_deployment("hello-agent-dev")
        assert live is not None and live["id"] == "new"

    def test_tie_break_picks_last_listed_without_timestamps(self, client):
        # No created_at on any match: the last-listed healthy one should win,
        # matching the documented fallback.
        self._stub(
            client,
            [
                {"name": "hello-agent-dev", "id": "first", "status": "DEPLOYED"},
                {"name": "hello-agent-dev-3f9a2c", "id": "last", "status": "DEPLOYED"},
            ],
        )
        live = client.resolve_live_deployment("hello-agent-dev")
        assert live is not None and live["id"] == "last"

    def test_returns_none_when_all_stuck(self, client):
        self._stub(
            client,
            [{"name": "hello-agent-dev", "id": "stuck", "status": "FAILED"}],
        )
        assert client.resolve_live_deployment("hello-agent-dev") is None


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self) -> dict:
        return self._payload


class TestListAllDeployments:
    def test_follows_pagination(self, client, monkeypatch):
        page_size = client_module._PAGE_SIZE
        pages = [
            [{"id": f"a{i}"} for i in range(page_size)],
            [{"id": "last"}],
        ]
        offsets: list[int] = []

        def _fake_get(url, headers, params, timeout):
            offsets.append(params["offset"])
            return _FakeResponse(HTTPStatus.OK, {"resources": pages[len(offsets) - 1]})

        monkeypatch.setattr(client_module.requests, "get", _fake_get)
        deployments = client.list_all_deployments()
        assert len(deployments) == page_size + 1
        assert offsets == [0, page_size]

    def test_raises_on_error(self, client, monkeypatch):
        monkeypatch.setattr(
            client_module.requests,
            "get",
            lambda *args, **kwargs: _FakeResponse(HTTPStatus.FORBIDDEN),
        )
        with pytest.raises(RuntimeError, match="403"):
            client.list_all_deployments()

    def test_empty_resources_is_an_empty_workspace(self, client, monkeypatch):
        monkeypatch.setattr(
            client_module.requests,
            "get",
            lambda *args, **kwargs: _FakeResponse(HTTPStatus.OK, {"resources": []}),
        )
        assert client.list_all_deployments() == []

    @pytest.mark.parametrize(
        "payload",
        [{}, {"resources": {}}, {"resources": None}],
    )
    def test_missing_resources_fails_closed(self, client, monkeypatch, payload):
        monkeypatch.setattr(
            client_module.requests,
            "get",
            lambda *args, **kwargs: _FakeResponse(HTTPStatus.OK, payload),
        )
        with pytest.raises(RuntimeError, match="resources"):
            client.list_all_deployments()

    def test_non_object_body_fails_closed(self, client, monkeypatch):
        class _ListBody:
            status_code = HTTPStatus.OK
            text = "[]"

            def json(self) -> list:
                return []

        monkeypatch.setattr(
            client_module.requests,
            "get",
            lambda *args, **kwargs: _ListBody(),
        )
        with pytest.raises(RuntimeError, match="resources"):
            client.list_all_deployments()


class TestDeleteListener:
    def test_no_content_is_success(self, client, monkeypatch):
        urls: list[str] = []

        def _fake_delete(url, headers, timeout):
            urls.append(url)
            return _FakeResponse(HTTPStatus.NO_CONTENT)

        monkeypatch.setattr(client_module.requests, "delete", _fake_delete)
        assert client.delete_listener(_LISTENER_ID.upper()) is True
        assert urls == [f"{client.base_url}/listeners/{_LISTENER_ID}"]

    def test_not_found_raises(self, client, monkeypatch):
        monkeypatch.setattr(
            client_module.requests,
            "delete",
            lambda *args, **kwargs: _FakeResponse(HTTPStatus.NOT_FOUND),
        )
        with pytest.raises(RuntimeError, match="404"):
            client.delete_listener(_LISTENER_ID)

    def test_rejects_non_uuid_before_request(self, client, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("request should not be sent")

        monkeypatch.setattr(client_module.requests, "get", _boom)
        monkeypatch.setattr(client_module.requests, "delete", _boom)
        traversal = f"../deployments/{_LISTENER_ID}"
        fragment = f"{_LISTENER_ID}#fragment"
        for listener_id in (traversal, fragment):
            with pytest.raises(ValueError, match="UUID"):
                client.get_listener(listener_id)
            with pytest.raises(ValueError, match="UUID"):
                client.delete_listener(listener_id)

    def test_transport_error_outcome_is_unknown(self, client, monkeypatch):
        def _fake_delete(url, headers, timeout):
            raise requests.Timeout("timed out")

        monkeypatch.setattr(client_module.requests, "delete", _fake_delete)
        with pytest.raises(RuntimeError, match="outcome is unknown") as exc_info:
            client.delete_listener(_LISTENER_ID)
        assert isinstance(exc_info.value.__cause__, requests.Timeout)
