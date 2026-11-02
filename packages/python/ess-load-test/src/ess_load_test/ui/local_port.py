"""Local port-forward helpers for SSM tunnel troubleshooting."""

from __future__ import annotations

import subprocess
from enum import Enum


class LocalPortExpectation(str, Enum):
    """Expected state of a local TCP port."""

    FREE = "free"
    LISTENING = "listening"


def is_local_port_listening(port: int) -> bool:
    """Return True when a process is listening on *port*."""
    result = subprocess.run(
        ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-P", "-n"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def kill_stale_ssm_port_forward(port: int) -> int:
    """Stop local SSM port-forward processes for *port*."""
    patterns = (
        rf"session-manager-plugin.*{port}",
        rf"ssm start-session.*localPortNumber={port}",
    )
    killed = 0
    for pattern in patterns:
        result = subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            killed += 1
    return killed


def check_local_port(port: int, *, expect: LocalPortExpectation) -> None:
    """Raise ``RuntimeError`` when the port does not match *expect*."""
    listening = is_local_port_listening(port)
    if expect == LocalPortExpectation.FREE and listening:
        msg = f"Port {port} is in use (expected free)."
        raise RuntimeError(msg)
    if expect == LocalPortExpectation.LISTENING and not listening:
        msg = f"Port {port} is free (expected listening)."
        raise RuntimeError(msg)


def cleanup_stale_port_forward(port: int) -> int:
    """Kill stale SSM forwards and verify *port* is free."""
    killed = kill_stale_ssm_port_forward(port)
    check_local_port(port, expect=LocalPortExpectation.FREE)
    return killed
