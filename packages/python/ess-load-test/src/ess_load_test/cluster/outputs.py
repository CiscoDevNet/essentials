"""Read Pulumi stack outputs for the load test cluster."""

import json
import subprocess
from pathlib import Path


class StackOutputError(RuntimeError):
    """Raised when Pulumi stack outputs cannot be loaded."""


def load_stack_outputs(stack: str, project_dir: Path) -> dict[str, object]:
    """Load JSON stack outputs via the Pulumi CLI."""
    try:
        result = subprocess.run(
            ["uv", "run", "pulumi", "stack", "output", "--json", "--stack", stack],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = (
            "Failed to read Pulumi stack outputs. "
            f"Run `pulumi up` in {project_dir} first.\n{exc.stderr}"
        )
        raise StackOutputError(msg) from exc

    return json.loads(result.stdout)
