"""CLI interface for core_github using Click."""

import logging
import sys

import click
from decouple import config

from .github_api import GitHubCore

logger = logging.getLogger(__name__)

# Configure logging level based on LOG_LEVEL environment variable
LOG_LEVEL = config("LOG_LEVEL", default="INFO")
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=log_level)


@click.group()
def cli():
    """GitHub CLI tools for managing pull requests."""
    pass


@cli.command()
def get_prs():
    """
    Get all open pull requests across all repositories you have access to.

    PRs are logged at DEBUG level. Set LOG_LEVEL=DEBUG to see them.
    """
    token = config("GH_TOKEN")
    if not token:
        click.echo("Error: GH_TOKEN environment variable is not set", err=True)
        sys.exit(1)

    gh = GitHubCore(token=token)
    for i, pr in enumerate(gh.get_prs(), start=1):
        logger.info("%d. %s: %s - %s", i, pr.base.repo.name, pr.title, pr.html_url)


# Wrapper function for script entry point
# This allows the prs script to work directly without needing 'get-prs' subcommand
def get_prs_standalone():
    """Standalone entry point for the prs script."""
    # Insert 'get-prs' subcommand if not already present
    if len(sys.argv) > 1:
        if sys.argv[1] not in ["get-prs", "--help", "-h"]:
            # First arg is not a subcommand, insert 'get-prs'
            sys.argv.insert(1, "get-prs")
    else:
        # No arguments, default to 'get-prs'
        sys.argv.append("get-prs")
    cli()


if __name__ == "__main__":
    cli()
