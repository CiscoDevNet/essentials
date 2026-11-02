"""Tests for local port-forward troubleshooting helpers."""

from unittest.mock import MagicMock, patch

import pytest
from ess_load_test.ui.local_port import (
    LocalPortExpectation,
    check_local_port,
    cleanup_stale_port_forward,
    is_local_port_listening,
    kill_stale_ssm_port_forward,
)


@patch("ess_load_test.ui.local_port.subprocess.run")
def test_is_local_port_listening_true_when_lsof_succeeds(mock_run) -> None:
    mock_run.return_value.returncode = 0
    assert is_local_port_listening(8089) is True
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0][:2] == ["lsof", "-i"]


@patch("ess_load_test.ui.local_port.subprocess.run")
def test_is_local_port_listening_false_when_lsof_fails(mock_run) -> None:
    mock_run.return_value.returncode = 1
    assert is_local_port_listening(8089) is False


@patch("ess_load_test.ui.local_port.subprocess.run")
def test_kill_stale_ssm_port_forward_counts_matches(mock_run) -> None:
    mock_run.side_effect = [
        MagicMock(returncode=0),
        MagicMock(returncode=1),
    ]
    assert kill_stale_ssm_port_forward(8089) == 1
    pkill_pattern_count = 2
    assert mock_run.call_count == pkill_pattern_count


@patch("ess_load_test.ui.local_port.is_local_port_listening", return_value=False)
def test_check_local_port_free_succeeds_when_port_free(_mock_listening) -> None:
    check_local_port(8089, expect=LocalPortExpectation.FREE)


@patch("ess_load_test.ui.local_port.is_local_port_listening", return_value=True)
def test_check_local_port_free_fails_when_port_in_use(_mock_listening) -> None:
    with pytest.raises(RuntimeError, match="expected free"):
        check_local_port(8089, expect=LocalPortExpectation.FREE)


@patch("ess_load_test.ui.local_port.is_local_port_listening", return_value=True)
def test_check_local_port_listening_succeeds_when_port_in_use(_mock_listening) -> None:
    check_local_port(8089, expect=LocalPortExpectation.LISTENING)


@patch("ess_load_test.ui.local_port.is_local_port_listening", return_value=False)
def test_check_local_port_listening_fails_when_port_free(_mock_listening) -> None:
    with pytest.raises(RuntimeError, match="expected listening"):
        check_local_port(8089, expect=LocalPortExpectation.LISTENING)


@patch("ess_load_test.ui.local_port.kill_stale_ssm_port_forward", return_value=2)
@patch("ess_load_test.ui.local_port.is_local_port_listening", return_value=False)
def test_cleanup_stale_port_forward(_mock_listening, mock_kill) -> None:
    killed_pattern_count = 2
    assert cleanup_stale_port_forward(8089) == killed_pattern_count
    mock_kill.assert_called_once_with(8089)
