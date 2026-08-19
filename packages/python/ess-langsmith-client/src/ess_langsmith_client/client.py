"""
LangSmith Control Plane API client.

Provides the base client for interacting with the LangSmith Control Plane API.

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

import os
import time
from http import HTTPStatus
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

_REQUEST_TIMEOUT = 30

# Smith app/data API host (tracing sessions, API keys, workspaces).
# Distinct from the control-plane host below (deployments and projects).
_SMITH_API_URL = "https://api.smith.langchain.com"

CONTROL_PLANE_HOSTS = {
    "us": "https://api.host.langchain.com",
    "eu": "https://eu.api.host.langchain.com",
}

# Maximum time to wait for deployment (30 minutes)
MAX_WAIT_TIME = 1800

# Poll interval for deployment status (60 seconds)
POLL_INTERVAL = 60

# Substrings in a deployment/revision status that mark it as unrecoverable.
# A deployment whose status contains any of these is treated as "stuck" and is
# skipped when resolving the live deployment for a canonical name.
_UNHEALTHY_STATUS_MARKERS = ("FAIL", "ERROR", "DELET")


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
            api_key: LangSmith API key (defaults to LANGSMITH_API_KEY env var).
                Required — the key is what authorizes access.
            workspace_id: LangSmith workspace ID (defaults to
                LANGSMITH_WORKSPACE_ID env var). Optional: the key authorizes
                access, and the workspace merely scopes which tenant an
                operation targets. Leave unset here and pass it per operation to
                select the workspace at runtime.
            region: LangSmith region ("us" or "eu")
        """
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        self.workspace_id = workspace_id or os.environ.get("LANGSMITH_WORKSPACE_ID")

        if not self.api_key:
            raise ValueError(
                "LANGSMITH_API_KEY is required. "
                "Set it as an environment variable or pass it to the constructor."
            )

        if region not in CONTROL_PLANE_HOSTS:
            raise ValueError(
                f"Invalid region: {region}. "
                f"Must be one of: {list(CONTROL_PLANE_HOSTS.keys())}"
            )

        self.control_plane_host = CONTROL_PLANE_HOSTS[region]
        self.base_url = f"{self.control_plane_host}/v2"
        # The API key authorizes access; the workspace only scopes which tenant
        # an operation targets. X-Tenant-Id is sent only when a workspace is
        # known (from here or per operation).
        self.headers = self._build_headers(self.workspace_id)

    def _build_headers(self, workspace_id: str | None) -> dict[str, str]:
        """Build request headers, adding tenant scope only when a workspace is set."""
        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }
        if workspace_id:
            headers["X-Tenant-Id"] = workspace_id
        return headers

    def list_listeners(self) -> dict[str, Any]:
        """List all listeners (hybrid deployment agents) for the workspace."""
        response = requests.get(
            f"{self.base_url}/listeners",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTPStatus.OK:
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

        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            raise RuntimeError(
                f"Failed to list deployments: {response.status_code}\n{response.text}"
            )

    @staticmethod
    def is_deployment_healthy(deployment: dict[str, Any]) -> bool:
        """Return True if a deployment is usable as the live target for its name.

        A deployment is considered stuck (not healthy) when its status contains
        a failure/error/deleting marker. A missing status is treated as healthy,
        since freshly created deployments may not report one yet.
        """
        status = str(deployment.get("status") or "").upper()
        return not any(marker in status for marker in _UNHEALTHY_STATUS_MARKERS)

    def find_deployments_by_base(self, base: str) -> list[dict[str, Any]]:
        """Find deployments belonging to a canonical ``<service>-<env>`` base.

        Resolution is by stable logical key, not exact name: a deployment
        matches when its name equals ``base`` or starts with ``base + "-"``
        (so ``hello-agent-dev`` does not match ``hello-agent-prod``). This lets
        a git-SHA rescue sibling (e.g. ``hello-agent-dev-3f9a2c``) be found
        without knowing the suffix.
        """
        result = self.list_deployments(name_contains=base)
        resources = result.get("resources", [])
        prefix = f"{base}-"
        return [
            deployment
            for deployment in resources
            if deployment.get("name") == base
            or str(deployment.get("name", "")).startswith(prefix)
        ]

    def resolve_live_deployment(self, base: str) -> dict[str, Any] | None:
        """Return the single healthy deployment for ``base``, or None.

        When multiple healthy deployments share the base, the most recently
        created one wins (falling back to last-listed when no timestamp is
        available), so deploys converge onto the newest live instance.
        """
        healthy = [
            deployment
            for deployment in self.find_deployments_by_base(base)
            if self.is_deployment_healthy(deployment)
        ]
        if not healthy:
            return None

        # Sort by created_at, breaking ties by list position so that when
        # timestamps are missing/equal the last-listed deployment wins (the
        # most recently created sorts last either way).
        def sort_key(indexed: tuple[int, dict[str, Any]]) -> tuple[str, int]:
            index, deployment = indexed
            return (str(deployment.get("created_at") or ""), index)

        return max(enumerate(healthy), key=sort_key)[1]

    def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Get a specific deployment by ID."""
        response = requests.get(
            f"{self.base_url}/deployments/{deployment_id}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTPStatus.OK:
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

        if response.status_code == HTTPStatus.OK:
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

        if response.status_code == HTTPStatus.OK:
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

        if response.status_code == HTTPStatus.NO_CONTENT:
            return True
        else:
            raise RuntimeError(
                f"Failed to delete deployment: {response.status_code}\n{response.text}"
            )

    def delete_project(
        self,
        project_id: str,
        *,
        workspace_id: str | None = None,
        force: bool = True,
        delete_tracing_project: bool = False,
    ) -> bool:
        """Delete a control-plane project record.

        This targets the control-plane host's ``/v1/projects/{id}`` resource
        (``api.host.langchain.com`` on SaaS), which is distinct from a tracing
        project (session). To delete a tracing project and its traces, use
        ``TracingProjectClient`` instead.

        On SaaS the control plane requires ``X-Tenant-Id`` (a workspace) to
        route the request, so a workspace must be provided here or on the
        client.

        Args:
            project_id: Control-plane project ID.
            workspace_id: Workspace to scope the delete to, selected at runtime.
                Defaults to the client's workspace if one was set. Sent as the
                ``X-Tenant-Id`` header; required by the SaaS control plane.
            force: Force deletion of the control-plane record, clearing stale
                references that would otherwise block it.
            delete_tracing_project: When ``False`` (default), the paired tracing
                project and its traces are preserved; only the control-plane
                record is removed.

        Returns:
            True on success (HTTP 200).

        Raises:
            RuntimeError: If the API returns a non-200 status.
        """
        # The control-plane "projects" resource lives at /v1/projects on the
        # control-plane host (api.host.langchain.com), not under this client's
        # /v2 base_url (which is the deployments API).
        tenant_id = workspace_id or self.workspace_id
        if not tenant_id:
            raise ValueError(
                "A workspace is required to delete a control-plane project "
                "(sent as X-Tenant-Id). Pass workspace_id or set one on the client."
            )

        response = requests.delete(
            f"{self.control_plane_host}/v1/projects/{project_id}",
            headers=self._build_headers(tenant_id),
            params={
                "force": str(force).lower(),
                "delete_tracing_project": str(delete_tracing_project).lower(),
            },
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTPStatus.OK:
            return True
        raise RuntimeError(
            f"Failed to delete project {project_id}: "
            f"{response.status_code}\n{response.text}"
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
