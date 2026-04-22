"""LangSmith data plane resources.

Installs the full data plane stack on the EKS cluster:
  1. Listener — registered with the LangSmith Control Plane API
  2. KEDA — Kubernetes event-driven autoscaling (prerequisite)
  3. langgraph-dataplane Helm chart — connects the cluster to LangSmith

Dependency chain:
    EKS node group ready (via ebs_csi_addon)
        ├── Listener (API call, outputs listener_id)
        └── KEDA (Helm, depends on nodes being schedulable)
                └── dataplane (Helm, depends on Listener + KEDA)
"""

from dataclasses import dataclass

import pulumi
import pulumi_kubernetes as k8s

from langsmith_hosting.config import LangSmithConfig
from langsmith_hosting.listener import LangSmithListener

_HOST_BACKEND_URL = "https://api.host.langchain.com"
_SMITH_BACKEND_URL = "https://api.smith.langchain.com"

_KEDA_CHART_VERSION = "2.16.0"
_DATAPLANE_CHART_VERSION = "0.2.17"

_WATCH_NAMESPACES = "default"

_REDIS_CPU_REQUEST = "1000m"
_REDIS_MEMORY_REQUEST = "2Gi"
_REDIS_CPU_LIMIT = "2000m"
_REDIS_MEMORY_LIMIT = "4Gi"


@dataclass
class DataplaneOutputs:
    """Outputs from the data plane module."""

    listener_id: pulumi.Output[str]


def create_dataplane(
    cfg: LangSmithConfig,
    k8s_provider: k8s.Provider,
    depends_on: list[pulumi.Resource] | None = None,
) -> DataplaneOutputs:
    """Install the LangSmith data plane on an EKS cluster.

    Args:
        cfg: Typed stack configuration (cluster name, API key, workspace ID).
        k8s_provider: Kubernetes provider for Helm releases.
        depends_on: Resources that must be ready before Helm charts are
            installed (e.g. EBS CSI addon, which implies the node group).

    Returns:
        DataplaneOutputs with the listener ID.
    """
    cluster_name = cfg.eks_cluster_name
    langsmith_api_key = cfg.langsmith_api_key
    langsmith_workspace_id = cfg.langsmith_workspace_id

    namespaces = [ns.strip() for ns in _WATCH_NAMESPACES.split(",")]

    # =========================================================================
    # 1. Register a listener with the LangSmith Control Plane API
    # =========================================================================
    listener = LangSmithListener(
        f"{cluster_name}-listener",
        api_key=langsmith_api_key,
        workspace_id=langsmith_workspace_id,
        compute_id=cluster_name,
        namespaces=namespaces,
    )

    # =========================================================================
    # 2. Install KEDA (prerequisite for the data plane operator)
    # =========================================================================
    keda = k8s.helm.v3.Release(
        f"{cluster_name}-keda",
        name="keda",
        chart="keda",
        version=_KEDA_CHART_VERSION,
        namespace="keda",
        create_namespace=True,
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://kedacore.github.io/charts",
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=depends_on or [],
            custom_timeouts=pulumi.CustomTimeouts(create="10m", update="10m"),
        ),
    )

    # =========================================================================
    # 3. Install LangSmith dataplane (depends on both KEDA and Listener)
    # =========================================================================

    # Build ingress values with ALB annotations so the AWS Load Balancer
    # Controller provisions an ALB for the shared dataplane ingress.
    ingress_annotations: dict[str, str] = {
        "alb.ingress.kubernetes.io/scheme": "internet-facing",
        "alb.ingress.kubernetes.io/target-type": "ip",
        "alb.ingress.kubernetes.io/listen-ports": '[{"HTTP": 80}]',
        "alb.ingress.kubernetes.io/healthcheck-path": "/ok",
        "alb.ingress.kubernetes.io/healthcheck-protocol": "HTTP",
        "alb.ingress.kubernetes.io/backend-protocol": "HTTP",
    }
    if cfg.ingress_certificate_arn:
        cert_arn = cfg.ingress_certificate_arn
        ingress_annotations.update(
            {
                "alb.ingress.kubernetes.io/certificate-arn": cert_arn,
                "alb.ingress.kubernetes.io/listen-ports": (
                    '[{"HTTP": 80}, {"HTTPS": 443}]'
                ),
                "alb.ingress.kubernetes.io/ssl-redirect": "443",
            }
        )

    ingress_values: dict = {
        "ingressClassName": "alb",
        "annotations": ingress_annotations,
    }
    ingress_hostname = (cfg.ingress_hostname or "").strip() or None
    if ingress_hostname and not cfg.ingress_certificate_arn:
        raise pulumi.RunError(
            "ingressCertificateArn is required when ingressHostname is set — "
            "the operator constructs https:// health-check URLs from the hostname."
        )
    if ingress_hostname:
        ingress_values["hostname"] = ingress_hostname

    # Enable health checks only when a hostname is configured, because the
    # listener constructs the check URL from the hostname. Without one, the
    # URL is malformed and deployments fail with UnsupportedProtocol.
    # Note: the operator always constructs https:// health check URLs when
    # a hostname is set, so TLS (via ingressCertificateArn) is required
    # before setting ingressHostname.
    enable_health_check = ingress_hostname is not None

    k8s.helm.v3.Release(
        f"{cluster_name}-dataplane",
        name="dataplane",
        chart="langgraph-dataplane",
        version=_DATAPLANE_CHART_VERSION,
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://langchain-ai.github.io/helm/",
        ),
        timeout=600,
        values={
            "config": {
                "langsmithApiKey": langsmith_api_key,
                "langsmithWorkspaceId": langsmith_workspace_id,
                "hostBackendUrl": _HOST_BACKEND_URL,
                "smithBackendUrl": _SMITH_BACKEND_URL,
                "langgraphListenerId": listener.listener_id,
                "watchNamespaces": ",".join(namespaces),
                "enableLGPDeploymentHealthCheck": enable_health_check,
            },
            "ingress": ingress_values,
            "redis": {
                "statefulSet": {
                    "resources": {
                        "requests": {
                            "cpu": _REDIS_CPU_REQUEST,
                            "memory": _REDIS_MEMORY_REQUEST,
                        },
                        "limits": {
                            "cpu": _REDIS_CPU_LIMIT,
                            "memory": _REDIS_MEMORY_LIMIT,
                        },
                    },
                },
            },
            "operator": {
                "enabled": True,
                "createCRDs": True,
            },
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[keda, listener],
            custom_timeouts=pulumi.CustomTimeouts(create="15m", update="15m"),
        ),
    )

    return DataplaneOutputs(listener_id=listener.listener_id)
