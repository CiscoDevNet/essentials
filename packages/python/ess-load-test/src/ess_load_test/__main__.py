"""CLI entry point for ess-load-test."""

import logging
import sys

import click

from ess_load_test.app_config import default_app_config
from ess_load_test.cli import build_cli

main = build_cli(default_app_config())


def cli_entry() -> None:
    """Console script entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        main()
    except click.ClickException as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli_entry()
