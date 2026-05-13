"""Unit tests for get_incident with mocked BrowserSession."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from ess_service_now_incident.client import get_incident
from ess_service_now_incident.exceptions import (
    APIError,
    AuthenticationError,
    IncidentNotFoundError,
    InputParseError,
)

_INSTANCE = "example.service-now.com"
_INCIDENT = {
    "number": "INC0000001",
    "sys_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "short_description": "Example short description",
    "description": "Full description here.",
}


def _make_session(
    *,
    evaluate_return: dict | None = None,
    is_auth_redirect: bool = False,
    wait_for_login_error: Exception | None = None,
) -> MagicMock:
    page = MagicMock()
    page.url = f"https://{_INSTANCE}/"

    if evaluate_return is None:
        evaluate_return = {
            "status": 200,
            "ok": True,
            "body": json.dumps({"result": _INCIDENT}),
        }
    page.evaluate.return_value = evaluate_return

    session = MagicMock()
    session.new_page.return_value = page
    session.is_auth_redirect.return_value = is_auth_redirect
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    if wait_for_login_error:
        session.wait_for_login.side_effect = wait_for_login_error

    return session


_PATCH_TARGET = "ess_service_now_incident.client.BrowserSession"


class TestGetIncidentSuccess:
    def test_returns_single_result(self):
        session = _make_session()
        with patch(_PATCH_TARGET, return_value=session):
            result = get_incident("INC0000001", instance=_INSTANCE)
        assert result == _INCIDENT

    def test_returns_first_from_list_result(self):
        body = json.dumps({"result": [_INCIDENT]})
        session = _make_session(
            evaluate_return={"status": 200, "ok": True, "body": body},
        )
        with patch(_PATCH_TARGET, return_value=session):
            result = get_incident("INC0000001", instance=_INSTANCE)
        assert result == _INCIDENT

    def test_url_argument_supplies_instance(self):
        session = _make_session()
        url = f"https://{_INSTANCE}/now/sow/record/incident/{_INCIDENT['sys_id']}"
        with patch(_PATCH_TARGET, return_value=session):
            result = get_incident(url)
        assert result == _INCIDENT


class TestGetIncidentInstanceValidation:
    def test_rejects_non_servicenow_instance(self):
        with pytest.raises(InputParseError, match="not a ServiceNow domain"):
            get_incident("INC0000001", instance="evil.com")

    def test_requires_instance_for_bare_number(self):
        with pytest.raises(InputParseError, match="No ServiceNow instance"):
            get_incident("INC0000001")

    def test_accepts_valid_instance(self):
        session = _make_session()
        with patch(_PATCH_TARGET, return_value=session):
            result = get_incident(
                "INC0000001",
                instance="acme.service-now.com",
            )
        assert result == _INCIDENT


class TestGetIncidentAuthErrors:
    def test_http_401_raises_authentication_error(self):
        session = _make_session(
            evaluate_return={
                "status": 401,
                "ok": False,
                "body": "Unauthorized",
            },
        )
        with (
            patch(_PATCH_TARGET, return_value=session),
            pytest.raises(AuthenticationError, match="HTTP 401"),
        ):
            get_incident("INC0000001", instance=_INSTANCE)

    def test_http_403_raises_authentication_error(self):
        session = _make_session(
            evaluate_return={
                "status": 403,
                "ok": False,
                "body": "Forbidden",
            },
        )
        with (
            patch(_PATCH_TARGET, return_value=session),
            pytest.raises(AuthenticationError, match="HTTP 403"),
        ):
            get_incident("INC0000001", instance=_INSTANCE)

    def test_sso_timeout_raises_authentication_error(self):
        session = _make_session(
            is_auth_redirect=True,
            wait_for_login_error=TimeoutError("SSO timed out"),
        )
        with (
            patch(_PATCH_TARGET, return_value=session),
            pytest.raises(AuthenticationError, match="timed out"),
        ):
            get_incident("INC0000001", instance=_INSTANCE)


class TestGetIncidentApiErrors:
    def test_non_ok_http_raises_api_error(self):
        session = _make_session(
            evaluate_return={
                "status": 500,
                "ok": False,
                "body": "Internal Server Error",
            },
        )
        with (
            patch(_PATCH_TARGET, return_value=session),
            pytest.raises(APIError, match="HTTP 500"),
        ):
            get_incident("INC0000001", instance=_INSTANCE)

    def test_invalid_json_raises_api_error(self):
        session = _make_session(
            evaluate_return={
                "status": 200,
                "ok": True,
                "body": "<html>Auth page</html>",
            },
        )
        with (
            patch(_PATCH_TARGET, return_value=session),
            pytest.raises(APIError, match="Expected JSON"),
        ):
            get_incident("INC0000001", instance=_INSTANCE)

    def test_unexpected_response_shape_raises_api_error(self):
        session = _make_session(
            evaluate_return={
                "status": 200,
                "ok": True,
                "body": json.dumps({"error": "something"}),
            },
        )
        with (
            patch(_PATCH_TARGET, return_value=session),
            pytest.raises(APIError, match="Unexpected API response"),
        ):
            get_incident("INC0000001", instance=_INSTANCE)

    def test_empty_list_raises_not_found(self):
        session = _make_session(
            evaluate_return={
                "status": 200,
                "ok": True,
                "body": json.dumps({"result": []}),
            },
        )
        with (
            patch(_PATCH_TARGET, return_value=session),
            pytest.raises(IncidentNotFoundError, match="No incident found"),
        ):
            get_incident("INC0000001", instance=_INSTANCE)
