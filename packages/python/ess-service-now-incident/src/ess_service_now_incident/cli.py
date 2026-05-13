"""Click-based CLI factory for ess-service-now-incident.

Wrappers can call :func:`build_cli` with a ``default_instance`` to bake
in an organization-specific hostname while keeping the same command
shape as the standalone CLI.
"""

from __future__ import annotations

import json
import logging
import sys

import click

from .client import DEFAULT_PROFILE_DIR, get_incident
from .exceptions import ServiceNowIncidentError

INSTANCE_ENV_VAR = "SERVICENOW_INSTANCE"


def build_cli(*, default_instance: str | None = None) -> click.Command:
    """Build a Click command for fetching ServiceNow incidents.

    Args:
        default_instance: Hostname baked in as the ``--instance``
            default.  At invocation time the ``SERVICENOW_INSTANCE``
            environment variable still takes precedence, and an
            explicit ``--instance`` flag wins over both.  Pass ``None``
            to require the user to supply an instance (either via the
            flag, the environment variable, or a full URL identifier).

    Returns:
        A :class:`click.Command` ready to be exposed as a console
        script.  The command exits with a non-zero status on errors.
    """
    show_default = bool(default_instance)

    @click.command()
    @click.argument("identifier")
    @click.option(
        "--headed",
        is_flag=True,
        default=False,
        help="Show the browser window. Use for first-time SSO login.",
    )
    @click.option(
        "--profile-dir",
        default=None,
        help=(
            f"Browser profile directory for session persistence. "
            f"[default: {DEFAULT_PROFILE_DIR}]"
        ),
    )
    @click.option(
        "--instance",
        default=default_instance,
        envvar=INSTANCE_ENV_VAR,
        show_default=show_default,
        help=(
            "ServiceNow instance hostname (e.g. example.service-now.com). "
            f"Falls back to the {INSTANCE_ENV_VAR} environment variable."
        ),
    )
    @click.option(
        "--json",
        "output_json",
        is_flag=True,
        default=False,
        help="Output full incident data as JSON.",
    )
    @click.option(
        "-v",
        "--verbose",
        is_flag=True,
        default=False,
        help="Enable verbose logging.",
    )
    def main(  # noqa: PLR0913
        identifier: str,
        headed: bool,
        profile_dir: str | None,
        instance: str | None,
        output_json: bool,
        verbose: bool,
    ) -> None:
        """Fetch the description of a ServiceNow incident.

        IDENTIFIER is an incident number (e.g. INC0000001) or a full
        ServiceNow URL.
        """
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.WARNING,
            format="%(levelname)s: %(message)s",
            stream=sys.stderr,
        )

        try:
            result = get_incident(
                identifier,
                instance=instance,
                headed=headed,
                profile_dir=profile_dir,
            )
        except ServiceNowIncidentError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001  -- last-resort CLI guard
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

        if output_json:
            click.echo(json.dumps(result, indent=2))
            return

        description = result.get("description", "").strip()
        if description:
            click.echo(description)
            return

        short_description = result.get("short_description", "").strip()
        if short_description:
            click.echo(
                "Note: description is empty, showing short_description instead.",
                err=True,
            )
            click.echo(short_description)
            return

        click.echo("No description or short_description found.", err=True)
        sys.exit(1)

    return main
