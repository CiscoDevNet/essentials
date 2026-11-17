"""AWS Bedrock package for provisioning IAM access to Anthropic models with Pulumi.

Public API for composing AWS Bedrock stacks::

    from ess_aws_bedrock import deploy_stack
    result = deploy_stack()
"""

from ess_aws_bedrock.stack import StackOutputs, deploy_stack

__all__ = ["StackOutputs", "deploy_stack"]
