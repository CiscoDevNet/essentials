"""Azure AI OpenAI package for deploying GPT models with Pulumi.

Public API for composing Azure AI stacks::

    from azure_ai import deploy_stack
    result = deploy_stack(extra_ips=["44.207.191.116"])
"""

from azure_ai.stack import StackOutputs, deploy_stack

__all__ = ["StackOutputs", "deploy_stack"]
