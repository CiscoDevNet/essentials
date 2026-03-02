"""Naming utilities for Pulumi resources.

This module provides common functions for generating consistent resource names
across Pulumi projects, including stack-based suffixing and name joining.
"""

import pulumi

from .config import DEFAULT_SEPARATOR


def get_suffix() -> str:
    """
    Get the suffix for resources based on the stack name.

    For production stacks (those starting with "prod"), no suffix is added.
    For all other stacks, the stack name is used as a suffix.

    Returns:
        The suffix for resources (empty string for production, stack name otherwise).

    Examples:
        >>> # When stack is "dev"
        >>> get_suffix()
        'dev'

        >>> # When stack is "prod"
        >>> get_suffix()
        ''

        >>> # When stack is "staging"
        >>> get_suffix()
        'staging'
    """
    stack_name = pulumi.get_stack()
    return "" if stack_name.lower().startswith("prod") else stack_name


def get_resource_name(*parts: str, separator: str = DEFAULT_SEPARATOR) -> str:
    """
    Generate a resource name by joining parts and appending the stack suffix.

    This function creates consistent resource names across Pulumi projects by:
    1. Converting all parts to lowercase
    2. Adding the stack suffix (if not production)
    3. Joining parts with the specified separator
    4. Normalizing any default separators to the specified separator

    Args:
        *parts: The parts to join (e.g., project name, resource type).
        separator: The separator to use when joining parts (default: "-").

    Returns:
        The formatted resource name with suffix.

    Examples:
        >>> # In dev stack with default separator
        >>> get_resource_name("myapp", "postgres", "server")
        'myapp-postgres-server-dev'

        >>> # In prod stack
        >>> get_resource_name("myapp", "postgres", "server")
        'myapp-postgres-server'

        >>> # With custom separator
        >>> get_resource_name("myapp", "db", separator="_")
        'myapp_db_dev'

        >>> # Parts with existing separators are normalized
        >>> get_resource_name("my-app", "postgres-db", separator="_")
        'my_app_postgres_db_dev'
    """
    _parts = [part.lower() for part in parts] + [get_suffix()]

    # Remove any default separators and join with the given separator.
    return separator.join(_parts).replace(DEFAULT_SEPARATOR, separator)
