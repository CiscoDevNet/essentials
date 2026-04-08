# LangSmith Hosting

Pulumi project that provisions AWS infrastructure for LangSmith Hybrid.

## Resources

- **VPC** with public/private subnets across 3 availability zones
- **EKS** cluster with managed node group, EBS CSI driver, and GP3 storage class
- **RDS PostgreSQL** instance for LangSmith data
- **ElastiCache Redis** cluster for caching
- **S3 bucket** with VPC endpoint for blob storage

## Prerequisites

- AWS CLI configured with an appropriate profile
- [uv](https://docs.astral.sh/uv/) installed
- Pulumi CLI installed

## Quickstart

```bash
# From this directory
uv run pulumi login file://.
uv run pulumi stack select dev
uv run pulumi up
```

## Configuration

Stack configuration lives in `Pulumi.dev.yaml`. Key settings:

| Config Key | Description | Default |
|---|---|---|
| `environment` | Environment name | `dev` |
| `vpcCidr` | VPC CIDR block | `10.0.0.0/16` |
| `eksClusterName` | EKS cluster name | `langsmith-hybrid-dev` |
| `eksClusterVersion` | Kubernetes version | `1.31` |
| `eksNodeInstanceType` | EC2 instance type for nodes | `m5.large` |
| `postgresInstanceClass` | RDS instance class | `db.t3.medium` |
| `redisNodeType` | ElastiCache node type | `cache.t3.micro` |
| `s3BucketPrefix` | S3 bucket name prefix | `langsmith` |
| `extraPublicAccessCidrs` | Comma-separated CIDRs to add to the EKS API server allowlist | _(none)_ |
