"""
LangSmith Control Plane API client.

Provides the base client for interacting with the LangSmith Control Plane API.

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

HTTP_OK = 200
HTTP_NO_CONTENT = 204

_REQUEST_TIMEOUT = 30

# Control Plane API hosts by region
CONTROL_PLANE_HOSTS = {
    "us": "https://api.host.langchain.com",
    "eu": "https://eu.api.host.langchain.com",
}

# Maximum time to wait for deployment (30 minutes)
MAX_WAIT_TIME = 1800

# Poll interval for deployment status (60 seconds)
POLL_INTERVAL = 60


class ControlPlaneClient:
    """Client for the LangSmith Control Plane API."""

    def __init__(
        self,
        api_key: str | None = None,
        workspace_id: str | None = None,
        region: str = "us",
    ):
        """
        Initialize the Control Plane client.

        Args:
            api_key: LangSmith API key (defaults to LANGSMITH_API_KEY env var)
            workspace_id: LangSmith workspace ID (defaults to LANGSMITH_WORKSPACE_ID
                env var)
            region: LangSmith region ("us" or "eu")
        """
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        self.workspace_id = workspace_id or os.environ.get("LANGSMITH_WORKSPACE_ID")

        if not self.api_key:
            raise ValueError(
                "LANGSMITH_API_KEY is required. "
                "Set it as an environment variable or pass it to the constructor."
            )

        if not self.workspace_id:
            raise ValueError(
                "LANGSMITH_WORKSPACE_ID is required. "
                "Find it in your LangSmith workspace settings."
            )

        if region not in CONTROL_PLANE_HOSTS:
            raise ValueError(
                f"Invalid region: {region}. "
                f"Must be one of: {list(CONTROL_PLANE_HOSTS.keys())}"
            )

        self.base_url = f"{CONTROL_PLANE_HOSTS[region]}/v2"
        self.headers = {
            "X-Api-Key": self.api_key,
            "X-Tenant-Id": self.workspace_id,
            "Content-Type": "application/json",
        }

    def list_listeners(self) -> dict[str, Any]:
        """List all listeners (hybrid deployment agents) for the workspace."""
        response = requests.get(
            f"{self.base_url}/listeners",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTP_OK:
            return response.json()
        else:
            raise RuntimeError(
                f"Failed to list listeners: {response.status_code}\n{response.text}"
            )

    def list_deployments(self, name_contains: str | None = None) -> dict[str, Any]:
        """List all deployments, optionally filtered by name."""
        params = {}
        if name_contains:
            params["name_contains"] = name_contains

        response = requests.get(
            f"{self.base_url}/deployments",
            headers=self.headers,
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTP_OK:
            return response.json()
        else:
            raise RuntimeError(
                f"Failed to list deployments: {response.status_code}\n{response.text}"
            )

    def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Get a specific deployment by ID."""
        response = requests.get(
            f"{self.base_url}/deployments/{deployment_id}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTP_OK:
            return response.json()
        else:
            raise RuntimeError(
                f"Failed to get deployment {deployment_id}: "
                f"{response.status_code}\n{response.text}"
            )

    def get_revision(self, deployment_id: str, revision_id: str) -> dict[str, Any]:
        """Get a specific revision of a deployment."""
        response = requests.get(
            f"{self.base_url}/deployments/{deployment_id}/revisions/{revision_id}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTP_OK:
            return response.json()
        else:
            raise RuntimeError(
                f"Failed to get revision {revision_id}: "
                f"{response.status_code}\n{response.text}"
            )

    def list_revisions(self, deployment_id: str) -> dict[str, Any]:
        """List all revisions for a deployment."""
        response = requests.get(
            f"{self.base_url}/deployments/{deployment_id}/revisions",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTP_OK:
            return response.json()
        else:
            raise RuntimeError(
                f"Failed to list revisions: {response.status_code}\n{response.text}"
            )

    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment."""
        response = requests.delete(
            f"{self.base_url}/deployments/{deployment_id}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTP_NO_CONTENT:
            return True
        else:
            raise RuntimeError(
                f"Failed to delete deployment: {response.status_code}\n{response.text}"
            )

    def wait_for_deployment(
        self,
        deployment_id: str,
        revision_id: str,
        max_wait: int = MAX_WAIT_TIME,
        poll_interval: int = POLL_INTERVAL,
    ) -> dict[str, Any]:
        """
        Wait for a deployment revision to reach DEPLOYED status.

        Args:
            deployment_id: ID of the deployment
            revision_id: ID of the revision to wait for
            max_wait: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds

        Returns:
            Final revision status

        Raises:
            RuntimeError: If deployment fails or times out
        """
        start_time = time.time()
        revision = None
        status = None

        while time.time() - start_time < max_wait:
            revision = self.get_revision(deployment_id, revision_id)
            status = revision.get("status")

            if status == "DEPLOYED":
                return revision
            elif "FAILED" in str(status):
                raise RuntimeError(f"Deployment failed: {revision}")

            print(f"  Status: {status}... waiting {poll_interval}s")
            time.sleep(poll_interval)

        raise RuntimeError(
            f"Timeout waiting for deployment. Last status: {status}\n{revision}"
        )
