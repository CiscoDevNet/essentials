"""CLI interface for core_github using Click."""

import json
import sys

import click

from .github_cli import get_prs as get_prs_data


@click.group()
def cli():
    """GitHub CLI tools for managing pull requests."""
    pass


@cli.command()
@click.option(
    "--org-repo",
    default="Cisco-DES/aide",
    help='Repository in format "org/repo" (e.g., "Cisco-DES/aide")',
)
@click.option(
    "--author",
    multiple=True,
    help="PR author filter. Can be specified multiple times for multiple authors.",
)
@click.option(
    "--state",
    type=click.Choice(["all", "open", "closed", "merged"], case_sensitive=False),
    default="all",
    help="PR state filter",
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of PRs to retrieve (default: GitHub CLI default of 30)",
)
@click.option(
    "--draft-status",
    type=click.Choice(["true", "false", "both"], case_sensitive=False),
    help="Draft filter: 'true' (only drafts), 'false' (exclude drafts), 'both' (include both)",
)
@click.option(
    "--is-mergeable",
    type=click.Choice(["true", "false", "both"], case_sensitive=False),
    help="Mergeable filter: 'true' (only mergeable), 'false' (only conflicts/failing checks), 'both' (include all)",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "csv", "json"], case_sensitive=False),
    default="json",
    help="Output format for the results",
)
def get_prs(org_repo, author, state, limit, draft_status, is_mergeable, output_format):
    """
    Get PRs for a particular org/repo using GitHub CLI.

    Examples:
        # Get all open PRs
        get-prs --state open

        # Get PRs by specific author
        get-prs --author username1 --author username2

        # Get only mergeable PRs
        get-prs --is-mergeable true

        # Output as CSV
        get-prs --output-format csv
    """
    # Convert Click multiple authors to list or None
    authors_list = list[str](author) if author else None

    # Convert draft_status string to boolean or None
    draft_status_bool = None
    if draft_status == "true":
        draft_status_bool = True
    elif draft_status == "false":
        draft_status_bool = False

    # Convert is_mergeable string to boolean or None
    is_mergeable_bool = None
    if is_mergeable == "true":
        is_mergeable_bool = True
    elif is_mergeable == "false":
        is_mergeable_bool = False

    # Get PR data
    prs_data = get_prs_data(
        org_repo=org_repo,
        authors=authors_list,
        state=state,
        limit=limit,
        draft_status=draft_status_bool,
        is_mergeable=is_mergeable_bool,
    )

    if not prs_data:
        click.echo(f"No PRs found for {org_repo}", err=True)
        return

    # Output based on format - write directly to stdout for shell redirection compatibility
    if output_format == "json":
        sys.stdout.write(json.dumps(prs_data, indent=2))
    elif output_format == "csv":
        # For CSV, we still need to convert to DataFrame
        from .github_cli import prs_data_to_dataframe

        df = prs_data_to_dataframe(prs_data, org_repo)
        sys.stdout.write(df.to_csv(index=False))
    else:  # table
        # For table, we still need to convert to DataFrame
        from .github_cli import prs_data_to_dataframe

        df = prs_data_to_dataframe(prs_data, org_repo)
        sys.stdout.write(df.to_string(index=False))
    sys.stdout.flush()


# Wrapper function for script entry point
# This allows the prs script to work directly without needing 'get-prs' subcommand
def get_prs_standalone():
    """Standalone entry point for the prs script."""
    import sys

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
