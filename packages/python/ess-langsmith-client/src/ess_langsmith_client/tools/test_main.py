"""Tests for the unified langsmith-client root CLI group."""

from click.testing import CliRunner

from ess_langsmith_client.tools.main import cli

_EXPECTED_SUBCOMMANDS = {
    "keys",
    "workspaces",
    "listeners",
    "projects",
    "control-plane",
    "build",
    "deploy",
    "test-deployed",
}

_EXPECTED_DEPLOY_SUBCOMMANDS = {"docker", "github"}


def test_root_group_registers_expected_subcommands():
    """The root group exposes every consolidated subcommand."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for subcommand in _EXPECTED_SUBCOMMANDS:
        assert subcommand in result.output


def test_deploy_group_registers_docker_and_github():
    """The deploy subgroup nests docker and github."""
    runner = CliRunner()
    result = runner.invoke(cli, ["deploy", "--help"])
    assert result.exit_code == 0
    for subcommand in _EXPECTED_DEPLOY_SUBCOMMANDS:
        assert subcommand in result.output


def test_registered_command_names_match_expected():
    """Guard against accidental additions/removals in the command mapping."""
    assert set(cli.commands) == _EXPECTED_SUBCOMMANDS
    deploy_group = cli.commands["deploy"]
    assert set(deploy_group.commands) == _EXPECTED_DEPLOY_SUBCOMMANDS
