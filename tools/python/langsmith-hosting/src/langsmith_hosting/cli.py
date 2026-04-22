"""LangSmith Hosting CLI utilities.

Quick-access commands for inspecting deployed agents on the EKS cluster.
Requires ``kubectl`` configured for the target cluster.
"""

import json as json_mod
import subprocess  # nosec B404  # developer tooling shells out to kubectl

import click

_INGRESS_NAME = "dataplane-langgraph-dataplane-ingress"
_DEFAULT_NAMESPACE = "default"


def _kubectl_json(*args: str, namespace: str = _DEFAULT_NAMESPACE) -> dict:
    """Run a kubectl command and return parsed JSON output."""
    result = subprocess.run(  # nosec B603 B607
        ["kubectl", "-n", namespace, *args, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or "kubectl failed")
    return json_mod.loads(result.stdout)


def _detect_scheme(data: dict) -> str:
    """Return 'https' if the ingress has an HTTPS listener, else 'http'."""
    annotations = data.get("metadata", {}).get("annotations", {})
    listen_ports = annotations.get("alb.ingress.kubernetes.io/listen-ports", "")
    if "HTTPS" in listen_ports:
        return "https"
    return "http"


def _get_ingress_data(namespace: str) -> dict:
    """Get the full ingress resource."""
    return _kubectl_json("get", "ingress", _INGRESS_NAME, namespace=namespace)


def _get_alb_hostname(data: dict) -> str:
    """Get the ALB hostname from ingress data."""
    ingresses = data.get("status", {}).get("loadBalancer", {}).get("ingress", [])
    if not ingresses or not ingresses[0].get("hostname"):
        raise click.ClickException(
            "ALB not provisioned. Check that the ingress has ALB annotations."
        )
    return ingresses[0]["hostname"]


def _get_agent_paths(data: dict) -> list[dict[str, str]]:
    """Get agent paths from the ingress rules."""
    agents = []
    for rule in data.get("spec", {}).get("rules", []):
        for path in rule.get("http", {}).get("paths", []):
            p = path.get("path", "")
            if not p.startswith("/lgp/"):
                continue
            service = path.get("backend", {}).get("service", {}).get("name", "unknown")
            agents.append({"path": p, "service": service})
    return agents


@click.group()
@click.option(
    "-n",
    "--namespace",
    default=_DEFAULT_NAMESPACE,
    show_default=True,
    help="Kubernetes namespace for the dataplane ingress.",
)
@click.pass_context
def cli(ctx: click.Context, namespace: str):
    """LangSmith Hosting utilities."""
    ctx.ensure_object(dict)
    ctx.obj["namespace"] = namespace


@cli.command()
@click.pass_context
def ingress(ctx: click.Context):
    """Print the ALB hostname for the shared dataplane ingress."""
    data = _get_ingress_data(ctx.obj["namespace"])
    click.echo(_get_alb_hostname(data))


@cli.command()
@click.pass_context
def alb(ctx: click.Context):
    """Print the ALB hostname (alias for ``ingress``)."""
    data = _get_ingress_data(ctx.obj["namespace"])
    click.echo(_get_alb_hostname(data))


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def endpoints(ctx: click.Context, as_json: bool):
    """List agent endpoints on the shared ALB."""
    data = _get_ingress_data(ctx.obj["namespace"])
    hostname = _get_alb_hostname(data)
    scheme = _detect_scheme(data)
    agents = _get_agent_paths(data)

    if not agents:
        raise click.ClickException("No agents found on the ingress.")

    if as_json:
        out = [
            {
                "service": a["service"],
                "url": f"{scheme}://{hostname}{a['path']}",
                "path": a["path"],
            }
            for a in agents
        ]
        click.echo(json_mod.dumps(out, indent=2))
        return

    click.echo(f"ALB: {hostname}\n")
    for a in agents:
        url = f"{scheme}://{hostname}{a['path']}"
        click.echo(f"  {a['service']}")
        click.echo(f"    {url}")
        click.echo()
