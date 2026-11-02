"""EC2 instance provisioning for the Locust load test cluster."""

from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

from ess_load_test.app_config import LocustSyncFile
from ess_load_test.infra.config import LoadTestInfraConfig
from ess_load_test.infra.constants import (
    UBUNTU_AMI_SSM_PARAMETER,
    get_tags,
    locust_pip,
    locust_venv_dir,
)
from ess_load_test.infra.network import NetworkPlacement


@dataclass
class InstanceOutputs:
    """Outputs from the instances module."""

    master_instance_id: pulumi.Output[str]
    master_private_ip: pulumi.Output[str]
    worker_instance_ids: list[pulumi.Output[str]]


def controller_hostname(resource_prefix: str) -> str:
    """Return the EC2 Name tag and OS hostname for the Locust coordinator."""
    return f"{resource_prefix}-locust-controller"


def worker_hostname(resource_prefix: str, index: int) -> str:
    """Return the EC2 Name tag and OS hostname for a Locust worker."""
    return f"{resource_prefix}-locust-worker-{index}"


EC2_USER_DATA_MAX_BYTES = 16 * 1024


def _build_user_data(
    hostname: str,
    *,
    locust_install_dir: str,
    cloud_init_files: tuple[LocustSyncFile, ...],
) -> str:
    """Build cloud-init user data that sets hostname and installs Locust.

    Locust scenario sources are synced via SSM before each run (see cluster
    runner); they are not embedded here because EC2 user_data is capped at
    16 KiB and a typical scenario bundle exceeds that limit.
    """
    del cloud_init_files
    venv_dir = locust_venv_dir(locust_install_dir)
    pip_bin = locust_pip(locust_install_dir)
    enable_ssm_agent = (
        "bash -lc 'systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service "
        "|| systemctl enable amazon-ssm-agent'"
    )
    start_ssm_agent = (
        "bash -lc 'systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service "
        "|| systemctl start amazon-ssm-agent'"
    )
    return f"""#cloud-config
hostname: {hostname}
fqdn: {hostname}.local
manage_etc_hosts: true
preserve_hostname: false
package_update: true
packages:
  - python3-pip
  - python3-venv
runcmd:
  - hostnamectl set-hostname {hostname}
  - mkdir -p {locust_install_dir}
  - python3 -m venv {venv_dir}
  - {pip_bin} install -q 'locust>=2.32,<3'
  - snap install amazon-ssm-agent --classic || apt-get install -y amazon-ssm-agent
  - {enable_ssm_agent}
  - {start_ssm_agent}
"""


def create_instance_profile(
    resource_prefix: str,
    *,
    component_name: str,
    environment: str,
    project_tag: str | None = None,
) -> aws.iam.InstanceProfile:
    """Create an IAM role and instance profile for SSM-managed EC2."""
    role = aws.iam.Role(
        f"{resource_prefix}-ec2-role",
        name=f"{resource_prefix}-ec2-role",
        assume_role_policy="""{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}""",
        tags=get_tags(
            component_name,
            environment,
            {"Name": f"{resource_prefix}-ec2-role"},
            project_tag=project_tag,
        ),
    )
    aws.iam.RolePolicyAttachment(
        f"{resource_prefix}-ssm-core",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    )
    profile = aws.iam.InstanceProfile(
        f"{resource_prefix}-ec2-profile",
        name=f"{resource_prefix}-ec2-profile",
        role=role.name,
        tags=get_tags(
            component_name,
            environment,
            {"Name": f"{resource_prefix}-ec2-profile"},
            project_tag=project_tag,
        ),
    )
    return profile


def create_instances(
    resource_prefix: str,
    config: LoadTestInfraConfig,
    placement: NetworkPlacement,
    security_group_id: pulumi.Input[str],
    instance_profile: aws.iam.InstanceProfile,
    *,
    component_name: str,
    locust_install_dir: str,
    cloud_init_files: tuple[LocustSyncFile, ...],
    project_tag: str | None = None,
) -> InstanceOutputs:
    """Create Locust coordinator and worker EC2 instances."""
    ami = aws.ssm.get_parameter(name=UBUNTU_AMI_SSM_PARAMETER)
    environment = config.environment

    common_args = {
        "ami": ami.value,
        "subnet_id": placement.subnet_id,
        "vpc_security_group_ids": [security_group_id],
        "iam_instance_profile": instance_profile.name,
        "associate_public_ip_address": True,
        "user_data_replace_on_change": True,
        "metadata_options": aws.ec2.InstanceMetadataOptionsArgs(
            http_endpoint="enabled",
            http_tokens="required",
        ),
        "root_block_device": aws.ec2.InstanceRootBlockDeviceArgs(
            volume_size=20,
            volume_type="gp3",
            encrypted=True,
        ),
    }

    controller_name = controller_hostname(resource_prefix)
    controller = aws.ec2.Instance(
        f"{resource_prefix}-locust-controller",
        instance_type=config.master_instance_type,
        user_data=_build_user_data(
            controller_name,
            locust_install_dir=locust_install_dir,
            cloud_init_files=cloud_init_files,
        ),
        tags=get_tags(
            component_name,
            environment,
            {
                "Name": controller_name,
                "Role": "locust-controller",
            },
            project_tag=project_tag,
        ),
        **common_args,
    )

    workers: list[aws.ec2.Instance] = []
    for index in range(config.worker_count):
        worker_name = worker_hostname(resource_prefix, index)
        worker = aws.ec2.Instance(
            f"{resource_prefix}-locust-worker-{index}",
            instance_type=config.instance_type,
            user_data=_build_user_data(
                worker_name,
                locust_install_dir=locust_install_dir,
                cloud_init_files=cloud_init_files,
            ),
            tags=get_tags(
                component_name,
                environment,
                {
                    "Name": worker_name,
                    "Role": "locust-worker",
                },
                project_tag=project_tag,
            ),
            **common_args,
        )
        workers.append(worker)

    return InstanceOutputs(
        master_instance_id=controller.id,
        master_private_ip=controller.private_ip,
        worker_instance_ids=[worker.id for worker in workers],
    )
