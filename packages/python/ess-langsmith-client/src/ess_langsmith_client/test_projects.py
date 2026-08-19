"""Tests for langsmith-client projects tracing-project management."""

from http import HTTPStatus
from typing import Any

import pytest

from ess_langsmith_client.tools import projects
from ess_langsmith_client.tools.projects import (
    TracingProjectClient,
    _delete_one,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def client() -> TracingProjectClient:
    return TracingProjectClient(api_key="test-key")


class TestGetProjectById:
    def test_returns_json_on_ok(self, client, monkeypatch):
        payload = {"id": "abc", "name": "hello-agent-dev", "run_count": 5}
        monkeypatch.setattr(
            projects.requests,
            "get",
            lambda *a, **k: _FakeResponse(HTTPStatus.OK, payload),
        )
        assert client.get_project_by_id("abc") == payload

    def test_returns_none_on_not_found(self, client, monkeypatch):
        monkeypatch.setattr(
            projects.requests,
            "get",
            lambda *a, **k: _FakeResponse(HTTPStatus.NOT_FOUND, text="missing"),
        )
        assert client.get_project_by_id("abc") is None

    def test_raises_on_server_error(self, client, monkeypatch):
        monkeypatch.setattr(
            projects.requests,
            "get",
            lambda *a, **k: _FakeResponse(
                HTTPStatus.INTERNAL_SERVER_ERROR, text="boom"
            ),
        )
        with pytest.raises(RuntimeError):
            client.get_project_by_id("abc")

    def test_requests_include_stats(self, client, monkeypatch):
        captured: dict[str, Any] = {}

        def _fake_get(url, *, headers, params, timeout):
            captured["url"] = url
            captured["params"] = params
            return _FakeResponse(HTTPStatus.OK, {"id": "abc"})

        monkeypatch.setattr(projects.requests, "get", _fake_get)
        client.get_project_by_id("abc")
        assert captured["params"] == {"include_stats": "true"}
        assert captured["url"].endswith("/api/v1/sessions/abc")


class TestDeleteOneTraceGuard:
    def _client_with_recorder(self, monkeypatch):
        client = TracingProjectClient(api_key="test-key")
        calls: list[tuple[str, bool]] = []

        def _record_delete(project_id: str, *, force: bool = False) -> bool:
            calls.append((project_id, force))
            return True

        monkeypatch.setattr(client, "delete_project", _record_delete)
        return client, calls

    def test_skips_project_with_traces_without_force(self, monkeypatch):
        client, calls = self._client_with_recorder(monkeypatch)
        project = {"id": "abc", "name": "hello-agent-dev", "run_count": 7}
        result = _delete_one(client, project, force=False)
        assert result == "skipped"
        assert calls == []

    def test_deletes_project_with_traces_when_forced(self, monkeypatch):
        client, calls = self._client_with_recorder(monkeypatch)
        project = {"id": "abc", "name": "hello-agent-dev", "run_count": 7}
        result = _delete_one(client, project, force=True)
        assert result == "deleted"
        assert calls == [("abc", True)]

    def test_deletes_empty_project_without_force(self, monkeypatch):
        client, calls = self._client_with_recorder(monkeypatch)
        project = {"id": "abc", "name": "hello-agent-dev", "run_count": 0}
        result = _delete_one(client, project, force=False)
        assert result == "deleted"
        assert calls == [("abc", False)]
