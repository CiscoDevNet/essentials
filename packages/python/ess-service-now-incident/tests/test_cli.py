"""Unit tests for the build_cli factory."""

from __future__ import annotations

import json
from unittest.mock import patch

import click
from click.testing import CliRunner
from ess_service_now_incident.cli import INSTANCE_ENV_VAR, build_cli

_INCIDENT = {
    "number": "INC0000001",
    "sys_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "short_description": "Example short description",
    "description": "Description body.",
}

_PATCH_TARGET = "ess_service_now_incident.cli.get_incident"


# Use ``None`` (not ``""``) to mark the env var as unset in ``CliRunner.invoke``.
# ``CliRunner`` removes any key whose value is ``None`` from the child env, which
# is the explicit, version-independent way to say "no SERVICENOW_INSTANCE here".
_ENV_UNSET: dict[str, str | None] = {INSTANCE_ENV_VAR: None}


def _invoke(
    cli: click.Command,
    args: list[str],
    env: dict[str, str | None] | None = None,
):
    """Invoke ``cli`` with ``get_incident`` mocked, returning the mock and result."""
    runner = CliRunner()
    with patch(_PATCH_TARGET, return_value=_INCIDENT) as mock_get:
        result = runner.invoke(cli, args, env=env)
    return mock_get, result


class TestBuildCli:
    def test_returns_click_command(self):
        cli = build_cli()
        assert isinstance(cli, click.Command)


class TestInstancePrecedence:
    """Runtime tests for the --instance / env var / default precedence."""

    def test_no_default_and_no_env_passes_none(self):
        cli = build_cli(default_instance=None)
        mock_get, result = _invoke(cli, ["INC0000001"], env=_ENV_UNSET)
        assert result.exit_code == 0
        assert mock_get.call_args.kwargs["instance"] is None

    def test_explicit_default_used_when_no_env(self):
        cli = build_cli(default_instance="example.service-now.com")
        mock_get, result = _invoke(cli, ["INC0000001"], env=_ENV_UNSET)
        assert result.exit_code == 0
        assert mock_get.call_args.kwargs["instance"] == "example.service-now.com"

    def test_env_var_used_when_no_explicit_default(self):
        cli = build_cli()
        mock_get, result = _invoke(
            cli, ["INC0000001"], env={INSTANCE_ENV_VAR: "acme.service-now.com"}
        )
        assert result.exit_code == 0
        assert mock_get.call_args.kwargs["instance"] == "acme.service-now.com"

    def test_env_var_overrides_explicit_default(self):
        cli = build_cli(default_instance="explicit.service-now.com")
        mock_get, result = _invoke(
            cli, ["INC0000001"], env={INSTANCE_ENV_VAR: "from-env.service-now.com"}
        )
        assert result.exit_code == 0
        assert mock_get.call_args.kwargs["instance"] == "from-env.service-now.com"

    def test_flag_overrides_env_var_and_default(self):
        cli = build_cli(default_instance="explicit.service-now.com")
        mock_get, result = _invoke(
            cli,
            ["--instance", "flag.service-now.com", "INC0000001"],
            env={INSTANCE_ENV_VAR: "from-env.service-now.com"},
        )
        assert result.exit_code == 0
        assert mock_get.call_args.kwargs["instance"] == "flag.service-now.com"

    def test_empty_env_var_falls_back_to_default(self):
        # An empty SERVICENOW_INSTANCE is intentionally treated as "unset" by
        # Click's envvar plumbing, so the baked-in default still wins.  Pin
        # this contract: users who export an empty value won't accidentally
        # send "" through to get_incident().
        cli = build_cli(default_instance="explicit.service-now.com")
        mock_get, result = _invoke(cli, ["INC0000001"], env={INSTANCE_ENV_VAR: ""})
        assert result.exit_code == 0
        assert mock_get.call_args.kwargs["instance"] == "explicit.service-now.com"


class TestCliInvocation:
    def test_prints_description_by_default(self):
        cli = build_cli(default_instance="example.service-now.com")
        runner = CliRunner()
        with patch(_PATCH_TARGET, return_value=_INCIDENT):
            result = runner.invoke(cli, ["INC0000001"], env=_ENV_UNSET)
        assert result.exit_code == 0
        assert "Description body." in result.output

    def test_json_flag_emits_json(self):
        cli = build_cli(default_instance="example.service-now.com")
        runner = CliRunner()
        with patch(_PATCH_TARGET, return_value=_INCIDENT):
            result = runner.invoke(cli, ["--json", "INC0000001"], env=_ENV_UNSET)
        assert result.exit_code == 0
        assert json.loads(result.output) == _INCIDENT

    def test_falls_back_to_short_description(self):
        cli = build_cli(default_instance="example.service-now.com")
        runner = CliRunner()
        payload = {**_INCIDENT, "description": "   "}
        with patch(_PATCH_TARGET, return_value=payload):
            result = runner.invoke(cli, ["INC0000001"], env=_ENV_UNSET)
        assert result.exit_code == 0
        assert "Example short description" in result.output

    def test_exit_nonzero_when_both_descriptions_empty(self):
        cli = build_cli(default_instance="example.service-now.com")
        runner = CliRunner()
        payload = {**_INCIDENT, "description": "", "short_description": ""}
        with patch(_PATCH_TARGET, return_value=payload):
            result = runner.invoke(cli, ["INC0000001"], env=_ENV_UNSET)
        assert result.exit_code == 1
