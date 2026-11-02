"""Tests for GitHub deployment CLI validation."""

from click import UsageError
from click.testing import CliRunner

from ess_langsmith_client.tools.deploy_github import cli


def test_reserved_only_secret_is_an_operator_facing_error() -> None:
    result = CliRunner().invoke(
        cli,
        [
            "create",
            "--repo-url",
            "https://git.example.com/owner/repository",
            "--secret",
            "LANGSMITH_CONTROL_PLANE_API_KEY=platform-owned",
        ],
    )

    assert result.exit_code == UsageError.exit_code
    assert "Error: All requested deployment secrets are managed" in result.output
    assert "LANGSMITH_CONTROL_PLANE_API_KEY" in result.output
