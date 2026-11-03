"""Tests for Locust scenario runtime helpers."""

import pytest
from ess_load_test.locust.runtime import (
    InvalidScenarioError,
    mark_response_failure,
    normalize_scenario,
)


class TestNormalizeScenario:
    def test_default_when_empty(self) -> None:
        assert normalize_scenario(None) == "default"
        assert normalize_scenario("  ") == "default"

    def test_accepts_known_scenarios(self) -> None:
        scenarios = frozenset({"default", "pages"})
        assert normalize_scenario("pages", valid_scenarios=scenarios) == "pages"

    def test_rejects_unknown_scenario(self) -> None:
        with pytest.raises(InvalidScenarioError, match="agent"):
            normalize_scenario("agent")


class TestMarkResponseFailure:
    def test_5xx_always_fails(self) -> None:
        response = _FakeResponse(503)
        mark_response_failure(response, strict=False)
        assert response.failed is True
        assert response.succeeded is False

    def test_4xx_strict_only(self) -> None:
        response = _FakeResponse(401)
        mark_response_failure(response, strict=False)
        assert response.failed is False
        assert response.succeeded is False
        mark_response_failure(response, strict=True)
        assert response.failed is True

    def test_accept_statuses_marks_success(self) -> None:
        response = _FakeResponse(400)
        mark_response_failure(response, accept_statuses=frozenset({400, 429}))
        assert response.failed is False
        assert response.succeeded is True

    def test_accept_statuses_does_not_override_5xx(self) -> None:
        response = _FakeResponse(503)
        mark_response_failure(response, accept_statuses=frozenset({503}))
        assert response.failed is True
        assert response.succeeded is False


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.failed = False
        self.succeeded = False
        self.message = ""

    def failure(self, message: str) -> None:
        self.failed = True
        self.message = message

    def success(self) -> None:
        self.succeeded = True
