"""Naming convention for LangSmith deployments and tracing projects.

Deployment naming is owned here and by ``langsmith-client deploy docker`` — deploy
shell scripts must not construct ``<service>-<env>`` strings or pass a pre-suffixed
name as ``--name``.

Three independent axes:

* **Service** — logical app identity (``[project].name`` in ``pyproject.toml``,
  or ``--name`` on the CLI). Example: ``hello-agent``.
* **Env** — deployment environment suffix (``--env``, then ``APP_ENV``, then
  ``dev``). Example: ``prod``.
* **Workspace** — LangSmith tenant (``LANGSMITH_WORKSPACE_ID`` + API key). Does
  not affect the deployment name. Example: a separate prod workspace.

The canonical deployment name is ``<service>-<env>`` — for example
``hello-agent-dev``. The same logical service deploys to that name over and over.

When the canonical name becomes stuck or orphaned and cannot be reclaimed, a git
short SHA is appended as a rescue suffix (``hello-agent-dev-3f9a2c``), with a
compact UTC time tiebreak if even that is taken. The SHA is decoration for
uniqueness only — deploys resolve by the stable canonical base and update by
deployment ID, so the rescue suffix never has to be known or matched.
"""

import os
import re
import subprocess  # nosec B404  # developer tooling shells out to git
from collections.abc import Iterable
from datetime import datetime, timezone

DEFAULT_ENV = "dev"

# Environment variable consulted when --env is not passed (12-factor style).
ENV_VAR = "APP_ENV"

_INVALID_CHARS = re.compile(r"[^a-zA-Z0-9_-]")


def sanitize_name_component(value: str) -> str:
    """Replace characters unsafe for LangSmith names with hyphens.

    Mirrors the sanitization used for Docker-derived names: anything outside
    ``[a-zA-Z0-9_-]`` becomes ``-``. Leading/trailing hyphens are trimmed.
    """
    cleaned = _INVALID_CHARS.sub("-", value.strip())
    return cleaned.strip("-")


def resolve_env(env: str | None = None) -> str:
    """Resolve the deployment environment.

    Precedence: explicit ``env`` argument, then the ``APP_ENV`` environment
    variable, then ``"dev"``.
    """
    resolved = env or os.environ.get(ENV_VAR) or DEFAULT_ENV
    return sanitize_name_component(resolved)


def compute_base_name(service: str, env: str | None = None) -> str:
    """Build the canonical ``<service>-<env>`` name.

    Args:
        service: Logical service name (typically ``[project].name``).
        env: Environment; resolved via :func:`resolve_env` when omitted.
    """
    return f"{sanitize_name_component(service)}-{resolve_env(env)}"


def resolve_deploy_base(
    *,
    deployment: str | None = None,
    service: str | None = None,
    env: str | None = None,
) -> str:
    """Return the deployment base name for create/upsert.

    When ``deployment`` is provided, it is sanitized and used as-is (no
    ``<service>-<env>`` construction). Otherwise builds the canonical name via
    :func:`compute_base_name`.
    """
    if deployment:
        cleaned = sanitize_name_component(deployment)
        if not cleaned:
            raise ValueError("deployment name is empty after sanitization")
        return cleaned
    if not service:
        raise ValueError("service is required when deployment is omitted")
    return compute_base_name(service, env)


def get_git_sha() -> str | None:
    """Return the short Git commit SHA, or None if unavailable."""
    try:
        result = subprocess.run(  # nosec B603 B607  # hardcoded git command with list args, no shell
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _rescue_candidates(
    base: str,
    git_sha: str | None,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Ordered rescue names to try when the canonical base is unavailable.

    Prefers a git-SHA suffix (traceable to the deploying commit); falls back to
    a compact UTC ``YYYYMMDD-HHMM`` stamp when no SHA is available, and adds an
    ``HHMM`` time tiebreak after the SHA for the rare same-commit collision.
    """
    moment = now or datetime.now(timezone.utc)
    if git_sha:
        sha = sanitize_name_component(git_sha)
        return [f"{base}-{sha}", f"{base}-{sha}-{moment:%H%M}"]
    stamp = f"{moment:%Y%m%d-%H%M}"
    return [f"{base}-{stamp}", f"{base}-{stamp}-{moment:%S}"]


def choose_deploy_name(
    base: str,
    taken: Iterable[str],
    git_sha: str | None = None,
    *,
    now: datetime | None = None,
) -> str:
    """Pick the name to create when no healthy deployment exists for ``base``.

    Returns the canonical ``base`` when it is free, otherwise the first
    available git-SHA rescue name. Raises ``RuntimeError`` if every candidate
    is already taken (extremely unlikely; signals manual cleanup is needed).

    Args:
        base: Canonical ``<service>-<env>`` name.
        taken: Names already in use for this base (stuck/orphaned siblings).
        git_sha: Short Git SHA used for the rescue suffix.
        now: Override for the current time (testing).
    """
    taken_set = set(taken)
    candidates = [base, *_rescue_candidates(base, git_sha, now=now)]
    for candidate in candidates:
        if candidate not in taken_set:
            return candidate
    raise RuntimeError(
        f"Could not find an available deployment name for base '{base}'. "
        f"Existing names: {sorted(taken_set)}. Clean up stuck deployments "
        "with 'langsmith-client projects delete --force'."
    )
