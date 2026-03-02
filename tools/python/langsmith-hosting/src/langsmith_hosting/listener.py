"""LangSmith Listener as a Pulumi dynamic resource.

Creates, adopts, updates, and deletes listeners via the LangSmith Control
Plane API. The listener connects the data plane running on the EKS cluster
to LangSmith's managed control plane.

Lifecycle:
  - create: Adopts an existing listener by compute_id, or creates a new one.
  - read:   Verifies the listener still exists in LangSmith (for refresh).
  - update: PATCHes the listener if namespaces change.
  - delete: Removes the listener from LangSmith on ``pulumi destroy``.

API reference: https://docs.langchain.com/langsmith/api-ref-control-plane
"""

from typing import Any

import pulumi
import requests
from pulumi import dynamic

HTTP_NOT_FOUND = 404
_CONTROL_PLANE_URL = "https://api.host.langchain.com/v2"


class _ListenerProvider(dynamic.ResourceProvider):
    """Manages a LangSmith listener through its full lifecycle."""

    def _headers(self, props: dict[str, Any]) -> dict[str, str]:
        return {
            "X-Api-Key": props["api_key"],
            "X-Tenant-Id": props["workspace_id"],
            "Content-Type": "application/json",
        }

    def _find_by_compute_id(
        self,
        props: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Find an existing listener matching the compute_id."""
        resp = requests.get(
            f"{_CONTROL_PLANE_URL}/listeners",
            headers=self._headers(props),
            params={"limit": 100},
            timeout=30,
        )
        resp.raise_for_status()
        for listener in resp.json().get("resources", []):
            if listener.get("compute_id") == props["compute_id"]:
                return listener
        return None

    def create(self, props: dict[str, Any]) -> dynamic.CreateResult:
        existing = self._find_by_compute_id(props)
        if existing:
            listener_id = existing["id"]
            return dynamic.CreateResult(
                id_=listener_id,
                outs={**props, "listener_id": listener_id},
            )

        response = requests.post(
            f"{_CONTROL_PLANE_URL}/listeners",
            headers=self._headers(props),
            json={
                "compute_type": "k8s",
                "compute_id": props["compute_id"],
                "compute_config": {
                    "k8s_namespaces": props["namespaces"],
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        listener_id = data["id"]
        return dynamic.CreateResult(
            id_=listener_id,
            outs={**props, "listener_id": listener_id},
        )

    def read(
        self,
        id_: str,
        props: dict[str, Any],
    ) -> dynamic.ReadResult:
        response = requests.get(
            f"{_CONTROL_PLANE_URL}/listeners/{id_}",
            headers=self._headers(props),
            timeout=30,
        )
        if response.status_code == HTTP_NOT_FOUND:
            return dynamic.ReadResult("", {})

        response.raise_for_status()
        data = response.json()

        namespaces = data.get("compute_config", {}).get("k8s_namespaces", [])
        return dynamic.ReadResult(
            id_=id_,
            outs={
                **props,
                "compute_id": data.get("compute_id", props.get("compute_id")),
                "namespaces": namespaces,
                "listener_id": id_,
            },
        )

    def diff(
        self,
        id_: str,
        old_outs: dict[str, Any],
        new_inputs: dict[str, Any],
    ) -> dynamic.DiffResult:
        replaces: list[str] = []
        if old_outs.get("compute_id") != new_inputs.get("compute_id"):
            replaces.append("compute_id")

        changes = bool(replaces) or (
            sorted(old_outs.get("namespaces", []))
            != sorted(new_inputs.get("namespaces", []))
        )
        return dynamic.DiffResult(
            changes=changes,
            replaces=replaces,
            delete_before_replace=True,
        )

    def update(
        self,
        id_: str,
        old_outs: dict[str, Any],
        new_inputs: dict[str, Any],
    ) -> dynamic.UpdateResult:
        response = requests.patch(
            f"{_CONTROL_PLANE_URL}/listeners/{id_}",
            headers=self._headers(new_inputs),
            json={
                "compute_config": {
                    "k8s_namespaces": new_inputs["namespaces"],
                },
            },
            timeout=30,
        )
        response.raise_for_status()

        return dynamic.UpdateResult(
            outs={**new_inputs, "listener_id": id_},
        )

    def delete(self, id_: str, props: dict[str, Any]) -> None:
        response = requests.delete(
            f"{_CONTROL_PLANE_URL}/listeners/{id_}",
            headers=self._headers(props),
            timeout=30,
        )
        if response.status_code == HTTP_NOT_FOUND:
            return
        response.raise_for_status()


class LangSmithListener(dynamic.Resource):
    """A LangSmith listener registered with the Control Plane API.

    On first ``pulumi up``, adopts an existing listener matching the
    ``compute_id``, or creates a new one if none exists. On subsequent
    runs, the listener is already in state and only updated if inputs
    change. On ``pulumi destroy``, deletes the listener.

    Attributes:
        listener_id: The system-assigned listener UUID, used as
            ``config.langgraphListenerId`` in the data plane Helm chart.
    """

    listener_id: pulumi.Output[str]

    def __init__(  # noqa: PLR0913
        self,
        name: str,
        *,
        api_key: pulumi.Input[str],
        workspace_id: pulumi.Input[str],
        compute_id: pulumi.Input[str],
        namespaces: pulumi.Input[list[str]],
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__(
            _ListenerProvider(),
            name,
            {
                "api_key": api_key,
                "workspace_id": workspace_id,
                "compute_id": compute_id,
                "namespaces": namespaces,
                "listener_id": None,
            },
            opts,
        )
