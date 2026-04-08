"""VPC resources for LangSmith Hosting infrastructure.

Creates a VPC with public and private subnets across 3 availability zones,
a single NAT gateway, and subnet tags for EKS auto-discovery.
"""

from dataclasses import dataclass

import pulumi
import pulumi_awsx as awsx

from langsmith_hosting.constants import get_tags


@dataclass
class VpcOutputs:
    """Outputs from the VPC module."""

    vpc_id: pulumi.Output[str]
    private_subnet_ids: pulumi.Output[list[str]]
    public_subnet_ids: pulumi.Output[list[str]]
    vpc_cidr_block: pulumi.Output[str]
    nat_gateway_public_ips: pulumi.Output[list[str]]


def create_vpc(
    cluster_name: str,
    cidr_block: str,
) -> VpcOutputs:
    """Create a VPC with public/private subnets for LangSmith infrastructure.

    Args:
        cluster_name: EKS cluster name, used for naming and subnet tags.
        cidr_block: CIDR block for the VPC (e.g. "10.0.0.0/16").

    Returns:
        VpcOutputs with VPC ID, subnet IDs, and CIDR block.
    """
    tags = get_tags("vpc")
    vpc = awsx.ec2.Vpc(
        f"{cluster_name}-vpc",
        cidr_block=cidr_block,
        enable_dns_hostnames=True,
        number_of_availability_zones=3,
        nat_gateways=awsx.ec2.NatGatewayConfigurationArgs(
            strategy=awsx.ec2.NatGatewayStrategy.SINGLE,
        ),
        subnet_strategy=awsx.ec2.SubnetAllocationStrategy.AUTO,
        subnet_specs=[
            awsx.ec2.SubnetSpecArgs(
                type=awsx.ec2.SubnetType.PRIVATE,
                cidr_mask=19,
                tags={
                    **tags,
                    f"kubernetes.io/cluster/{cluster_name}": "shared",
                    "kubernetes.io/role/internal-elb": "1",
                },
            ),
            awsx.ec2.SubnetSpecArgs(
                type=awsx.ec2.SubnetType.PUBLIC,
                cidr_mask=20,
                tags={
                    **tags,
                    f"kubernetes.io/cluster/{cluster_name}": "shared",
                    "kubernetes.io/role/elb": "1",
                },
            ),
        ],
        tags=tags,
    )

    nat_gateway_public_ips = pulumi.Output.all(vpc.eips).apply(
        lambda eips_list: [eip.public_ip for eip in eips_list[0]]
    )

    return VpcOutputs(
        vpc_id=vpc.vpc_id,
        private_subnet_ids=vpc.private_subnet_ids,
        public_subnet_ids=vpc.public_subnet_ids,
        vpc_cidr_block=pulumi.Output.from_input(cidr_block),
        nat_gateway_public_ips=nat_gateway_public_ips,
    )
