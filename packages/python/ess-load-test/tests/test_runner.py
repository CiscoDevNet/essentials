"""Tests for SSM runner helpers."""

from ess_load_test.app_config import default_app_config
from ess_load_test.cluster.runner import (
    _LOCUST_MASTER_PORT,
    _LOCUST_STATS_PORT,
    _WEB_UI_PORT,
    _auth_file_bootstrap_lines,
    _base64_write_file_command,
    _bootstrap_locust_script,
    _operator_scenario_env_exports,
    _reset_locust_cluster_script,
    _wrap_bash_script,
)


def test_wrap_bash_script_runs_under_bash() -> None:
    wrapped = _wrap_bash_script("set -euo pipefail\necho ok")
    assert wrapped.startswith("bash -c '")
    assert "pipefail" in wrapped


def test_reset_cluster_script_stops_locust_and_frees_ports() -> None:
    script = _reset_locust_cluster_script()
    assert "pkill -f '[/]locust'" in script
    assert f"fuser -k {_LOCUST_MASTER_PORT}/tcp" in script
    assert f"fuser -k {_LOCUST_STATS_PORT}/tcp" in script
    assert f"fuser -k {_WEB_UI_PORT}/tcp" in script


def test_base64_write_file_command_uses_shell_safe_decode() -> None:
    command = _base64_write_file_command("/opt/locustfile.py", "YWJj")
    assert "base64 -d" in command
    assert "/opt/locustfile.py" in command
    assert "python3 -c" not in command


def test_bootstrap_script_uses_install_dir() -> None:
    install_dir = default_app_config().locust_install_dir
    script = _bootstrap_locust_script(install_dir)
    assert install_dir in script


def test_auth_file_bootstrap_lines_uses_mktemp() -> None:
    lines = _auth_file_bootstrap_lines("Cookie: session=abc")
    assert "_auth_file=$(mktemp)" in lines
    assert 'base64 -d > "$_auth_file"' in lines
    assert 'export LOAD_TEST_AUTH_HEADER_FILE="$_auth_file"' in lines


def test_auth_file_bootstrap_lines_empty_when_no_header() -> None:
    assert _auth_file_bootstrap_lines(None) == ""
    assert _auth_file_bootstrap_lines("") == ""


def test_operator_scenario_env_exports_forwards_chat_tuning(monkeypatch) -> None:
    monkeypatch.delenv("LOAD_TEST_THINK_TIME", raising=False)
    assert _operator_scenario_env_exports() == ""

    monkeypatch.setenv("LOAD_TEST_THINK_TIME", "15,30")
    monkeypatch.setenv("LOAD_TEST_PRODUCT_SLUG", "__all__")
    monkeypatch.setenv("LOAD_TEST_AWS_PROFILE", "team-dev")
    exports = _operator_scenario_env_exports()
    assert "export LOAD_TEST_THINK_TIME='15,30'" in exports
    assert "export LOAD_TEST_PRODUCT_SLUG='__all__'" in exports
    assert "LOAD_TEST_AWS_PROFILE" not in exports
