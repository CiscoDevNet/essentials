"""Installed package version for CLI --version output."""

from importlib.metadata import PackageNotFoundError, version


def get_package_version() -> str:
    """Return the installed ess-langsmith-client distribution version."""
    try:
        return version("ess-langsmith-client")
    except PackageNotFoundError:
        return "0.0.0"
