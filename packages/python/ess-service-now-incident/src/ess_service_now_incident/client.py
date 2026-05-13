"""Fetch incident data from a ServiceNow instance via a browser session."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ess_browser import BrowserSession
from ess_browser.auth import LOGIN_TIMEOUT_MS

from .exceptions import (
    APIError,
    AuthenticationError,
    IncidentNotFoundError,
    InputParseError,
)

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_DIR = Path.home() / ".ess-service-now-incident" / "browser-profile"

_API_FIELDS = "description,short_description,number,sys_id"
_NAV_TIMEOUT_MS = 60_000
_SYS_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_INC_PATTERN = re.compile(r"^INC\d+$", re.IGNORECASE)

# JavaScript executed inside the browser to call the ServiceNow Table API.
# Uses the browser's session cookies and the g_ck CSRF token for auth.
_FETCH_JS = """\
async ([url]) => {
    const token = window.g_ck || "";
    const resp = await fetch(url, {
        credentials: "include",
        headers: {
            "Accept": "application/json",
            "X-UserToken": token
        }
    });
    const text = await resp.text();
    return { status: resp.status, ok: resp.ok, body: text };
}
"""


@dataclass(frozen=True)
class IncidentQuery:
    """Parsed incident identifier."""

    query_type: str  # "number" or "sys_id"
    value: str
    instance: str | None = None


def _normalize_url(raw: str) -> str:
    """Prepend ``https://`` if *raw* looks like a schemeless URL."""
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("//"):
        return f"https:{raw}"
    dot = raw.find(".")
    slash = raw.find("/")
    if dot != -1 and (slash == -1 or dot < slash):
        return f"https://{raw}"
    return raw


def _is_servicenow_host(hostname: str) -> bool:
    """Return True if *hostname* is a genuine ``*.service-now.com`` domain."""
    normalized_host = hostname.lower()
    return normalized_host == "service-now.com" or normalized_host.endswith(
        ".service-now.com"
    )


def parse_incident_input(raw: str) -> IncidentQuery:
    """Parse a raw incident identifier into a structured query.

    Args:
        raw: An incident number (``INC0000001``) or a ServiceNow URL.

    Returns:
        An ``IncidentQuery`` describing how to look up the incident.

    Raises:
        InputParseError: If *raw* is neither a recognisable URL nor an
            incident number.
    """
    stripped = raw.strip()

    normalized = _normalize_url(stripped)
    parsed = urlparse(normalized)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme in ("http", "https") and hostname:
        if not _is_servicenow_host(hostname):
            message = (
                f"URL hostname {hostname!r} is not a ServiceNow instance. "
                "Expected service-now.com or a *.service-now.com domain."
            )
            raise InputParseError(message)

        # Check query-string for sys_id (classic UI links).
        query_string_ids = parse_qs(parsed.query).get("sys_id", [])
        if query_string_ids and _SYS_ID_PATTERN.match(query_string_ids[0]):
            return IncidentQuery("sys_id", query_string_ids[0], hostname)

        # Check path segments for a 32-char hex string (workspace URLs).
        for segment in reversed(parsed.path.strip("/").split("/")):
            if _SYS_ID_PATTERN.match(segment):
                return IncidentQuery("sys_id", segment, hostname)

        message = f"Could not extract a sys_id from URL: {stripped}"
        raise InputParseError(message)

    if _INC_PATTERN.match(stripped):
        return IncidentQuery("number", stripped.upper())

    message = (
        f"Unrecognised input: {stripped!r}. "
        "Provide an incident number (INC...) or a ServiceNow URL."
    )
    raise InputParseError(message)


def _build_api_url(instance: str, query: IncidentQuery) -> str:
    """Build the ServiceNow Table API URL for the given query."""
    base = f"https://{instance}/api/now/table/incident"
    if query.query_type == "sys_id":
        return f"{base}/{query.value}?sysparm_fields={_API_FIELDS}"
    return f"{base}?sysparm_query=number={query.value}&sysparm_fields={_API_FIELDS}"


def _resolve_instance(query: IncidentQuery, override: str | None) -> str:
    """Pick the effective ServiceNow instance and validate the hostname."""
    effective = query.instance or override
    if not effective:
        message = (
            "No ServiceNow instance specified. Pass a full ServiceNow URL "
            "as the identifier, or supply instance=<hostname>."
        )
        raise InputParseError(message)
    if not _is_servicenow_host(effective):
        message = (
            f"Instance {effective!r} is not a ServiceNow domain. "
            "Expected service-now.com or a *.service-now.com domain."
        )
        raise InputParseError(message)
    return effective


def _fetch_via_browser(
    *,
    api_url: str,
    target_url: str,
    headed: bool,
    profile_dir: str,
) -> tuple[int, str]:
    """Run the Table API call inside an authenticated browser session.

    Returns ``(status, body)`` for a successful HTTP response. Raises
    :class:`AuthenticationError` if SSO fails or the session is rejected,
    or :class:`APIError` for non-success HTTP statuses.
    """
    with BrowserSession(headed=headed, profile_dir=profile_dir) as session:
        page = session.new_page()

        # Navigate to the instance root to trigger SSO if needed.
        logger.info("Navigating to %s", target_url)
        page.goto(target_url, wait_until="load", timeout=_NAV_TIMEOUT_MS)

        if session.is_auth_redirect(page.url, target_url):
            logger.info("SSO redirect detected -- waiting for login")
            try:
                session.wait_for_login(page, target_url, timeout_ms=LOGIN_TIMEOUT_MS)
            except TimeoutError as exc:
                hint = (
                    " Re-run with --headed to complete login in the browser."
                    if not headed
                    else ""
                )
                message = f"SSO authentication timed out.{hint}"
                raise AuthenticationError(message) from exc

        # Wait for ServiceNow to fully establish the session (sets g_ck).
        logger.info("Waiting for ServiceNow session to initialise")
        page.wait_for_load_state("networkidle", timeout=_NAV_TIMEOUT_MS)
        page.wait_for_function("() => !!window.g_ck", timeout=_NAV_TIMEOUT_MS)

        # Call the Table API from within the authenticated browser context.
        logger.info("Fetching %s", api_url)
        result = page.evaluate(_FETCH_JS, [api_url])

    status = result["status"]
    body = result["body"]

    if status in (401, 403):
        message = (
            f"ServiceNow returned HTTP {status}. "
            "Your session may have expired -- re-run with --headed."
        )
        raise AuthenticationError(message)

    if not result["ok"]:
        raise APIError(status, body[:500])

    return status, body


def _unwrap_result(query: IncidentQuery, status: int, body: str) -> dict[str, Any]:
    """Parse the Table API JSON body and unwrap the ``result`` field."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        snippet = body[:200].strip()
        message = f"Expected JSON but received: {snippet!r}"
        raise APIError(status, message) from exc

    api_result = data.get("result")
    if api_result is None:
        message = f"Unexpected API response shape: {list(data.keys())}"
        raise APIError(status, message)

    if isinstance(api_result, list):
        if not api_result:
            message = f"No incident found for {query.value}"
            raise IncidentNotFoundError(message)
        return api_result[0]

    return api_result


def get_incident(
    raw_input: str,
    *,
    instance: str | None = None,
    headed: bool = False,
    profile_dir: str | None = None,
) -> dict[str, Any]:
    """Fetch an incident record from a ServiceNow instance.

    The instance hostname is resolved in this order:
    1. The host embedded in *raw_input* if it is a URL.
    2. The *instance* keyword argument.

    Args:
        raw_input: An incident number (``INC0000001``) or a ServiceNow URL.
        instance: ServiceNow instance hostname. Required when *raw_input*
            is a bare incident number.
        headed: Show the browser window for first-time SSO login.
        profile_dir: Browser profile directory for session persistence.
            Defaults to ``DEFAULT_PROFILE_DIR`` when omitted.

    Returns:
        A dict with keys ``number``, ``sys_id``, ``short_description``,
        and ``description``.

    Raises:
        InputParseError: If *raw_input* cannot be parsed or no instance
            can be resolved.
        AuthenticationError: If SSO authentication fails.
        IncidentNotFoundError: If the incident does not exist.
        APIError: If the Table API returns a non-success status.
    """
    query = parse_incident_input(raw_input)
    effective_instance = _resolve_instance(query, instance)
    effective_profile = profile_dir or str(DEFAULT_PROFILE_DIR)

    status, body = _fetch_via_browser(
        api_url=_build_api_url(effective_instance, query),
        target_url=f"https://{effective_instance}/",
        headed=headed,
        profile_dir=effective_profile,
    )
    return _unwrap_result(query, status, body)
