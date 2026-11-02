"""Tests for shared Locust load-test parameters."""

from ess_load_test.app_config import default_app_config
from ess_load_test.cli.load_params import (
    LoadTestParams,
    build_locust_load_flag_lines,
    config_users_json,
)
from ess_load_test.cluster.runner import (
    LoadTestRunRequest,
    LoadTestUiRequest,
    WorkerRuntimeEnv,
    _build_master_command,
    _build_master_ui_command,
    _build_worker_command,
)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def test_config_users_json_empty() -> None:
    assert config_users_json(()) is None


def test_config_users_json_builds_array() -> None:
    payload = config_users_json(("PagesUser", "BffUser"))
    assert payload is not None
    assert "PagesUser" in payload
    assert "BffUser" in payload


def test_build_locust_load_flag_lines_headless() -> None:
    params = LoadTestParams(users=50, spawn_rate=5.0, duration="5m")
    lines = build_locust_load_flag_lines(
        params,
        headless=True,
        shell_quote=_shell_quote,
    )
    assert "-u 50" in lines
    assert "-r 5.0" in lines
    assert "-t '5m'" in lines
    assert "--headless" in lines
    assert "--autostart" not in lines


def test_build_locust_load_flag_lines_ui_autostart() -> None:
    params = LoadTestParams(users=10, spawn_rate=2.0, autostart=True, autoquit=30)
    lines = build_locust_load_flag_lines(
        params,
        headless=False,
        shell_quote=_shell_quote,
    )
    assert "--autostart" in lines
    assert "--autoquit 30" in lines
    assert "--headless" not in lines


def test_build_locust_load_flag_lines_omits_autoquit_without_autostart() -> None:
    params = LoadTestParams(users=10, spawn_rate=2.0, autoquit=30)
    lines = build_locust_load_flag_lines(
        params,
        headless=False,
        shell_quote=_shell_quote,
    )
    assert "--autoquit" not in lines
    assert "--autostart" not in lines


def test_master_ui_command_includes_users_spawn_rate() -> None:
    app_config = default_app_config()
    request = LoadTestUiRequest(
        stack="dev",
        target_url="https://app.example.com",
        paths="/",
        scenario="mixed",
        load_params=LoadTestParams(users=50, spawn_rate=5.0, duration="10m"),
        auth_header=None,
        profile="team-dev",
        region="us-east-1",
    )
    command = _build_master_ui_command(
        request,
        app_config,
        master_private_ip="10.0.0.1",
        worker_count=2,
    )
    assert "-u 50" in command
    assert "-r 5.0" in command
    assert "-t '10m'" in command
    assert "export LOAD_TEST_USERS=50" in command
    assert "export LOAD_TEST_SPAWN_RATE=5.0" in command
    assert "export LOAD_TEST_DURATION='10m'" in command
    assert "export LOCUST_USERS=50" in command
    assert "export LOCUST_SPAWN_RATE=5.0" in command
    assert "export LOCUST_RUN_TIME='10m'" in command
    assert "--class-picker" in command
    assert "--autostart" not in command


def test_master_ui_command_config_users() -> None:
    app_config = default_app_config()
    request = LoadTestUiRequest(
        stack="dev",
        target_url="https://app.example.com",
        paths="/",
        scenario="mixed",
        load_params=LoadTestParams(
            user_classes=("PagesUser", "BffUser"),
        ),
        auth_header=None,
        profile="team-dev",
        region="us-east-1",
    )
    command = _build_master_ui_command(
        request,
        app_config,
        master_private_ip="10.0.0.1",
        worker_count=2,
    )
    assert "--config-users" in command
    assert "PagesUser" in command
    assert "BffUser" in command


def test_worker_command_exports_scenario_and_auth() -> None:
    app_config = default_app_config()
    runtime = WorkerRuntimeEnv(
        scenario="mixed",
        paths="/healthz",
        auth_header="Bearer example-token",
    )
    command = _build_worker_command(app_config, "10.0.0.1", runtime)
    assert "export LOAD_TEST_SCENARIO='mixed'" in command
    assert "export LOAD_TEST_PATHS='/healthz'" in command
    assert "export LOAD_TEST_AUTH_HEADER='Bearer example-token'" in command
    assert "--worker" in command


def test_master_command_headless_exports() -> None:
    app_config = default_app_config()
    _remote_csv_prefix = "/opt/my-load-test/stats"
    _remote_html_path = "/opt/my-load-test/report.html"

    request = LoadTestRunRequest(
        stack="dev",
        target_url="https://app.example.com",
        paths="/",
        scenario="default",
        load_params=LoadTestParams(
            users=10,
            spawn_rate=2.0,
            duration="1m",
            csv_prefix=_remote_csv_prefix,
            html_path=_remote_html_path,
            reset_stats=True,
        ),
        auth_header=None,
        profile="team-dev",
        region="us-east-1",
    )
    command = _build_master_command(
        request,
        app_config,
        master_private_ip="10.0.0.1",
        worker_count=2,
    )
    assert "--headless" in command
    assert f"--csv '{_remote_csv_prefix}'" in command
    assert f"--html '{_remote_html_path}'" in command
    assert "--reset-stats" in command
