"""Base URL resolution for deployed LangGraph agents."""

import subprocess  # nosec B404  # developer tooling shells out to kubectl
import urllib.parse

import click

from ess_langsmith_client import resolve_deployment_base_url

_DEFAULT_PORT_FORWARD_HOST = "http://localhost:8000"


def _detect_prefix() -> str | None:
    """Auto-detect the mount prefix from a running agent pod."""
    try:
        result = subprocess.run(  # nosec B603 B607  # hardcoded kubectl with list args, no shell
            [
                "kubectl",
                "get",
                "pods",
                "-o",
                "jsonpath={range .items[*]}{range .spec.containers[0].env[*]}"
                '{.name}={.value}{"\\n"}{end}{end}',
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in result.stdout.splitlines():
        if line.startswith("MOUNT_PREFIX="):
            return line.split("=", 1)[1]
    return None


def resolve_prefix_via_kubectl(host: str) -> str:
    """Join a host URL with the mount prefix auto-detected from kubectl."""
    click.echo("Auto-detecting mount prefix from kubectl...")
    detected = _detect_prefix()
    if not detected:
        raise click.ClickException(
            "Could not auto-detect mount prefix from kubectl. Use --prefix to specify."
        )
    click.echo(f"  Found: {detected}")
    return f"{host.rstrip('/')}{detected}"


def join_host_with_custom_url(host_url: str, custom_url: str) -> str:
    """Combine a user-supplied friendly host with a control-plane ``custom_url`` path.

    Args:
        host_url: Ingress host the user wants to hit (e.g.
            ``https://agents.example.com``). Only scheme and netloc are used.
        custom_url: Full URL from the control plane (e.g.
            ``https://agents.internal.example.com/lgp/hello-agent-dev-abc``).

    Returns:
        ``{host scheme+netloc}{custom_url path}`` with no trailing slash on the host.

    Raises:
        click.ClickException: if ``custom_url`` has no path to join.
    """
    host = urllib.parse.urlparse(host_url)
    custom = urllib.parse.urlparse(custom_url)
    if not custom.path or custom.path == "/":
        raise click.ClickException(
            f"Deployment custom_url has no mount path: {custom_url!r}. "
            "Use --prefix or --kubectl instead."
        )
    scheme = host.scheme or custom.scheme or "https"
    netloc = host.netloc or custom.netloc
    if not netloc:
        raise click.ClickException(
            f"Could not determine host from --url={host_url!r} or custom_url."
        )
    return f"{scheme}://{netloc}{custom.path}"


def resolve_base_url(  # noqa: PLR0913  # one param per resolution input
    service: str,
    *,
    url: str | None,
    prefix: str | None,
    use_kubectl: bool,
    deployment: str | None,
    env: str | None,
    region: str,
) -> str:
    """Determine the full base URL for a deployed agent.

    Precedence:
      1. ``--prefix`` -> host + prefix (host defaults to port-forward localhost).
      2. ``--kubectl`` -> host + kubectl-detected prefix.
      3. Control plane -> resolve ``custom_url``; if ``--url`` host given, join
         host with ``custom_url`` path; else return ``custom_url`` as-is.
    """
    if prefix:
        host = (url or _DEFAULT_PORT_FORWARD_HOST).rstrip("/")
        normalized_prefix = prefix if prefix.startswith("/") else f"/{prefix}"
        return f"{host}{normalized_prefix}"
    if use_kubectl:
        return resolve_prefix_via_kubectl(url or _DEFAULT_PORT_FORWARD_HOST)
    custom_url = resolve_deployment_base_url(
        service, deployment=deployment, env=env, region=region
    )
    if url:
        joined = join_host_with_custom_url(url, custom_url)
        click.echo(f"  Using host: {joined}")
        return joined
    return custom_url
