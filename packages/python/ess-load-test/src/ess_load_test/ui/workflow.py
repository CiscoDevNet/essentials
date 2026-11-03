"""Orchestration for the Locust web UI workflow."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import boto3
import click
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    NoRegionError,
    ProfileNotFound,
)

from ess_load_test.app_config import AppConfig
from ess_load_test.cli.load_params import LoadTestParams
from ess_load_test.cluster.outputs import StackOutputError, load_stack_outputs
from ess_load_test.cluster.runner import (
    LoadTestUiRequest,
    build_ui_port_forward_command,
    get_cluster_status,
    start_locust_ui,
)


class UiWorkflowError(RuntimeError):
    """Raised when the Locust UI workflow cannot proceed."""


@dataclass(frozen=True)
class UiWorkflowConfig:
    """Parameters for the Locust web UI workflow."""

    app_config: AppConfig
    target_url: str
    paths: str = "/"
    scenario: str | None = None
    stack: str | None = None
    profile: str | None = None
    region: str | None = None
    local_port: int = 8089
    fetch_token: bool = True
    auth_header: str | None = None
    browser_auth: bool = False
    headed: bool = False
    browser_profile_dir: str | None = None
    load_params: LoadTestParams | None = None

    @property
    def resolved_load_params(self) -> LoadTestParams:
        if self.load_params is not None:
            return self.load_params
        return LoadTestParams()

    @property
    def resolved_scenario(self) -> str:
        if self.scenario is not None:
            return self.scenario
        return self.app_config.ui_default_scenario

    @property
    def resolved_stack(self) -> str:
        return self.stack or self.app_config.default_stack

    @property
    def resolved_profile(self) -> str | None:
        return (
            self.profile
            if self.profile is not None
            else self.app_config.default_profile
        )

    @property
    def resolved_region(self) -> str | None:
        return self.region


def run_preflight(config: UiWorkflowConfig) -> None:
    """Verify target URL and AWS credentials before starting Locust."""
    if not config.target_url.strip():
        msg = "Target URL is required (e.g. https://app.example.com)"
        raise UiWorkflowError(msg)

    session_kwargs: dict[str, str] = {}
    if config.resolved_profile:
        session_kwargs["profile_name"] = config.resolved_profile
    if config.resolved_region:
        session_kwargs["region_name"] = config.resolved_region

    try:
        boto3.Session(**session_kwargs).client("sts").get_caller_identity()
    except (ClientError, NoCredentialsError, NoRegionError, ProfileNotFound) as exc:
        msg = (
            f"AWS credentials failed for profile {config.resolved_profile!r}. "
            "Refresh your AWS SSO session and retry."
        )
        raise UiWorkflowError(msg) from exc


def resolve_auth_header(
    explicit_header: str | None,
    *,
    fetch_token: bool,
    resolve_token,
) -> str | None:
    """Resolve the Locust auth header from explicit value, env, or OAuth."""
    if explicit_header:
        return explicit_header
    if not fetch_token:
        return None
    return resolve_token()


def open_locust_ui(
    config: UiWorkflowConfig,
    *,
    resolve_token,
) -> tuple[dict[str, object], str]:
    """Preflight, start Locust UI, return outputs and forward cmd."""
    run_preflight(config)
    try:
        outputs = load_stack_outputs(
            config.resolved_stack,
            config.app_config.pulumi_project_dir,
        )
    except StackOutputError as exc:
        raise UiWorkflowError(str(exc)) from exc

    resolved_region = config.resolved_region or str(outputs.get("region", "us-east-1"))
    resolved_auth = resolve_auth_header(
        config.auth_header,
        fetch_token=config.fetch_token,
        resolve_token=resolve_token,
    )

    try:
        request = LoadTestUiRequest(
            stack=config.resolved_stack,
            target_url=config.target_url,
            paths=config.paths,
            scenario=config.resolved_scenario,
            load_params=config.resolved_load_params,
            auth_header=resolved_auth,
            profile=config.resolved_profile,
            region=resolved_region or None,
        )
        start_locust_ui(request, config.app_config)
    except (RuntimeError, TimeoutError) as exc:
        raise UiWorkflowError(str(exc)) from exc

    forward_command = build_ui_port_forward_command(
        master_instance_id=str(outputs["master_instance_id"]),
        region=resolved_region,
        profile=config.resolved_profile,
        local_port=config.local_port,
    )
    return outputs, forward_command


def print_cluster_status(config: UiWorkflowConfig) -> None:
    """Print Pulumi outputs and SSM reachability."""
    try:
        outputs = load_stack_outputs(
            config.resolved_stack,
            config.app_config.pulumi_project_dir,
        )
        resolved_region = config.resolved_region or str(outputs.get("region", ""))
        status = get_cluster_status(
            stack=config.resolved_stack,
            profile=config.resolved_profile,
            region=resolved_region or None,
            app_config=config.app_config,
        )
    except StackOutputError as exc:
        raise UiWorkflowError(str(exc)) from exc

    stack_outputs = status["outputs"]
    click.echo(f"master_instance_id: {stack_outputs['master_instance_id']}")
    click.echo(f"master_private_ip: {stack_outputs['master_private_ip']}")
    click.echo(f"worker_instance_ids: {stack_outputs['worker_instance_ids']}")
    click.echo(f"security_group_id: {stack_outputs['security_group_id']}")
    click.echo(f"region: {stack_outputs['region']}")
    click.echo("ssm_ping_status:")
    for instance_id, ping_status in status["ssm_ping_status"].items():
        click.echo(f"  {instance_id}: {ping_status}")


def build_port_forward_argv(
    *,
    master_instance_id: str,
    region: str,
    profile: str | None,
    local_port: int,
) -> list[str]:
    """Build argv for `aws ssm start-session` port-forward (no shell)."""
    command = [
        "aws",
    ]
    if profile:
        command.extend(["--profile", profile])
    command.extend(
        [
            "ssm",
            "start-session",
            "--target",
            master_instance_id,
            "--region",
            region,
            "--document-name",
            "AWS-StartPortForwardingSession",
            "--parameters",
            f"localPortNumber={local_port},portNumber=8089",
        ]
    )
    return command


def run_port_forward(config: UiWorkflowConfig, *, exec_forward: bool) -> str:
    """Print or run the SSM port-forward command for the Locust web UI."""
    try:
        outputs = load_stack_outputs(
            config.resolved_stack,
            config.app_config.pulumi_project_dir,
        )
    except StackOutputError as exc:
        raise UiWorkflowError(str(exc)) from exc

    resolved_region = config.resolved_region or str(outputs.get("region", "us-east-1"))
    master_instance_id = str(outputs["master_instance_id"])
    forward_command = build_ui_port_forward_command(
        master_instance_id=master_instance_id,
        region=resolved_region,
        profile=config.resolved_profile,
        local_port=config.local_port,
    )

    if exec_forward:
        argv = build_port_forward_argv(
            master_instance_id=master_instance_id,
            region=resolved_region,
            profile=config.resolved_profile,
            local_port=config.local_port,
        )
        click.echo(
            f"==> Port-forwarding Locust UI to http://localhost:{config.local_port}"
        )
        subprocess.run(argv, check=True)

    return forward_command
