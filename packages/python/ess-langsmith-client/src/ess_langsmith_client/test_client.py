"""Tests for ControlPlaneClient deployment resolution."""

import pytest

from ess_langsmith_client.client import ControlPlaneClient


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
