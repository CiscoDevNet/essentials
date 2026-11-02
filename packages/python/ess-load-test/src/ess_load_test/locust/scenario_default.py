"""Default Locust user that hits configurable HTTP paths."""

import os
from http import HTTPStatus

from locust import HttpUser, between, task

try:
    from locust_runtime import apply_auth_header, parse_load_test_paths
except ImportError:
    from ess_load_test.locust.runtime import apply_auth_header, parse_load_test_paths


class LoadTestUser(HttpUser):
    """Simulate users hitting one or more HTTP paths on the target host."""

    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        apply_auth_header(
            self.client.headers,
            os.environ.get("LOAD_TEST_AUTH_HEADER"),
        )

    @task
    def request_paths(self) -> None:
        paths = parse_load_test_paths(os.environ.get("LOAD_TEST_PATHS"))
        for path in paths:
            with self.client.get(path, catch_response=True, name=path) as response:
                if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
                    response.failure(f"status {response.status_code}")
