"""Composable Locust load-test cluster deployment."""

from pathlib import Path

import pulumi
import pulumi_aws as aws
from dotenv import load_dotenv

from ess_load_test.app_config import LocustBundle, LocustSyncFile, default_app_config
from ess_load_test.infra.config import load_config
from ess_load_test.infra.instances import create_instance_profile, create_instances
from ess_load_test.infra.network import create_network, resolve_network_placement


def deploy_cluster(  # noqa: PLR0913  -- all params are keyword-only with defaults
    *,
    locust_install_dir: str | None = None,
    component_name: str | None = None,
    pulumi_config_namespace: str | None = None,
    cloud_init_bundle: LocustBundle | None = None,
    pulumi_project_dir: Path | None = None,
    project_tag: str | None = None,
) -> None:
    """Deploy the Locust EC2 cluster and export Pulumi outputs.

    Shells call this from ``infra/__main__.py`` with organization-specific
    install paths, tags, and Locust source bundles. ``project_tag`` sets the
    ``Project`` tag on every resource and defaults to the component name.
    """
    defaults = default_app_config()
    resolved_install_dir = locust_install_dir or defaults.locust_install_dir
    resolved_component = component_name or defaults.component_name
    resolved_namespace = pulumi_config_namespace or defaults.config_namespace
    resolved_bundle = cloud_init_bundle or defaults.locust_bundle
    resolved_project_dir = pulumi_project_dir or defaults.pulumi_project_dir

    load_dotenv(resolved_project_dir / ".env")

    config = load_config(resolved_namespace)
    resource_prefix = f"load-test-{config.environment}"

    current_region = aws.get_region()
    placement = resolve_network_placement(
        config,
        config_namespace=resolved_namespace,
    )
    network = create_network(
        resource_prefix,
        placement,
        component_name=resolved_component,
        environment=config.environment,
        project_tag=project_tag,
    )
    instance_profile = create_instance_profile(
        resource_prefix,
        component_name=resolved_component,
        environment=config.environment,
        project_tag=project_tag,
    )
    instances = create_instances(
        resource_prefix=resource_prefix,
        config=config,
        placement=placement,
        security_group_id=network.security_group_id,
        instance_profile=instance_profile,
        component_name=resolved_component,
        locust_install_dir=resolved_install_dir,
        cloud_init_files=cloud_init_files_from_bundle(resolved_bundle),
        project_tag=project_tag,
    )

    pulumi.export("master_instance_id", instances.master_instance_id)
    pulumi.export("master_private_ip", instances.master_private_ip)
    pulumi.export("worker_instance_ids", instances.worker_instance_ids)
    pulumi.export("security_group_id", network.security_group_id)
    pulumi.export("region", current_region.region)
    pulumi.export("worker_count", config.worker_count)


def cloud_init_files_from_bundle(bundle: LocustBundle) -> tuple[LocustSyncFile, ...]:
    """Return sync files for cloud-init (paths must exist on disk)."""
    for sync_file in bundle.sync_files:
        if not sync_file.local_path.is_file():
            msg = f"Cloud-init source missing: {sync_file.local_path}"
            raise FileNotFoundError(msg)
    return bundle.sync_files
