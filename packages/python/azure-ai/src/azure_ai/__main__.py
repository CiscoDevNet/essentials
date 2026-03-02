"""Azure OpenAI deployment with Pulumi.

Creates the full Azure OpenAI stack:
  1. Resource group with network ACLs
  2. Cognitive Services account (OpenAI)
  3. GPT model deployment
  4. Tag-enforcement policies at the subscription scope

This is the standalone entry-point. For deployments that need additional
firewall IPs (e.g. from an AWS NAT Gateway), see ``azure_ai.stack.deploy_stack``.
"""

from azure_ai.stack import deploy_stack

deploy_stack()
