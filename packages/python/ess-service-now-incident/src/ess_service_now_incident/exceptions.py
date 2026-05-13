"""Domain exceptions for the ess-service-now-incident library."""

from __future__ import annotations


class ServiceNowIncidentError(Exception):
    """Base exception for all ess-service-now-incident errors."""


class IncidentNotFoundError(ServiceNowIncidentError):
    """The requested incident does not exist."""


class AuthenticationError(ServiceNowIncidentError):
    """SSO authentication failed or the session is expired."""


class APIError(ServiceNowIncidentError):
    """The ServiceNow Table API returned an error."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"ServiceNow API error (HTTP {status}): {message}")


class InputParseError(ServiceNowIncidentError):
    """The input cannot be parsed as an incident number or URL."""
