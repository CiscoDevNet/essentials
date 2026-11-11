"""AWS Bedrock deployment with Pulumi.

Creates the full AWS Bedrock stack:
  1. IAM user with Bedrock invoke permissions
  2. Scoped IAM policy for Anthropic foundation models
  3. Long-lived access keys for programmatic API access

This is the standalone entry-point. For deployments that need additional
IAM policy statements or a team-specific tag prefix, call
``ess_aws_bedrock.stack.deploy_stack`` from a team wrapper project.
"""

from ess_aws_bedrock.stack import deploy_stack

deploy_stack()
