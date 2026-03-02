"""Project metadata utilities for reading pyproject.toml."""

import tomllib
from pathlib import Path
from typing import NamedTuple


class ProjectInfo(NamedTuple):
    """Project metadata from pyproject.toml."""

    name: str
    version: str


def get_project_info(start_path: Path | None = None) -> ProjectInfo | None:
    """
    Read project name and version from pyproject.toml.

    Searches from start_path (default: cwd) up to the filesystem root.
    Returns None if no pyproject.toml is found or it lacks project metadata.
    """
    path = start_path or Path.cwd()

    # Search up the directory tree
    for directory in [path, *path.parents]:
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            try:
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                project = data.get("project", {})
                name = project.get("name")
                version = project.get("version")
                if name and version:
                    return ProjectInfo(name=name, version=version)
            except (tomllib.TOMLDecodeError, OSError):
                pass
    return None
