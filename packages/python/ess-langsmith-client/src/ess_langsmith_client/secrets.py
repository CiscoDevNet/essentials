"""Secret management utilities for LangSmith deployments."""

import os
from collections.abc import Iterable

_PLATFORM_MANAGED_SECRET_NAMES = frozenset(
    {
        "LANGSMITH_CONTROL_PLANE_API_KEY",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_PROJECT",
        "LANGSMITH_TRACING",
    }
)


def get_env_secrets(keys: Iterable[str]) -> list[dict[str, str]]:
    """Read the named environment variables as deployment secrets.

    Args:
        keys: Environment variable names to look up.

    Returns:
        A ``{"name", "value"}`` entry for each key that is set and non-empty,
        in the order the keys were given.
    """
    secrets = []
    for key in keys:
        value = os.environ.get(key)
        if value:
            secrets.append({"name": key, "value": value})
    return secrets


def parse_secrets(secret_args: list[str] | None) -> list[dict[str, str]]:
    """Parse secrets from command line arguments (NAME=VALUE format)."""
    secrets = []
    if secret_args:
        for secret in secret_args:
            name, value = secret.split("=", 1)
            secrets.append({"name": name, "value": value})
    return secrets


def merge_secrets(
    cli_secrets: tuple[str, ...] | list[str],
    auto_detect_keys: Iterable[str] = (),
) -> list[dict[str, str]]:
    """Merge explicitly passed secrets with ones read from the environment.

    Nothing is read from the environment unless ``auto_detect_keys`` names it, so
    a deployment never receives a credential the caller did not ask for. Callers
    that want the convenience of picking keys up from the environment pass their
    own list.

    Args:
        cli_secrets: ``NAME=VALUE`` strings, typically from a ``--secret`` flag.
        auto_detect_keys: Environment variable names to fall back to.

    Returns:
        The merged list. ``cli_secrets`` win on name collisions. Names managed
        by the LangSmith control plane are omitted because the deployment API
        rejects customer attempts to set them.
    """
    all_secrets = parse_secrets(list(cli_secrets))
    for secret in get_env_secrets(auto_detect_keys):
        if not any(existing["name"] == secret["name"] for existing in all_secrets):
            all_secrets.append(secret)
    filtered_secrets = [
        secret
        for secret in all_secrets
        if secret["name"] not in _PLATFORM_MANAGED_SECRET_NAMES
    ]
    if all_secrets and not filtered_secrets:
        names = ", ".join(sorted(secret["name"] for secret in all_secrets))
        raise ValueError(
            "All requested deployment secrets are managed by the LangSmith "
            f"control plane and cannot be submitted: {names}"
        )
    return filtered_secrets
