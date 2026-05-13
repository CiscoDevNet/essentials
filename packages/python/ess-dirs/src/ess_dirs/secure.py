"""Atomic file writes with restrictive permissions."""

from __future__ import annotations

import os
import tempfile

_OWNER_RW = 0o600  # owner read/write only -- protects cached secrets


def write_secure(path: str, content: str) -> None:
    """Write *content* to *path* atomically with owner-only permissions.

    Creates parent directories if needed, writes to a unique temporary file
    with ``0o600`` permissions, then atomically replaces the target via
    :func:`os.replace`.  This prevents other users from reading the file
    and avoids partial writes on crash.
    """
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path)
    try:
        os.fchmod(fd, _OWNER_RW)
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise
