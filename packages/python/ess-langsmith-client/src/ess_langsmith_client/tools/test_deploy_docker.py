"""Tests for Docker deployment CLI validation."""

import pytest
from click import UsageError
from click.testing import CliRunner

from ess_langsmith_client.tools.deploy_docker import cli


@pytest.mark.parametrize(
    "args",
    [
        [
            "create",
            "--deployment",
            "agent-test",
            "--image-uri",
            "registry.example.com/agent:test",
        ],
        [
            "update",
            "--deployment-id",
            "deployment-id",
            "--image-uri",
            "registry.example.com/agent:test",
        ],
    ],
)
def test_reserved_only_secret_is_an_operator_facing_error(args: list[str]) -> None:
    result = CliRunner().invoke(
        cli,
        [
            *args,
            "--secret",
            "LANGSMITH_CONTROL_PLANE_API_KEY=platform-owned",
        ],
    )

    assert result.exit_code == UsageError.exit_code
    assert "Error: All requested deployment secrets are managed" in result.output
    assert "LANGSMITH_CONTROL_PLANE_API_KEY" in result.output
