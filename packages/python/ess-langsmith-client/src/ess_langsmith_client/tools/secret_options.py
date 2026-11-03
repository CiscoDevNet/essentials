"""Click-facing validation for deployment secret options."""

import click

from ess_langsmith_client.secrets import merge_secrets


def merge_cli_secrets(secrets: tuple[str, ...]) -> list[dict[str, str]]:
    """Merge CLI secrets and present validation failures as usage errors."""
    try:
        return merge_secrets(secrets)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
