"""Locust helpers deployed to EC2 (stdlib only — no locust import).

On EC2 this module is written to ``locust_runtime.py`` beside ``locustfile.py``.
Scenario modules import ``locust_runtime`` there; in the monorepo they import
``ess_load_test.locust.runtime`` via ``try/except ImportError`` shims.
"""

import os
from http import HTTPStatus
from typing import Protocol

_DEFAULT_PATHS = ("/",)
_AUTH_HEADER_FILE = "/tmp/load-test-auth-header.txt"  # nosec B108 — EC2 worker sync path
_REDIRECT_STATUS_CODES = frozenset({301, 302, 307, 308})

VALID_SCENARIOS = frozenset({"default"})
DEFAULT_SCENARIO = "default"
UI_DEFAULT_SCENARIO = "default"

_SCENARIO_DEFAULT_PROFILES: dict[str, str] = {
    "default": "smoke",
    "pages": "pages-run",
    "bff": "bff-run",
    "api": "api-run",
    "mixed": "mixed-run",
}

LOCUST_RUN_PROFILES = (
    "smoke",
    "pages-run",
    "bff-run",
    "api-run",
    "mixed-run",
)


class _ResponseLike(Protocol):
    status_code: int

    def failure(self, message: str) -> None: ...

    def success(self) -> None: ...


class InvalidScenarioError(ValueError):
    """Raised when LOAD_TEST_SCENARIO is not a supported value."""


def normalize_scenario(
    raw_scenario: str | None,
    *,
    valid_scenarios: frozenset[str] | None = None,
) -> str:
    """Return a supported scenario name from env or CLI input."""
    scenarios = valid_scenarios or VALID_SCENARIOS
    if not raw_scenario or not raw_scenario.strip():
        return DEFAULT_SCENARIO
    scenario = raw_scenario.strip().lower()
    if scenario not in scenarios:
        options = ", ".join(sorted(scenarios))
        msg = f"Unsupported LOAD_TEST_SCENARIO {scenario!r}. Expected one of: {options}"
        raise InvalidScenarioError(msg)
    return scenario


def mark_response_failure(
    response: _ResponseLike,
    *,
    strict: bool = False,
    accept_statuses: frozenset[int] | None = None,
) -> None:
    """Mark a Locust response as failed for 5xx, or 4xx when strict.

    Locust treats 4xx as failures on context exit unless ``response.success()``
    was called. Pass ``accept_statuses`` for expected non-2xx outcomes (e.g.
    validation probes) so they are not counted as failures.
    """
    status_code = response.status_code
    if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        response.failure(f"status {status_code}")
        return
    if accept_statuses and status_code in accept_statuses:
        response.success()
        return
    if strict and status_code >= HTTPStatus.BAD_REQUEST:
        response.failure(f"status {status_code}")


def parse_load_test_paths(raw_paths: str | None) -> tuple[str, ...]:
    """Parse comma-separated HTTP paths for load test tasks."""
    if not raw_paths:
        return _DEFAULT_PATHS
    paths = tuple(path.strip() for path in raw_paths.split(",") if path.strip())
    return paths or _DEFAULT_PATHS


def normalize_locust_host(target_url: str) -> str:
    """Strip trailing slashes from the Locust --host base URL.

    Next.js returns 308 when ``--host`` ends with ``/`` and paths start with
    ``/api/...``, which breaks POST requests (auth cookies never reach the route).
    """
    return target_url.strip().rstrip("/")


def default_profile_for_scenario(scenario: str) -> str:
    """Return the suggested Locust UI profile label for a load-test scenario."""
    return _SCENARIO_DEFAULT_PROFILES.get(scenario, "smoke")


def read_load_test_users() -> int | None:
    """Return peak user count from LOAD_TEST_USERS or LOCUST_USERS."""
    for env_name in ("LOAD_TEST_USERS", "LOCUST_USERS"):
        raw_value = os.environ.get(env_name)
        if raw_value is not None and raw_value.strip():
            return int(raw_value.strip())
    return None


def read_load_test_spawn_rate() -> float | None:
    """Return spawn rate from LOAD_TEST_SPAWN_RATE or LOCUST_SPAWN_RATE."""
    for env_name in ("LOAD_TEST_SPAWN_RATE", "LOCUST_SPAWN_RATE"):
        raw_value = os.environ.get(env_name)
        if raw_value is not None and raw_value.strip():
            return float(raw_value.strip())
    return None


def read_load_test_duration() -> str | None:
    """Return run duration string from LOAD_TEST_DURATION or LOCUST_RUN_TIME."""
    for env_name in ("LOAD_TEST_DURATION", "LOCUST_RUN_TIME"):
        raw_value = os.environ.get(env_name)
        if raw_value is not None and raw_value.strip():
            return raw_value.strip()
    return None


def read_auth_header() -> str | None:
    """Return the Locust auth header from a synced file or process env."""
    file_path = os.environ.get("LOAD_TEST_AUTH_HEADER_FILE", _AUTH_HEADER_FILE)
    try:
        with open(file_path, encoding="utf-8") as auth_file:
            from_file = auth_file.read().strip()
    except OSError:
        from_file = ""
    if from_file:
        return from_file
    raw = os.environ.get("LOAD_TEST_AUTH_HEADER")
    if raw and raw.strip():
        return raw.strip()
    return None


def apply_auth_header(headers: dict[str, str], raw_auth_header: str | None) -> None:
    """Apply an optional auth header value to request headers."""
    if not raw_auth_header:
        return
    if ":" in raw_auth_header:
        header_name, header_value = raw_auth_header.split(":", 1)
        headers[header_name.strip()] = header_value.strip()
        return
    headers["Authorization"] = raw_auth_header.strip()


def apply_auth_to_client(client, raw_auth_header: str | None) -> None:
    """Apply browser cookie or bearer auth to a Locust requests session."""
    if not raw_auth_header:
        return
    if ":" in raw_auth_header:
        header_name, header_value = raw_auth_header.split(":", 1)
        name = header_name.strip()
        value = header_value.strip()
        client.headers[name] = value
        if name.lower() == "cookie":
            client.cookies.clear()
            for raw_cookie_pair in value.split(";"):
                cookie_pair = raw_cookie_pair.strip()
                if "=" not in cookie_pair:
                    continue
                cookie_name, cookie_value = cookie_pair.split("=", 1)
                client.cookies.set(cookie_name.strip(), cookie_value.strip())
        return
    client.headers["Authorization"] = raw_auth_header.strip()


def is_auth_redirect(status_code: int) -> bool:
    """Return True when an unauthenticated API call was redirected to sign-in."""
    return status_code in _REDIRECT_STATUS_CODES
