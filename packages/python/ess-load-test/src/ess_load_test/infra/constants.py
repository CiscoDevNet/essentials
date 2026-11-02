"""Shared constants for ess-load-test Pulumi stacks."""

UBUNTU_AMI_SSM_PARAMETER = (
    "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id"
)


def locustfile_remote_path(install_dir: str) -> str:
    return f"{install_dir}/locustfile.py"


def locust_venv_dir(install_dir: str) -> str:
    return f"{install_dir}/venv"


def locust_bin(install_dir: str) -> str:
    return f"{locust_venv_dir(install_dir)}/bin/locust"


def locust_pip(install_dir: str) -> str:
    return f"{locust_venv_dir(install_dir)}/bin/pip"


def base_tags(component_name: str, project_tag: str | None = None) -> dict[str, str]:
    return {
        "Project": project_tag or component_name,
        "ManagedBy": "pulumi",
        "Component": component_name,
    }


def get_tags(
    component_name: str,
    environment: str,
    extra: dict[str, str] | None = None,
    *,
    project_tag: str | None = None,
) -> dict[str, str]:
    """Merge base tags with environment and optional extra tags.

    ``project_tag`` sets the ``Project`` tag and defaults to
    ``component_name``.
    """
    merged = {**base_tags(component_name, project_tag), "Environment": environment}
    if extra:
        merged.update(extra)
    return merged
