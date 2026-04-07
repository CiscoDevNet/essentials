"""S3 resources for LangSmith Hosting infrastructure.

Creates an S3 bucket with a VPC gateway endpoint and a bucket policy
restricting access through the endpoint, matching the Terraform module.s3
configuration.
"""

import json
import logging
from dataclasses import dataclass
from http import HTTPStatus

import boto3
import pulumi
import pulumi_aws as aws
from botocore.exceptions import ClientError

from langsmith_hosting.constants import get_tags

logger = logging.getLogger(__name__)


def _bucket_exists(name: str) -> bool:
    """Check if an S3 bucket exists and is owned by this account.

    Used to decide whether Pulumi should import an existing bucket into
    state or create a new one (adopt-or-create pattern).

    A 403 (e.g. from a VPC endpoint policy) still means the bucket
    exists — only a 404 confirms it does not.
    """
    try:
        boto3.client("s3").head_bucket(Bucket=name)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code == str(HTTPStatus.NOT_FOUND):
            return False
        return True


@dataclass
class S3Outputs:
    """Outputs from the S3 module."""

    bucket_name: pulumi.Output[str]
    bucket_arn: pulumi.Output[str]
    vpc_endpoint_id: pulumi.Output[str]


def create_s3(
    bucket_name: str,
    vpc_id: pulumi.Output[str],
    region: str,
) -> S3Outputs:
    """Create an S3 bucket with VPC endpoint for LangSmith blob storage.

    Args:
        bucket_name: Full bucket name (e.g. "langsmith-dev-123456789012").
        vpc_id: VPC ID for the gateway endpoint.
        region: AWS region for the VPC endpoint service.

    Returns:
        S3Outputs with bucket and endpoint details.
    """
    tags = get_tags("s3")
    # =========================================================================
    # S3 bucket
    # =========================================================================
    if _bucket_exists(bucket_name):
        logger.info("Bucket %s already exists; importing into state", bucket_name)
        bucket_opts = pulumi.ResourceOptions(import_=bucket_name)
    else:
        bucket_opts = None

    bucket = aws.s3.Bucket(
        bucket_name,
        bucket=bucket_name,
        tags={**tags, "Name": bucket_name},
        opts=bucket_opts,
    )

    # Block all public access
    aws.s3.BucketPublicAccessBlock(
        f"{bucket_name}-public-access-block",
        bucket=bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True,
    )

    # Enable server-side encryption
    aws.s3.BucketServerSideEncryptionConfiguration(
        f"{bucket_name}-encryption",
        bucket=bucket.id,
        rules=[
            aws.s3.BucketServerSideEncryptionConfigurationRuleArgs(
                apply_server_side_encryption_by_default=(
                    aws.s3.BucketServerSideEncryptionConfigurationRuleApplyServerSideEncryptionByDefaultArgs(
                        sse_algorithm="AES256",
                    )
                ),
            )
        ],
    )

    # =========================================================================
    # VPC gateway endpoint for S3
    # =========================================================================
    # Get the main route table for the VPC
    route_tables = aws.ec2.get_route_tables_output(
        filters=[
            aws.ec2.GetRouteTablesFilterArgs(
                name="vpc-id",
                values=[vpc_id],
            )
        ],
    )

    vpc_endpoint = aws.ec2.VpcEndpoint(
        f"{bucket_name}-vpc-endpoint",
        vpc_id=vpc_id,
        service_name=f"com.amazonaws.{region}.s3",
        vpc_endpoint_type="Gateway",
        route_table_ids=route_tables.ids,
        tags={**tags, "Name": f"{bucket_name}-s3-endpoint"},
    )

    # =========================================================================
    # Bucket policy restricting access to VPC endpoint
    # =========================================================================
    # Deny data-plane operations only when not using the VPC endpoint.
    # Management operations (GetBucketPolicy, PutBucketPolicy, etc.) are
    # intentionally excluded so that admin tooling (e.g. Pulumi, AWS CLI) can
    # still manage the bucket from outside the VPC without being locked out.
    data_plane_actions = (
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:GetObjectTagging",
        "s3:PutObject",
        "s3:PutObjectTagging",
        "s3:DeleteObject",
        "s3:DeleteObjectVersion",
        "s3:ListBucket",
        "s3:ListBucketVersions",
        "s3:ListBucketMultipartUploads",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts",
        "s3:RestoreObject",
    )

    bucket_policy_doc = pulumi.Output.all(bucket.arn, vpc_endpoint.id).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "RestrictDataAccessToVpcEndpoint",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": data_plane_actions,
                        "Resource": [
                            args[0],
                            f"{args[0]}/*",
                        ],
                        "Condition": {
                            "StringNotEquals": {
                                "aws:sourceVpce": args[1],
                            },
                        },
                    },
                ],
            }
        )
    )

    aws.s3.BucketPolicy(
        f"{bucket_name}-policy",
        bucket=bucket.id,
        policy=bucket_policy_doc,
    )

    return S3Outputs(
        bucket_name=bucket.bucket,
        bucket_arn=bucket.arn,
        vpc_endpoint_id=vpc_endpoint.id,
    )
