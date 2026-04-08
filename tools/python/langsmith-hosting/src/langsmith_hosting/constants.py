"""Shared constants for LangSmith Hosting infrastructure."""

from functools import lru_cache
from importlib.metadata import entry_points

PROJECT_NAME = "langsmith-hosting"

_BASE_TAGS: dict[str, str] = {
    "Project": PROJECT_NAME,
    "ManagedBy": "pulumi",
}


@lru_cache
def _build_tags(resource: str = "") -> dict[str, str]:
    global_tags: dict[str, str] = {}
    for ep in entry_points(group="langsmith_hosting.tags"):
        global_tags.update(ep.load())

    resource_tags: dict[str, str] = {}
    if resource:
        for ep in entry_points(group=f"langsmith_hosting.tags.{resource}"):
            resource_tags.update(ep.load())

    return {**_BASE_TAGS, **global_tags, **resource_tags}


def get_tags(resource: str = "") -> dict[str, str]:
    """Build the tag dict for a resource, merging base + plugin tags.

    Args:
        resource: Resource type key (e.g. "eks", "s3"). When empty,
            only base and global plugin tags are returned.

    Returns:
        Shallow copy of the cached tag dict (safe to mutate).
    """
    return dict(_build_tags(resource))
