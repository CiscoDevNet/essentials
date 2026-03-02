"""EKS resources for LangSmith Hosting infrastructure.

Creates an EKS cluster with a managed node group, EBS CSI driver addon,
GP3 default storage class, and Helm-based addons (AWS Load Balancer Controller,
metrics-server, cluster-autoscaler).

Dependency chain (from apply-targeted.sh):
    VPC -> EKS cluster -> EBS CSI addon -> Helm addons -> GP3 storage class
"""

import importlib.resources
import json
from dataclasses import dataclass

import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s

from langsmith_hosting.constants import TAGS

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


def create_eks_cluster(  # noqa: PLR0913
    cluster_name: str,
    cluster_version: str,
    vpc_id: pulumi.Output[str],
    private_subnet_ids: pulumi.Output[list[str]],
    public_subnet_ids: pulumi.Output[list[str]],
    node_instance_type: str,
    node_min_size: int,
    node_max_size: int,
    node_desired_size: int,
) -> EksOutputs:
    """Create an EKS cluster with managed node group and addons.

    Args:
        cluster_name: Name of the EKS cluster.
        cluster_version: Kubernetes version (e.g. "1.31").
        vpc_id: VPC ID to deploy into.
        private_subnet_ids: Private subnet IDs for worker nodes.
        public_subnet_ids: Public subnet IDs for load balancers.
        node_instance_type: EC2 instance type for nodes (e.g. "m5.xlarge").
        node_min_size: Minimum number of nodes.
        node_max_size: Maximum number of nodes.
        node_desired_size: Desired number of nodes.

    Returns:
        EksOutputs with cluster details and Kubernetes provider.
    """
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
        tags=TAGS,
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
        skip_default_node_group=True,
        create_oidc_provider=True,
        tags=TAGS,
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
    )

    # =========================================================================
    # Kubernetes provider from cluster kubeconfig
    # =========================================================================
    k8s_provider = k8s.Provider(
        f"{cluster_name}-k8s",
        kubeconfig=cluster.kubeconfig_json,
    )

    # =========================================================================
    # EBS CSI driver addon
    # =========================================================================
    # Depends on node_group (not just cluster) so nodes are ready to schedule
    # the addon's DaemonSet pods before we wait for ACTIVE state.
    ebs_csi_addon = aws.eks.Addon(
        f"{cluster_name}-ebs-csi",
        cluster_name=cluster.eks_cluster.name,
        addon_name="aws-ebs-csi-driver",
        resolve_conflicts_on_create="OVERWRITE",
        resolve_conflicts_on_update="OVERWRITE",
        opts=pulumi.ResourceOptions(depends_on=[node_group]),
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
        opts=pulumi.ResourceOptions(depends_on=[node_group]),
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
        tags=TAGS,
    )

    aws.iam.RolePolicy(
        f"{cluster_name}-lbc-policy",
        role=lbc_role.id,
        policy=json.dumps(_LBC_IAM_POLICY),
    )

    # Bind the role to the LBC service account via Pod Identity (no SA annotation).
    # Captured so the Helm release can depend on it — pods must not start until the
    # association is registered with the EKS control plane.
    lbc_pod_identity = aws.eks.PodIdentityAssociation(
        f"{cluster_name}-lbc-pod-identity",
        cluster_name=cluster.eks_cluster.name,
        namespace="kube-system",
        service_account="aws-load-balancer-controller",
        role_arn=lbc_role.arn,
        opts=pulumi.ResourceOptions(depends_on=[pod_identity_addon]),
    )

    # =========================================================================
    # IAM role for EBS CSI controller (Pod Identity)
    # =========================================================================
    # The EBS CSI controller runs in a Deployment (not a DaemonSet), so it
    # cannot rely on the node role via IMDS (hop limit = 1 blocks pod access).
    # Pod Identity injects credentials directly without IMDS.
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
        tags=TAGS,
    )

    aws.iam.RolePolicyAttachment(
        f"{cluster_name}-ebs-csi-role-policy",
        role=ebs_csi_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy",
    )

    aws.eks.PodIdentityAssociation(
        f"{cluster_name}-ebs-csi-pod-identity",
        cluster_name=cluster.eks_cluster.name,
        namespace="kube-system",
        service_account="ebs-csi-controller-sa",
        role_arn=ebs_csi_role.arn,
        opts=pulumi.ResourceOptions(depends_on=[pod_identity_addon, ebs_csi_addon]),
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
        tags=TAGS,
    )

    aws.iam.RolePolicy(
        f"{cluster_name}-autoscaler-policy",
        role=autoscaler_role.id,
        policy=json.dumps(_AUTOSCALER_POLICY),
    )

    autoscaler_pod_identity = aws.eks.PodIdentityAssociation(
        f"{cluster_name}-autoscaler-pod-identity",
        cluster_name=cluster.eks_cluster.name,
        namespace="kube-system",
        service_account="cluster-autoscaler",
        role_arn=autoscaler_role.arn,
        opts=pulumi.ResourceOptions(depends_on=[pod_identity_addon]),
    )

    # =========================================================================
    # Helm addons: ALB Controller, metrics-server, cluster-autoscaler
    # =========================================================================
    k8s.helm.v3.Release(
        f"{cluster_name}-aws-lb-controller",
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
    )
