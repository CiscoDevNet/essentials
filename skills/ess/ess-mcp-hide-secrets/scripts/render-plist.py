#!/usr/bin/env python3
"""Render the LaunchAgent plist from its template with absolute, resolved paths.

Usage: render-plist.py <template> <dest> <label> <loader> <mcp.env> <log file>

The LaunchAgent runs at login without the shell's XDG variables, so every path it
needs is written into the plist at install time. plistlib escapes any path safely.
"""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

_ARGC = 7
_USAGE_EXIT_CODE = 2


def render(
    template: Path, label: str, loader: str, mcp_env: str, log_file: str
) -> dict:
    """Return the template's plist with the label and loader arguments filled in."""
    for path in (loader, mcp_env, log_file):
        if not os.path.isabs(path):
            raise ValueError(f"path must be absolute: {path}")

    with template.open("rb") as handle:
        plist = plistlib.load(handle)

    placeholders = {
        "LOADER_PATH": loader,
        "MCP_ENV_PATH": mcp_env,
        "LOG_PATH": log_file,
    }
    plist["Label"] = label
    plist["ProgramArguments"] = [
        placeholders.get(arg, arg) for arg in plist["ProgramArguments"]
    ]
    plist["StandardErrorPath"] = log_file
    return plist


def main() -> int:
    if len(sys.argv) != _ARGC:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return _USAGE_EXIT_CODE

    template, dest, label, loader, mcp_env, log_file = sys.argv[1:]
    try:
        plist = render(Path(template), label, loader, mcp_env, log_file)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    with open(dest, "wb") as handle:
        plistlib.dump(plist, handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
