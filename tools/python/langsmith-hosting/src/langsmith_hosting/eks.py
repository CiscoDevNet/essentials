"""EKS resources for LangSmith Hosting infrastructure.

Creates an EKS cluster with a managed node group, EBS CSI driver addon,
GP3 default storage class, and Helm-based addons (AWS Load Balancer Controller,
metrics-server, cluster-autoscaler).

Dependency chain::

    VPC
    ├── EKS cluster → node group → pod_identity_addon
    │                              ├── ebs_csi_pod_identity → ebs_csi_addon
    │                              ├── lbc_pod_identity ──────┐
    │                              └── autoscaler_pod_identity┤
    │   ebs_csi_addon ─────────────────────────────────────── ├── ALB controller
    │                  ├── GP3 StorageClass                   ├── metrics-server
    │                  └── cluster-autoscaler ────────────────┘
    │   ALB controller → KEDA → dataplane  (wired in dataplane.py)
    ├── Postgres (parallel)
    ├── Redis (parallel)
    └── S3 (parallel)
"""

import importlib.resources
import json
from dataclasses import dataclass

import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s

from langsmith_hosting.config import LangSmithConfig
from langsmith_hosting.constants import get_tags

# IAM policy for AWS Load Balancer Controller (v2.7.x).
# Source: https://github.com/kubernetes-sigs/aws-load-balancer-controller/blob/v2.7.2/docs/install/iam_policy.json
with (
    importlib.resources.files("langsmith_hosting")
    .joinpath("lbc_policy.json")
    .open() as _file
):
    _LBC_IAM_POLICY: dict = json.load(_file)

# IAM policy for cluster autoscaler.
# Source: https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md
with (
    importlib.resources.files("langsmith_hosting")
    .joinpath("autoscaler_policy.json")
    .open() as _file
):
    _AUTOSCALER_POLICY: dict = json.load(_file)


@dataclass
class EksOutputs:
    """Outputs from the EKS module."""

    cluster_name: pulumi.Output[str]
    kubeconfig: pulumi.Output[str]
    oidc_provider_arn: pulumi.Output[str]
    oidc_provider_url: pulumi.Output[str]
    k8s_provider: k8s.Provider
    alb_controller: k8s.helm.v3.Release


def create_eks_cluster(
    cfg: LangSmithConfig,
    vpc_id: pulumi.Output[str],
    private_subnet_ids: pulumi.Output[list[str]],
    public_subnet_ids: pulumi.Output[list[str]],
    public_access_cidrs: list[str] | None = None,
) -> EksOutputs:
    """Create an EKS cluster with managed node group and addons.

    Args:
        cfg: Typed stack configuration (cluster name, version, node sizing).
        vpc_id: VPC ID to deploy into.
        private_subnet_ids: Private subnet IDs for worker nodes.
        public_subnet_ids: Public subnet IDs for load balancers.
        public_access_cidrs: CIDR blocks allowed to reach the public API
            endpoint. When provided, the private endpoint is also enabled
            so in-VPC traffic stays internal.

    Returns:
        EksOutputs with cluster details and Kubernetes provider.
    """
    tags = get_tags("eks")
    cluster_name = cfg.eks_cluster_name
    cluster_version = cfg.eks_cluster_version
    node_instance_type = cfg.eks_node_instance_type
    node_min_size = cfg.eks_node_min_size
    node_max_size = cfg.eks_node_max_size
    node_desired_size = cfg.eks_node_desired_size
    # =========================================================================
    # IAM role for worker nodes
    # =========================================================================
    node_role = aws.iam.Role(
        f"{cluster_name}-node-role",
        assume_role_policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "sts:AssumeRole",
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                    }
                ],
            }
        ),
        tags=tags,
    )

    for policy_name, policy_arn in [
        ("worker-node", "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"),
        ("cni", "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"),
        ("ecr-readonly", "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"),
        ("ebs-csi", "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"),
    ]:
        aws.iam.RolePolicyAttachment(
            f"{cluster_name}-{policy_name}-policy",
            role=node_role.name,
            policy_arn=policy_arn,
        )

    # =========================================================================
    # EKS cluster
    # =========================================================================
    cluster = eks.Cluster(
        cluster_name,
        name=cluster_name,
        version=cluster_version,
        vpc_id=vpc_id,
        public_subnet_ids=public_subnet_ids,
        private_subnet_ids=private_subnet_ids,
        authentication_mode=eks.AuthenticationMode.API,
        endpoint_private_access=bool(public_access_cidrs),
        endpoint_public_access=True,
        public_access_cidrs=public_access_cidrs,
        skip_default_node_group=True,
        create_oidc_provider=True,
        tags=tags,
    )

    # =========================================================================
    # Launch template (IMDS hop limit = 2 for DinD sidecar)
    # =========================================================================
    # The DinD sidecar runs a privileged container inside the pod to provide
    # Docker-in-Docker for code execution sandboxes. It needs IMDS access to
    # fetch ECR credentials via `aws ecr get-login-password`. With the default
    # hop limit of 1, requests from the nested Docker daemon cannot reach IMDS
    # (pod→node = hop 1, DinD→pod = hop 2). Setting the limit to 2 allows the
    # second hop to succeed.
    launch_template = aws.ec2.LaunchTemplate(
        f"{cluster_name}-node-launch-template",
        metadata_options=aws.ec2.LaunchTemplateMetadataOptionsArgs(
            http_endpoint="enabled",
            http_tokens="required",
            http_put_response_hop_limit=2,
        ),
        tags=tags,
    )

    # =========================================================================
    # Managed node group
    # =========================================================================
    node_group = eks.ManagedNodeGroup(
        f"{cluster_name}-default",
        cluster=cluster,
        node_role=node_role,
        instance_types=[node_instance_type],
        scaling_config={
            "min_size": node_min_size,
            "max_size": node_max_size,
            "desired_size": node_desired_size,
        },
        launch_template={
            "id": launch_template.id,
            "version": launch_template.latest_version.apply(str),
        },
    )

    # =========================================================================
    # Kubernetes provider from cluster kubeconfig
    # =========================================================================
    k8s_provider = k8s.Provider(
        f"{cluster_name}-k8s",
        kubeconfig=cluster.kubeconfig_json,
    )

    # =========================================================================
    # EKS Pod Identity agent addon
    # =========================================================================
    # Required for Pod Identity credential injection into pods. Must be
    # present on nodes before any PodIdentityAssociation can take effect.
    pod_identity_addon = aws.eks.Addon(
        f"{cluster_name}-pod-identity-agent",
        cluster_name=cluster.eks_cluster.name,
        addon_name="eks-pod-identity-agent",
        resolve_conflicts_on_create="OVERWRITE",
        resolve_conflicts_on_update="OVERWRITE",
        opts=pulumi.ResourceOptions(
            depends_on=[node_group],
            custom_timeouts=pulumi.CustomTimeouts(create="10m", update="10m"),
        ),
    )

    # =========================================================================
    # IAM role for EBS CSI controller (Pod Identity)
    # =========================================================================
    # The EBS CSI controller runs in a Deployment (not a DaemonSet). While
    # the launch template now sets hop limit = 2 (for DinD IMDS access),
    # Pod Identity is still preferred here — it injects credentials directly
    # without IMDS, avoiding any timing/propagation issues.
    # Registered BEFORE the addon so credentials are available on first boot.
    ebs_csi_role = aws.iam.Role(
        f"{cluster_name}-ebs-csi-role",
        assume_role_policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "pods.eks.amazonaws.com"},
                        "Action": ["sts:AssumeRole", "sts:TagSession"],
                    }
                ],
            }
        ),
        tags=tags,
    )

    ebs_csi_role_policy = aws.iam.RolePolicyAttachment(
        f"{cluster_name}-ebs-csi-role-policy",
        role=ebs_csi_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy",
    )

    # Policy must be attached before the association so the role has
    # permissions when pods first assume it. IAM propagation may still
    # lag briefly; pods should tolerate transient AccessDenied on startup.
    ebs_csi_pod_identity = aws.eks.PodIdentityAssociation(
        f"{cluster_name}-ebs-csi-pod-identity",
        cluster_name=cluster.eks_cluster.name,
        namespace="kube-system",
        service_account="ebs-csi-controller-sa",
        role_arn=ebs_csi_role.arn,
        opts=pulumi.ResourceOptions(
            depends_on=[pod_identity_addon, ebs_csi_role_policy],
        ),
    )

    # =========================================================================
    # EBS CSI driver addon
    # =========================================================================
    # Depends on node_group and ebs_csi_pod_identity so credentials are
    # registered before the controller pods start.
    ebs_csi_addon = aws.eks.Addon(
        f"{cluster_name}-ebs-csi",
        cluster_name=cluster.eks_cluster.name,
        addon_name="aws-ebs-csi-driver",
        resolve_conflicts_on_create="OVERWRITE",
        resolve_conflicts_on_update="OVERWRITE",
        opts=pulumi.ResourceOptions(
            depends_on=[node_group, ebs_csi_pod_identity],
            custom_timeouts=pulumi.CustomTimeouts(create="10m", update="10m"),
        ),
    )

    # =========================================================================
    # GP3 default storage class
    # =========================================================================
    k8s.storage.v1.StorageClass(
        f"{cluster_name}-gp3",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="gp3",
            annotations={
                "storageclass.kubernetes.io/is-default-class": "true",
            },
        ),
        provisioner="ebs.csi.aws.com",
        volume_binding_mode="WaitForFirstConsumer",
        parameters={
            "type": "gp3",
            "fsType": "ext4",
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[ebs_csi_addon],
        ),
    )

    # =========================================================================
    # IAM role for AWS Load Balancer Controller (Pod Identity)
    # =========================================================================
    # Trust policy is static — no OIDC URL manipulation required.
    lbc_role = aws.iam.Role(
        f"{cluster_name}-lbc-role",
        assume_role_policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "pods.eks.amazonaws.com"},
                        "Action": ["sts:AssumeRole", "sts:TagSession"],
                    }
                ],
            }
        ),
        tags=tags,
    )

    lbc_policy = aws.iam.RolePolicy(
        f"{cluster_name}-lbc-policy",
        role=lbc_role.id,
        policy=json.dumps(_LBC_IAM_POLICY),
    )

    # Policy must be attached before the association so the role has
    # permissions when pods first assume it. Captured so the Helm release
    # can depend on it — pods must not start until the association is
    # registered with the EKS control plane.
    lbc_pod_identity = aws.eks.PodIdentityAssociation(
        f"{cluster_name}-lbc-pod-identity",
        cluster_name=cluster.eks_cluster.name,
        namespace="kube-system",
        service_account="aws-load-balancer-controller",
        role_arn=lbc_role.arn,
        opts=pulumi.ResourceOptions(
            depends_on=[pod_identity_addon, lbc_policy],
        ),
    )

    # =========================================================================
    # IAM role for cluster autoscaler (Pod Identity)
    # =========================================================================
    autoscaler_role = aws.iam.Role(
        f"{cluster_name}-autoscaler-role",
        assume_role_policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "pods.eks.amazonaws.com"},
                        "Action": ["sts:AssumeRole", "sts:TagSession"],
                    }
                ],
            }
        ),
        tags=tags,
    )

    autoscaler_policy = aws.iam.RolePolicy(
        f"{cluster_name}-autoscaler-policy",
        role=autoscaler_role.id,
        policy=json.dumps(_AUTOSCALER_POLICY),
    )

    # Policy must be attached before the association so the role has
    # permissions when pods first assume it.
    autoscaler_pod_identity = aws.eks.PodIdentityAssociation(
        f"{cluster_name}-autoscaler-pod-identity",
        cluster_name=cluster.eks_cluster.name,
        namespace="kube-system",
        service_account="cluster-autoscaler",
        role_arn=autoscaler_role.arn,
        opts=pulumi.ResourceOptions(
            depends_on=[pod_identity_addon, autoscaler_policy],
        ),
    )

    # =========================================================================
    # Helm addons: ALB Controller, metrics-server, cluster-autoscaler
    # =========================================================================
    alb_controller = k8s.helm.v3.Release(
        f"{cluster_name}-aws-lb-controller",
        name="aws-load-balancer-controller",
        chart="aws-load-balancer-controller",
        version="1.7.2",
        namespace="kube-system",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://aws.github.io/eks-charts",
        ),
        values={
            "clusterName": cluster_name,
            "region": aws.get_region().region,
            "vpcId": vpc_id,
            "serviceAccount": {
                "create": True,
                "name": "aws-load-balancer-controller",
            },
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[ebs_csi_addon, lbc_pod_identity],
            custom_timeouts=pulumi.CustomTimeouts(create="10m", update="10m"),
        ),
    )

    k8s.helm.v3.Release(
        f"{cluster_name}-metrics-server",
        name="metrics-server",
        chart="metrics-server",
        version="3.12.0",
        namespace="kube-system",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://kubernetes-sigs.github.io/metrics-server/",
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[ebs_csi_addon],
        ),
    )

    k8s.helm.v3.Release(
        f"{cluster_name}-cluster-autoscaler",
        name="cluster-autoscaler",
        chart="cluster-autoscaler",
        version="9.36.0",
        namespace="kube-system",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://kubernetes.github.io/autoscaler",
        ),
        values={
            "autoDiscovery": {
                "clusterName": cluster_name,
            },
            "awsRegion": aws.get_region().region,
            "rbac": {
                "serviceAccount": {
                    "create": True,
                    "name": "cluster-autoscaler",
                },
            },
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[ebs_csi_addon, autoscaler_pod_identity],
        ),
    )

    # =========================================================================
    # Outputs
    # =========================================================================
    return EksOutputs(
        cluster_name=cluster.eks_cluster.name,
        kubeconfig=cluster.kubeconfig_json,
        oidc_provider_arn=cluster.oidc_provider_arn,
        oidc_provider_url=cluster.oidc_provider_url,
        k8s_provider=k8s_provider,
        alb_controller=alb_controller,
    )
