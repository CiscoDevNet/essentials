"""Tests for langsmith-client listeners list and delete."""

from typing import Any

import pytest
from click.testing import CliRunner

from ess_langsmith_client.tools import listeners
from ess_langsmith_client.tools.listeners import cli

_IDLE_ID = "11111111-1111-1111-1111-111111111111"
_BUSY_ID = "22222222-2222-2222-2222-222222222222"


class _FakeClient:
    """Stands in for ControlPlaneClient; records delete calls."""

    workspace_id = "test-ws"

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def list_listeners(self) -> dict[str, Any]:
        return {"resources": [self.get_listener(_IDLE_ID)]}

    def get_listener(self, listener_id: str) -> dict[str, Any]:
        return {
            "id": listener_id,
            "compute_id": f"cluster-{listener_id[:4]}",
            "compute_config": {"k8s_namespaces": ["default"]},
            "created_at": "2026-04-06T00:00:00Z",
            "version": "0.13.9",
        }

    def list_all_deployments(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "dep-1",
                "name": "live-agent",
                "source_config": {"listener_id": _BUSY_ID},
            },
        ]

    def delete_listener(self, listener_id: str) -> bool:
        self.deleted.append(listener_id)
        return True


@pytest.fixture
def fake_client(monkeypatch) -> _FakeClient:
    client = _FakeClient()
    monkeypatch.setattr(listeners, "create_client", lambda *args, **kwargs: client)
    return client


def _invoke(args: list[str], stdin: str | None = None):
    return CliRunner().invoke(cli, [*args, "--api-key", "test-key"], input=stdin)


class TestList:
    def test_table_shows_compute_id_and_version(self, fake_client):
        result = _invoke(["list"])
        assert result.exit_code == 0
        assert "cluster-1111" in result.output
        assert "0.13.9" in result.output


class TestDelete:
    def test_dry_run_deletes_nothing(self, fake_client):
        result = _invoke(["delete", _IDLE_ID, "--dry-run"])
        assert result.exit_code == 0
        assert _IDLE_ID in result.output
        assert "Dry run" in result.output
        assert fake_client.deleted == []

    def test_dry_run_wins_over_yes(self, fake_client):
        result = _invoke(["delete", _IDLE_ID, "--dry-run", "--yes"])
        assert result.exit_code == 0
        assert fake_client.deleted == []

    def test_yes_skips_prompt(self, fake_client):
        result = _invoke(["delete", _IDLE_ID, "--yes"])
        assert result.exit_code == 0
        assert fake_client.deleted == [_IDLE_ID]

    def test_duplicate_ids_deleted_once(self, fake_client):
        result = _invoke(["delete", _IDLE_ID, _IDLE_ID, "--yes"])
        assert result.exit_code == 0
        assert fake_client.deleted == [_IDLE_ID]

    def test_deletes_id_returned_by_lookup(self, fake_client):
        alias = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        original = fake_client.get_listener

        def _get(listener_id: str) -> dict[str, Any]:
            listener = original(listener_id)
            listener["id"] = _IDLE_ID
            return listener

        fake_client.get_listener = _get
        result = _invoke(["delete", alias, _IDLE_ID, "--yes"])
        assert result.exit_code == 0
        assert fake_client.deleted == [_IDLE_ID]

    def test_in_use_check_uses_resolved_id(self, fake_client):
        alias = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        original = fake_client.get_listener

        def _get(listener_id: str) -> dict[str, Any]:
            listener = original(listener_id)
            if listener_id == alias:
                listener["id"] = _BUSY_ID
            return listener

        fake_client.get_listener = _get
        result = _invoke(["delete", alias, "--yes"])
        assert result.exit_code != 0
        assert "live-agent" in result.output
        assert _BUSY_ID in result.output
        assert fake_client.deleted == []

    def test_invalid_id_is_a_click_error(self, fake_client):
        def _get(listener_id: str) -> dict[str, Any]:
            raise ValueError(f"Listener ID must be a UUID, got {listener_id!r}.")

        fake_client.get_listener = _get
        result = _invoke(["delete", "../deployments/not-a-uuid", "--yes"])
        assert result.exit_code != 0
        assert "UUID" in result.output
        assert "Traceback" not in result.output
        assert fake_client.deleted == []

    def test_recheck_after_confirm_blocks_new_placement(self, fake_client, monkeypatch):
        monkeypatch.setattr(listeners, "_is_interactive", lambda: True)
        phases: list[str] = []

        def _list() -> list[dict[str, Any]]:
            phases.append("before" if not phases else "after")
            if phases == ["before"]:
                return []
            return [
                {
                    "id": "dep-new",
                    "name": "moved-on",
                    "source_config": {"listener_id": _IDLE_ID},
                }
            ]

        fake_client.list_all_deployments = _list
        result = _invoke(["delete", _IDLE_ID], stdin="y\n")
        assert result.exit_code != 0
        assert "moved-on" in result.output
        assert fake_client.deleted == []
        assert phases == ["before", "after"]

    def test_refuses_listener_with_deployments(self, fake_client):
        result = _invoke(["delete", _IDLE_ID, _BUSY_ID, "--yes"])
        assert result.exit_code != 0
        assert "live-agent" in result.output
        assert fake_client.deleted == []

    def test_non_interactive_without_yes_fails(self, fake_client):
        result = _invoke(["delete", _IDLE_ID])
        assert result.exit_code != 0
        assert "--yes" in result.output
        assert fake_client.deleted == []

    def test_interactive_decline_aborts(self, fake_client, monkeypatch):
        monkeypatch.setattr(listeners, "_is_interactive", lambda: True)
        result = _invoke(["delete", _IDLE_ID], stdin="n\n")
        assert result.exit_code != 0
        assert fake_client.deleted == []

    def test_interactive_accept_deletes(self, fake_client, monkeypatch):
        monkeypatch.setattr(listeners, "_is_interactive", lambda: True)
        result = _invoke(["delete", _IDLE_ID], stdin="y\n")
        assert result.exit_code == 0
        assert fake_client.deleted == [_IDLE_ID]
