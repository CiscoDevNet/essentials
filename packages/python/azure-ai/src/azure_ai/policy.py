"""Azure Policy assignments for tag enforcement.

Assigns built-in "Require a tag" policies at the subscription scope so that
every resource and resource group must carry the required kebab-case,
lowercase tags (e.g. ``managed-by``, ``environment``).
"""

from dataclasses import dataclass

import pulumi
import pulumi_azure_native as azure_native

REQUIRE_TAG_ON_RESOURCES = (
    "/providers/Microsoft.Authorization"
    "/policyDefinitions/871b6d14-10aa-478d-b590-94f262ecfa99"
)
REQUIRE_TAG_ON_RESOURCE_GROUPS = (
    "/providers/Microsoft.Authorization"
    "/policyDefinitions/96670d01-0a4d-4649-9c89-2d3abc0a5025"
)


@dataclass
class PolicyOutputs:
    """Outputs from the tag-policy module."""

    resource_policy_names: list[pulumi.Output[str]]
    resource_group_policy_names: list[pulumi.Output[str]]


def create_tag_policies(
    subscription_id: str,
    required_tags: list[str],
) -> PolicyOutputs:
    """Create policy assignments that require tags on all resources.

    Assigns the built-in "Require a tag on resources" and "Require a tag on
    resource groups" policies at the subscription scope for each tag name in
    *required_tags*.

    Args:
        subscription_id: Azure subscription ID to scope the policies to.
        required_tags: Tag names to require (e.g. ["managed-by", "environment"]).

    Returns:
        PolicyOutputs with the names of all created assignments.
    """
    scope = f"/subscriptions/{subscription_id}"
    resource_names: list[pulumi.Output[str]] = []
    rg_names: list[pulumi.Output[str]] = []

    for tag_name in required_tags:
        slug = tag_name.replace(" ", "-").lower()

        resource_assignment = azure_native.authorization.PolicyAssignment(
            f"require-tag-{slug}-on-resources",
            policy_assignment_name=f"require-{slug}-on-resources",
            scope=scope,
            policy_definition_id=REQUIRE_TAG_ON_RESOURCES,
            display_name=f"Require '{tag_name}' tag on resources",
            description=(
                f"Denies creation of resources that do not have the "
                f"'{tag_name}' tag. Tags must be kebab-case and lowercase."
            ),
            enforcement_mode=azure_native.authorization.EnforcementMode.DEFAULT,
            parameters={
                "tagName": azure_native.authorization.ParameterValuesValueArgs(
                    value=tag_name,
                ),
            },
            non_compliance_messages=[
                azure_native.authorization.NonComplianceMessageArgs(
                    message=(
                        f"Resource is missing the required '{tag_name}' tag. "
                        f"All tags must be kebab-case and lowercase."
                    ),
                ),
            ],
        )

        rg_assignment = azure_native.authorization.PolicyAssignment(
            f"require-tag-{slug}-on-rgs",
            policy_assignment_name=f"require-{slug}-on-rgs",
            scope=scope,
            policy_definition_id=REQUIRE_TAG_ON_RESOURCE_GROUPS,
            display_name=f"Require '{tag_name}' tag on resource groups",
            description=(
                f"Denies creation of resource groups that do not have the "
                f"'{tag_name}' tag. Tags must be kebab-case and lowercase."
            ),
            enforcement_mode=azure_native.authorization.EnforcementMode.DEFAULT,
            parameters={
                "tagName": azure_native.authorization.ParameterValuesValueArgs(
                    value=tag_name,
                ),
            },
            non_compliance_messages=[
                azure_native.authorization.NonComplianceMessageArgs(
                    message=(
                        f"Resource group is missing the required '{tag_name}' "
                        f"tag. All tags must be kebab-case and lowercase."
                    ),
                ),
            ],
        )

        resource_names.append(resource_assignment.name)
        rg_names.append(rg_assignment.name)

    return PolicyOutputs(
        resource_policy_names=resource_names,
        resource_group_policy_names=rg_names,
    )
