"""Tests for Locust UI workflow helpers."""

from unittest.mock import MagicMock, patch

import pytest
from ess_load_test.app_config import default_app_config
from ess_load_test.ui.workflow import (
    UiWorkflowConfig,
    UiWorkflowError,
    build_port_forward_argv,
    resolve_auth_header,
    run_preflight,
)


def test_resolved_region_defers_to_stack_output_when_unset() -> None:
    config = UiWorkflowConfig(
        app_config=default_app_config(),
        target_url="https://app.example.com",
    )
    assert config.resolved_region is None


def test_build_port_forward_argv_includes_profile() -> None:
    argv = build_port_forward_argv(
        master_instance_id="i-abc",
        region="us-east-1",
        profile="team-dev",
        local_port=8089,
    )
    assert argv[:3] == ["aws", "--profile", "team-dev"]
    assert "i-abc" in argv
    assert "localPortNumber=8089,portNumber=8089" in argv


def test_resolve_auth_header_prefers_explicit() -> None:
    resolve_token = MagicMock()
    header = resolve_auth_header(
        "X-API-KEY: secret", fetch_token=True, resolve_token=resolve_token
    )
    assert header == "X-API-KEY: secret"
    resolve_token.assert_not_called()


def test_resolve_auth_header_skips_fetch_when_disabled() -> None:
    resolve_token = MagicMock()
    assert (
        resolve_auth_header(None, fetch_token=False, resolve_token=resolve_token)
        is None
    )
    resolve_token.assert_not_called()


def test_run_preflight_requires_target_url() -> None:
    config = UiWorkflowConfig(
        app_config=default_app_config(),
        target_url="  ",
    )
    with pytest.raises(UiWorkflowError, match="Target URL"):
        run_preflight(config)


@patch("ess_load_test.ui.workflow.boto3.Session")
def test_run_preflight_checks_aws_credentials(mock_session_cls: MagicMock) -> None:
    identity = mock_session_cls.return_value.client.return_value.get_caller_identity
    identity.return_value = {
        "Account": "123",
    }
    config = UiWorkflowConfig(
        app_config=default_app_config(),
        target_url="https://app.example.com",
        profile="team-dev",
        region="us-east-1",
    )
    run_preflight(config)
    mock_session_cls.assert_called_once_with(
        profile_name="team-dev", region_name="us-east-1"
    )
