#!/usr/bin/env python3
"""Report whether mcp.json files still contain inline secrets (never print values)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ENV_REF = re.compile(r"^\$\{env:[^}]+\}$")
_MIN_ARGC = 2
_USAGE_EXIT_CODE = 2


def scan(path: Path) -> tuple[bool, int]:
    """Return (has_inline_secrets, env_reference_count)."""
    if not path.is_file():
        return False, 0

    config = json.loads(path.read_text(encoding="utf-8"))
    has_inline = False
    env_refs = 0

    for server in config.get("mcpServers", {}).values():
        for block in (server.get("env"), server.get("headers")):
            if not isinstance(block, dict):
                continue
            for value in block.values():
                if not isinstance(value, str) or not value:
                    continue
                if ENV_REF.match(value):
                    env_refs += 1
                else:
                    has_inline = True

    return has_inline, env_refs


def main() -> int:
    if len(sys.argv) < _MIN_ARGC:
        print("usage: check-inline-secrets.py <mcp.json> [...]", file=sys.stderr)
        return _USAGE_EXIT_CODE

    exit_code = 0
    for arg in sys.argv[1:]:
        path = Path(arg).expanduser().resolve()
        if not path.is_file():
            print(f"{path}:missing")
            exit_code = 1
            continue
        has_inline, env_refs = scan(path)
        inline = "yes" if has_inline else "no"
        print(f"{path}:inline={inline} env_refs={env_refs}")
        if has_inline:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
