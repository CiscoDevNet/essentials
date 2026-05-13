"""Fetch ServiceNow incident records via an authenticated browser session."""

from .cli import INSTANCE_ENV_VAR, build_cli
from .client import (
    DEFAULT_PROFILE_DIR,
    IncidentQuery,
    get_incident,
    parse_incident_input,
)
from .exceptions import (
    APIError,
    AuthenticationError,
    IncidentNotFoundError,
    InputParseError,
    ServiceNowIncidentError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "DEFAULT_PROFILE_DIR",
    "INSTANCE_ENV_VAR",
    "IncidentNotFoundError",
    "IncidentQuery",
    "InputParseError",
    "ServiceNowIncidentError",
    "build_cli",
    "get_incident",
    "parse_incident_input",
]
