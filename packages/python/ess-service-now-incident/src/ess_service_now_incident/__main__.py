"""CLI entry point for ess-service-now-incident.

The standalone CLI has no built-in default instance; users must either
pass ``--instance``, set the ``SERVICENOW_INSTANCE`` environment
variable, or supply a full ServiceNow URL as the identifier argument.
Build a customized CLI with :func:`ess_service_now_incident.build_cli`
to bake in an organization-specific default.
"""

from __future__ import annotations

from .cli import build_cli

main = build_cli()


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter  # Click supplies args at runtime
