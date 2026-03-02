"""Secret management utilities for LangSmith deployments."""

import os

# Environment variables to auto-detect as deployment secrets.
# These are common API keys needed by LangGraph agents at runtime.
AUTO_DETECT_KEYS = [
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
    "TAVILY_API_KEY",
]


def get_env_secrets() -> list[dict[str, str]]:
    """Get deployment secrets from well-known environment variables."""
    secrets = []
    for key in AUTO_DETECT_KEYS:
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


def merge_secrets(cli_secrets: tuple[str, ...] | list[str]) -> list[dict[str, str]]:
    """Merge CLI secrets with auto-detected secrets from environment.

    CLI secrets take precedence over auto-detected ones.
    """
    all_secrets = parse_secrets(list(cli_secrets))
    env_secrets = get_env_secrets()
    for secret in env_secrets:
        if not any(s["name"] == secret["name"] for s in all_secrets):
            all_secrets.append(secret)
    return all_secrets
