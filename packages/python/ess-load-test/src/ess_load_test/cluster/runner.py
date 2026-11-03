"""SSM orchestration for distributed Locust test runs."""

# The remote shell scripts below are f-string templates, and a noqa comment
# inside one would become part of the script, so line length is waived here.
# ruff: noqa: E501

import base64
import logging
import os
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from ess_load_test.app_config import AppConfig
from ess_load_test.cli.load_params import LoadTestParams, build_locust_load_flag_lines
from ess_load_test.cluster.outputs import load_stack_outputs
from ess_load_test.infra.constants import locust_bin, locust_venv_dir
from ess_load_test.locust.runtime import normalize_locust_host

logger = logging.getLogger(__name__)

_SSM_DOCUMENT = "AWS-RunShellScript"
_POLL_INTERVAL_SECONDS = 5
_COMMAND_TIMEOUT_SECONDS = 3600
_WEB_UI_PORT = 8089
_LOCUST_MASTER_PORT = 5557
_LOCUST_STATS_PORT = 5558
_OPERATOR_SCENARIO_ENV_KEYS = frozenset(
    {"LOAD_TEST_PRODUCT_SLUG", "LOAD_TEST_THINK_TIME", "LOAD_TEST_CHAT_PROMPTS"}
)


def _operator_scenario_env_exports() -> str:
    """Export scenario tuning vars from the operator shell onto cluster workers."""
    lines: list[str] = []
    for key, value in sorted(os.environ.items()):
        if not value:
            continue
        if key in _OPERATOR_SCENARIO_ENV_KEYS:
            lines.append(f"export {key}={_shell_quote(value)}")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


_VALID_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_extra_env_key(key: str) -> None:
    if not _VALID_ENV_KEY.match(key):
        msg = f"Invalid extra_env key {key!r}: must be an ASCII shell identifier"
        raise ValueError(msg)


def _reset_locust_cluster_script() -> str:
    return f"""
set -euo pipefail
pkill -f '[/]locust' 2>/dev/null || true
fuser -k {_LOCUST_MASTER_PORT}/tcp 2>/dev/null || true
fuser -k {_LOCUST_STATS_PORT}/tcp 2>/dev/null || true
fuser -k {_WEB_UI_PORT}/tcp 2>/dev/null || true
if pgrep -f '[/]locust' >/dev/null 2>&1; then
  echo 'Locust processes still running after reset.' >&2
  pgrep -af '[/]locust' >&2 || true
  exit 1
fi
echo 'OK: Locust processes stopped and coordination ports are free'
"""


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _base64_write_file_command(remote_path: str, payload_b64: str) -> str:
    quoted_path = _shell_quote(remote_path)
    quoted_payload = _shell_quote(payload_b64)
    return f"printf '%s' {quoted_payload} | base64 -d > {quoted_path}"


def _auth_file_bootstrap_lines(auth_header: str | None) -> str:
    """Write the auth header to a file so workers avoid shell-export mangling."""
    if not auth_header:
        return ""
    payload_b64 = base64.b64encode(auth_header.encode()).decode("ascii")
    quoted_payload = _shell_quote(payload_b64)
    return (
        "_auth_file=$(mktemp)\n"
        f"printf '%s' {quoted_payload} | base64 -d > \"$_auth_file\"\n"
        'chmod 600 "$_auth_file"\n'
        'export LOAD_TEST_AUTH_HEADER_FILE="$_auth_file"\n'
    )


def _build_sync_locust_sources_script(app_config: AppConfig) -> str:
    install_dir = app_config.locust_install_dir
    lines = ["set -euo pipefail", f"mkdir -p {install_dir!r}"]
    for sync_file in app_config.locust_bundle.sync_files:
        payload_b64 = base64.b64encode(sync_file.local_path.read_bytes()).decode(
            "ascii"
        )
        lines.append(_base64_write_file_command(sync_file.remote_path, payload_b64))
    return "\n".join(lines)


def _bootstrap_locust_script(install_dir: str) -> str:
    venv_dir = locust_venv_dir(install_dir)
    pip_bin = f"{venv_dir}/bin/pip"
    bin_path = locust_bin(install_dir)
    return f"""
set -euo pipefail
if [[ -x {bin_path!r} ]]; then
  exit 0
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv
python3 -m venv {venv_dir!r}
{pip_bin!r} install -q 'locust>=2.32,<3'
"""


def _verify_master_web_ui_script() -> str:
    return f"""
set -euo pipefail
for attempt in $(seq 1 30); do
  if ss -tln 2>/dev/null | grep -q ':{_WEB_UI_PORT} ' || \\
     netstat -tln 2>/dev/null | grep -q ':{_WEB_UI_PORT} '; then
    exit 0
  fi
  sleep 2
done
echo 'Locust web UI is not listening on port {_WEB_UI_PORT}.' >&2
tail -30 /var/log/locust-master.log 2>/dev/null || true
exit 1
"""


@dataclass(frozen=True)
class LoadTestRunRequest:
    """Parameters for a distributed Locust run."""

    stack: str
    target_url: str
    paths: str
    scenario: str
    load_params: LoadTestParams
    auth_header: str | None
    profile: str | None
    region: str | None
    extra_env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LoadTestUiRequest:
    """Parameters for starting the Locust web UI on the cluster."""

    stack: str
    target_url: str
    paths: str
    scenario: str
    load_params: LoadTestParams
    auth_header: str | None
    profile: str | None
    region: str | None
    extra_env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class WorkerRuntimeEnv:
    """Environment variables workers need to match the master's locustfile."""

    scenario: str
    paths: str
    auth_header: str | None
    extra_env: tuple[tuple[str, str], ...] = ()


def _extra_env_exports(extra_env: tuple[tuple[str, str], ...]) -> str:
    if not extra_env:
        return ""
    lines: list[str] = []
    for key, value in extra_env:
        if not key:
            continue
        _validate_extra_env_key(key)
        lines.append(f"export {key}={_shell_quote(value)}")
    return "\n".join(lines) + "\n"


def _worker_runtime_env(
    *,
    scenario: str,
    paths: str,
    auth_header: str | None,
    extra_env: tuple[tuple[str, str], ...] = (),
) -> WorkerRuntimeEnv:
    return WorkerRuntimeEnv(
        scenario=scenario,
        paths=paths,
        auth_header=auth_header,
        extra_env=extra_env,
    )


def _wrap_bash_script(script: str) -> str:
    """Wrap a script for SSM RunShellScript."""
    return f"bash -c {_shell_quote(script.strip())}"


def _create_ssm_client(profile: str | None, region: str | None):
    session_kwargs: dict[str, str] = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region
    session = boto3.Session(**session_kwargs)
    return session.client("ssm")


def _locustfile_remote_path(app_config: AppConfig) -> str:
    for sync_file in app_config.locust_bundle.sync_files:
        if sync_file.local_path.name == "locustfile.py":
            return sync_file.remote_path
    return f"{app_config.locust_install_dir}/locustfile.py"


def _build_worker_command(
    app_config: AppConfig,
    master_private_ip: str,
    runtime: WorkerRuntimeEnv,
) -> str:
    install_dir = app_config.locust_install_dir
    locustfile_path = _locustfile_remote_path(app_config)
    master_host = _shell_quote(master_private_ip)
    bin_path = locust_bin(install_dir)
    auth_export = ""
    auth_file_bootstrap = ""
    if runtime.auth_header:
        auth_export = (
            f"export LOAD_TEST_AUTH_HEADER={_shell_quote(runtime.auth_header)}\n"
        )
        auth_file_bootstrap = _auth_file_bootstrap_lines(runtime.auth_header)
    extra_exports = _extra_env_exports(runtime.extra_env)
    return f"""
set -euo pipefail
export PYTHONPATH={install_dir!r}
export LOAD_TEST_PATHS={_shell_quote(runtime.paths)}
{_scenario_export(runtime.scenario)}{_operator_scenario_env_exports()}{auth_export}{extra_exports}{auth_file_bootstrap}pkill -x locust 2>/dev/null || true
nohup {bin_path} -f {locustfile_path} --worker --master-host {master_host} \\
  > /var/log/locust-worker.log 2>&1 &
"""


def _scenario_export(scenario: str) -> str:
    return f"export LOAD_TEST_SCENARIO={_shell_quote(scenario)}\n"


def _load_params_env_exports(params: LoadTestParams) -> str:
    """Export load-test env vars so the Locust web UI can pre-fill Start defaults."""
    lines = [
        f"export LOAD_TEST_USERS={params.users}",
        f"export LOAD_TEST_SPAWN_RATE={params.spawn_rate}",
        f"export LOCUST_USERS={params.users}",
        f"export LOCUST_SPAWN_RATE={params.spawn_rate}",
    ]
    if params.duration is not None:
        duration = _shell_quote(params.duration)
        lines.append(f"export LOAD_TEST_DURATION={duration}")
        lines.append(f"export LOCUST_RUN_TIME={duration}")
    return "\n".join(lines) + "\n"


def _format_load_flag_lines(params: LoadTestParams, *, headless: bool) -> str:
    lines = build_locust_load_flag_lines(
        params,
        headless=headless,
        shell_quote=_shell_quote,
    )
    if not lines:
        return ""
    return "  " + " \\\n  ".join(lines) + " \\\n"


def _build_master_command(
    request: LoadTestRunRequest,
    app_config: AppConfig,
    *,
    master_private_ip: str,
    worker_count: int,
) -> str:
    install_dir = app_config.locust_install_dir
    locustfile_path = _locustfile_remote_path(app_config)
    bin_path = locust_bin(install_dir)
    auth_export = ""
    auth_file_bootstrap = ""
    if request.auth_header:
        auth_export = (
            f"export LOAD_TEST_AUTH_HEADER={_shell_quote(request.auth_header)}\n"
        )
        auth_file_bootstrap = _auth_file_bootstrap_lines(request.auth_header)
    load_flags = _format_load_flag_lines(request.load_params, headless=True)
    load_env = _load_params_env_exports(request.load_params)
    extra_exports = _extra_env_exports(request.extra_env)
    return f"""
set -euo pipefail
export PYTHONPATH={install_dir!r}
export LOAD_TEST_PATHS={_shell_quote(request.paths)}
{_scenario_export(request.scenario)}{_operator_scenario_env_exports()}{load_env}{auth_export}{extra_exports}{auth_file_bootstrap}pkill -x locust 2>/dev/null || true
{bin_path} -f {locustfile_path} \\
  --master \\
  --master-bind-host {_shell_quote(master_private_ip)} \\
  --expect-workers {worker_count} \\
{load_flags}  --host {_shell_quote(normalize_locust_host(request.target_url))}
"""


def _build_master_ui_command(
    request: LoadTestUiRequest,
    app_config: AppConfig,
    *,
    master_private_ip: str,
    worker_count: int,
) -> str:
    install_dir = app_config.locust_install_dir
    locustfile_path = _locustfile_remote_path(app_config)
    bin_path = locust_bin(install_dir)
    auth_export = ""
    auth_file_bootstrap = ""
    if request.auth_header:
        auth_export = (
            f"export LOAD_TEST_AUTH_HEADER={_shell_quote(request.auth_header)}\n"
        )
        auth_file_bootstrap = _auth_file_bootstrap_lines(request.auth_header)
    load_flags = _format_load_flag_lines(request.load_params, headless=False)
    load_env = _load_params_env_exports(request.load_params)
    extra_exports = _extra_env_exports(request.extra_env)
    return f"""
set -euo pipefail
export PYTHONPATH={install_dir!r}
export LOAD_TEST_PATHS={_shell_quote(request.paths)}
{_scenario_export(request.scenario)}{_operator_scenario_env_exports()}{load_env}{auth_export}{extra_exports}{auth_file_bootstrap}pkill -x locust 2>/dev/null || true
nohup {bin_path} -f {locustfile_path} \\
  --master \\
  --master-bind-host {_shell_quote(master_private_ip)} \\
  --expect-workers {worker_count} \\
  --class-picker \\
  --web-host 127.0.0.1 \\
{load_flags}  --host {_shell_quote(normalize_locust_host(request.target_url))} \\
  > /var/log/locust-master.log 2>&1 &
"""


def _send_command(
    ssm_client,
    *,
    instance_ids: Sequence[str],
    commands: Sequence[str],
    comment: str,
) -> str:
    response = ssm_client.send_command(
        InstanceIds=list(instance_ids),
        DocumentName=_SSM_DOCUMENT,
        Comment=comment,
        Parameters={"commands": list(commands)},
        TimeoutSeconds=_COMMAND_TIMEOUT_SECONDS,
    )
    return response["Command"]["CommandId"]


def _wait_for_command(
    ssm_client,
    *,
    command_id: str,
    instance_id: str,
) -> str:
    deadline = time.time() + _COMMAND_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            response = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code != "InvocationDoesNotExist":
                raise
            time.sleep(_POLL_INTERVAL_SECONDS)
            continue
        status = response["Status"]
        if status in {"Success", "Cancelled", "TimedOut", "Failed"}:
            stdout = response.get("StandardOutputContent", "")
            stderr = response.get("StandardErrorContent", "")
            if status != "Success":
                msg = f"SSM command {command_id} on {instance_id} ended with {status}"
                if stderr:
                    msg = f"{msg}\n{stderr}"
                raise RuntimeError(msg)
            return stdout
        time.sleep(_POLL_INTERVAL_SECONDS)

    msg = f"Timed out waiting for SSM command {command_id} on {instance_id}"
    raise TimeoutError(msg)


def _sync_locust_sources(
    ssm_client,
    *,
    instance_ids: Sequence[str],
    app_config: AppConfig,
) -> None:
    if not instance_ids:
        return
    script = _build_sync_locust_sources_script(app_config)
    command_id = _send_command(
        ssm_client,
        instance_ids=instance_ids,
        commands=[_wrap_bash_script(script)],
        comment="Sync Locust source files",
    )
    for instance_id in instance_ids:
        _wait_for_command(
            ssm_client,
            command_id=command_id,
            instance_id=instance_id,
        )


def _bootstrap_locust(
    ssm_client,
    *,
    instance_ids: Sequence[str],
    app_config: AppConfig,
) -> None:
    if not instance_ids:
        return
    script = _bootstrap_locust_script(app_config.locust_install_dir)
    command_id = _send_command(
        ssm_client,
        instance_ids=instance_ids,
        commands=[_wrap_bash_script(script)],
        comment="Bootstrap Locust if missing",
    )
    for instance_id in instance_ids:
        _wait_for_command(
            ssm_client,
            command_id=command_id,
            instance_id=instance_id,
        )


def _verify_master_web_ui(
    ssm_client,
    *,
    master_instance_id: str,
) -> None:
    command_id = _send_command(
        ssm_client,
        instance_ids=[master_instance_id],
        commands=[_wrap_bash_script(_verify_master_web_ui_script())],
        comment="Verify Locust web UI port",
    )
    _wait_for_command(
        ssm_client,
        command_id=command_id,
        instance_id=master_instance_id,
    )


def _start_workers(
    ssm_client,
    *,
    worker_instance_ids: Sequence[str],
    master_private_ip: str,
    app_config: AppConfig,
    runtime: WorkerRuntimeEnv,
) -> None:
    if not worker_instance_ids:
        return
    worker_command_id = _send_command(
        ssm_client,
        instance_ids=worker_instance_ids,
        commands=[
            _wrap_bash_script(
                _build_worker_command(
                    app_config,
                    master_private_ip,
                    runtime,
                )
            )
        ],
        comment="Start Locust workers",
    )
    for worker_id in worker_instance_ids:
        _wait_for_command(
            ssm_client,
            command_id=worker_command_id,
            instance_id=worker_id,
        )


def run_load_test(request: LoadTestRunRequest, app_config: AppConfig) -> str:
    """Start workers, run a headless Locust test on the master, and return stdout."""
    outputs = load_stack_outputs(request.stack, app_config.pulumi_project_dir)
    master_instance_id = str(outputs["master_instance_id"])
    master_private_ip = str(outputs["master_private_ip"])
    worker_instance_ids = [
        str(instance_id) for instance_id in outputs["worker_instance_ids"]
    ]
    worker_count = len(worker_instance_ids)

    ssm_client = _create_ssm_client(request.profile, request.region)
    all_instance_ids = [master_instance_id, *worker_instance_ids]
    _sync_locust_sources(
        ssm_client, instance_ids=all_instance_ids, app_config=app_config
    )
    _bootstrap_locust(ssm_client, instance_ids=all_instance_ids, app_config=app_config)
    _start_workers(
        ssm_client,
        worker_instance_ids=worker_instance_ids,
        master_private_ip=master_private_ip,
        app_config=app_config,
        runtime=_worker_runtime_env(
            scenario=request.scenario,
            paths=request.paths,
            auth_header=request.auth_header,
            extra_env=request.extra_env,
        ),
    )

    master_command_id = _send_command(
        ssm_client,
        instance_ids=[master_instance_id],
        commands=[
            _wrap_bash_script(
                _build_master_command(
                    request,
                    app_config,
                    master_private_ip=master_private_ip,
                    worker_count=worker_count,
                )
            )
        ],
        comment="Run Locust headless master",
    )
    return _wait_for_command(
        ssm_client,
        command_id=master_command_id,
        instance_id=master_instance_id,
    )


def start_locust_ui(request: LoadTestUiRequest, app_config: AppConfig) -> str:
    """Start workers and a Locust master with the web UI enabled."""
    outputs = load_stack_outputs(request.stack, app_config.pulumi_project_dir)
    master_instance_id = str(outputs["master_instance_id"])
    master_private_ip = str(outputs["master_private_ip"])
    worker_instance_ids = [
        str(instance_id) for instance_id in outputs["worker_instance_ids"]
    ]
    worker_count = len(worker_instance_ids)

    ssm_client = _create_ssm_client(request.profile, request.region)
    all_instance_ids = [master_instance_id, *worker_instance_ids]
    _sync_locust_sources(
        ssm_client, instance_ids=all_instance_ids, app_config=app_config
    )
    _bootstrap_locust(ssm_client, instance_ids=all_instance_ids, app_config=app_config)
    _start_workers(
        ssm_client,
        worker_instance_ids=worker_instance_ids,
        master_private_ip=master_private_ip,
        app_config=app_config,
        runtime=_worker_runtime_env(
            scenario=request.scenario,
            paths=request.paths,
            auth_header=request.auth_header,
            extra_env=request.extra_env,
        ),
    )

    master_command_id = _send_command(
        ssm_client,
        instance_ids=[master_instance_id],
        commands=[
            _wrap_bash_script(
                _build_master_ui_command(
                    request,
                    app_config,
                    master_private_ip=master_private_ip,
                    worker_count=worker_count,
                )
            )
        ],
        comment="Start Locust master web UI",
    )
    stdout = _wait_for_command(
        ssm_client,
        command_id=master_command_id,
        instance_id=master_instance_id,
    )
    _verify_master_web_ui(ssm_client, master_instance_id=master_instance_id)
    return stdout


def reset_cluster_locust(
    *,
    stack: str,
    profile: str | None,
    region: str | None,
    app_config: AppConfig,
) -> None:
    """Stop Locust on all cluster instances and free RPC/web UI ports."""
    outputs = load_stack_outputs(stack, app_config.pulumi_project_dir)
    instance_ids = [str(outputs["master_instance_id"])]
    instance_ids.extend(
        str(instance_id) for instance_id in outputs["worker_instance_ids"]
    )

    ssm_client = _create_ssm_client(profile, region)
    command_id = _send_command(
        ssm_client,
        instance_ids=instance_ids,
        commands=[_wrap_bash_script(_reset_locust_cluster_script())],
        comment="Reset Locust processes on cluster",
    )
    for instance_id in instance_ids:
        _wait_for_command(
            ssm_client,
            command_id=command_id,
            instance_id=instance_id,
        )


def get_cluster_status(
    *,
    stack: str,
    profile: str | None,
    region: str | None,
    app_config: AppConfig,
) -> dict[str, object]:
    """Return stack outputs and SSM ping status for cluster instances."""
    outputs = load_stack_outputs(stack, app_config.pulumi_project_dir)
    instance_ids = [str(outputs["master_instance_id"])]
    instance_ids.extend(
        str(instance_id) for instance_id in outputs["worker_instance_ids"]
    )

    ssm_client = _create_ssm_client(profile, region)
    response = ssm_client.describe_instance_information(
        Filters=[{"Key": "InstanceIds", "Values": instance_ids}],
    )
    ping_status = dict.fromkeys(instance_ids, "Unknown")
    for entry in response.get("InstanceInformationList", []):
        ping_status[entry["InstanceId"]] = entry.get("PingStatus", "Unknown")

    return {
        "outputs": outputs,
        "ssm_ping_status": ping_status,
    }


def build_ui_port_forward_command(
    *,
    master_instance_id: str,
    region: str,
    profile: str | None,
    local_port: int = 8089,
) -> str:
    """Return the AWS CLI command to port-forward the Locust web UI."""
    profile_flag = f"--profile {profile} " if profile else ""
    return (
        f"aws {profile_flag}ssm start-session "
        f"--target {master_instance_id} "
        f"--region {region} "
        f"--document-name AWS-StartPortForwardingSession "
        f"--parameters localPortNumber={local_port},portNumber=8089"
    )
