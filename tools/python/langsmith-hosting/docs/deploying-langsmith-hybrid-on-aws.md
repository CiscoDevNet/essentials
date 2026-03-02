# Deploying LangSmith Hybrid on AWS EKS: A Practitioner's Guide

*February 2026*

This post documents the end-to-end journey of deploying LangSmith Hybrid on
AWS EKS, building custom tooling around it, and debugging every failure along
the way. It is written as a practical reference for anyone repeating this
work -- whether a person or an automated agent.

---

## Background

Our team needed a way to run LLM agents in production on our own
infrastructure while keeping the LangSmith control plane managed by
LangChain. LangSmith Hybrid gives you exactly this: the control plane
(UI, tracing, deployment management) lives in LangChain's cloud, while
the **data plane** (the actual agent pods, Redis, and supporting services)
runs in your own Kubernetes cluster.

The project started as a Terraform deployment, evolved into a Pulumi-managed
stack, and grew to include a custom Python CLI for building, pushing, and
deploying agent images.

**Assumption:** The agents in this guide use Azure OpenAI for chat model
inference. The `azure-ai` Pulumi package provisions the Azure OpenAI
account, model deployment, and firewall rules. If you use a different LLM
provider, Phase 4 and the Azure-specific firewall steps won't apply, but
the rest of the guide (EKS infrastructure, build tooling, debugging) is
provider-agnostic.

---

## Phase 1: Terraform Foundation

We started with a pure Terraform approach using LangChain's official modules
from `github.com/langchain-ai/terraform`:

| Component   | Module                  | Purpose                               |
|-------------|-------------------------|---------------------------------------|
| VPC         | `modules/aws/vpc`       | Public/private subnets, NAT gateway   |
| EKS         | `modules/aws/eks`       | Kubernetes cluster                    |
| PostgreSQL  | `modules/aws/postgres`  | RDS database                          |
| Redis       | `modules/aws/redis`     | ElastiCache                           |
| S3          | `modules/aws/s3`        | Object storage with VPC endpoint      |

Terraform taught us the shape of the infrastructure, but we hit friction
immediately:

- **Module variable mismatches.** LangChain modules use different variable
  names than standard Terraform AWS modules (e.g., `instance_class` vs.
  `instance_type`). We had to inspect each module's `variables.tf` manually.
- **Circular dependencies.** Root-level Kubernetes/Helm providers created a
  cycle with the EKS module. The EKS module manages its own providers
  internally -- you have to let it.
- **Orphaned resources.** Failed deployments left behind KMS aliases,
  CloudWatch log groups, RDS subnet groups, ElastiCache subnet groups, and S3
  buckets that conflicted with fresh runs.
- **SSO timeouts.** EKS deployments take 15-20 minutes, often outlasting the
  AWS SSO session.

We built shell scripts (`deploy.sh`, `list-aws-resources.sh`,
`destroy-aws-resources.sh`) to manage targeted applies and dependency-ordered
destroys, but the Terraform workflow remained brittle for our use case.

---

## Phase 2: Migrating to Pulumi

We moved the infrastructure to Pulumi (Python) to get first-class
programmability and to share configuration logic with the rest of the
monorepo. The Pulumi stack lives in `tools/python/langsmith-hosting/` and
provisions:

1. **VPC** with public and private subnets and a NAT gateway
2. **EKS cluster** with managed node groups, Pod Identity, EBS CSI driver,
   cluster autoscaler, and an AWS Load Balancer Controller
3. **S3 bucket** for LangSmith blob storage
4. **RDS PostgreSQL** instance
5. **ElastiCache Redis** cluster
6. **Data plane** (KEDA + the `langgraph-dataplane` Helm chart)

### Configuration as code

Rather than duplicating values across `Pulumi.dev.yaml` and Python, we
extracted sensible defaults into module-level constants in `config.py`:

```python
_VPC_CIDR = "10.0.0.0/16"
_EKS_CLUSTER_VERSION = "1.31"
_EKS_NODE_INSTANCE_TYPE = "m5.xlarge"
_POSTGRES_INSTANCE_CLASS = "db.t3.medium"
_REDIS_NODE_TYPE = "cache.t3.micro"
```

The stack config file shrank from 16 keys to 5 essentials: `environment`,
`eksClusterName`, `s3BucketPrefix`, `langsmithWorkspaceId`, and
`langsmithApiKey`. Everything else uses the Python defaults unless
explicitly overridden.

### Listener as a dynamic resource

The LangSmith Hybrid data plane requires a **listener** registered with the
control plane API. We built a Pulumi dynamic resource (`LangSmithListener`)
that calls the LangSmith API to create, read, and delete listeners as part
of `pulumi up` / `pulumi destroy`. This eliminated the manual
`manage_listeners.py` step from the Terraform era.

### Dataplane Helm release

The data plane itself is a single Helm release (`langgraph-dataplane`) that
installs the listener agent, operator, and a Redis StatefulSet. The Helm
values are wired to Pulumi outputs (API key, workspace ID, listener ID) so
everything stays in sync:

```python
k8s.helm.v3.Release(
    f"{cluster_name}-dataplane",
    name="dataplane",
    chart="langgraph-dataplane",
    values={
        "config": {
            "langsmithApiKey": langsmith_api_key,
            "langgraphListenerId": listener.listener_id,
            "enableLGPDeploymentHealthCheck": _ENABLE_HEALTH_CHECK,
        },
        ...
    },
    opts=pulumi.ResourceOptions(depends_on=[keda, listener]),
)
```

---

## Phase 3: Build and Deploy Tooling

We created a Python CLI package (`langsmith-client`) that wraps the
build-push-deploy cycle into repeatable commands.

### `langsmith-build`

Builds a Docker image using `langgraph build` with an auto-generated tag
derived from `pyproject.toml`. The key insight was appending the **Git SHA**
to every image tag:

```
hello-world-graph:0.1.0-ff95149
```

This solved a persistent Kubernetes caching problem. With a static tag like
`hello-world-graph:0.1.0`, the default `imagePullPolicy: IfNotPresent`
caused nodes to skip pulling the updated image. Unique tags forced a fresh
pull on every deployment.

The implementation is a small private helper in `build.py`:

```python
def _get_git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
```

If Git is unavailable (e.g., inside a CI container without the repo), it
falls back to `name:version`.

### `langsmith-deploy-docker`

Creates or updates a deployment through the LangSmith API, specifying the
ECR image URI, environment variables (Azure OpenAI secrets), and the target
listener. This replaced manual deployments through the LangSmith UI.

---

## Phase 4: Azure OpenAI Integration

The agent uses Azure OpenAI (`gpt-5.1-chat`) via `AzureChatOpenAI` from
LangChain. Getting this to work from inside EKS required solving two
distinct problems.

### Problem: 403 Forbidden from Azure

Azure OpenAI has Virtual Network / firewall restrictions. The EKS cluster's
outbound traffic exits through a NAT gateway, and that IP was not in the
Azure allowlist.

**Diagnosis:**

```bash
kubectl exec <pod-name> -- \
  python3 -c "from urllib.request import urlopen; print(urlopen('https://ifconfig.me').read().decode())"
```

**Fix:** Add the NAT gateway's public IP to the Azure OpenAI resource's
firewall rules. We later automated this with the `azure-ai` Pulumi package
(`packages/python/azure-ai/`) that manages the Azure OpenAI resource and
its firewall rules, accepting NAT IPs as input from the hosting stack.

### Problem: Temperature incompatibility

`gpt-5.1-chat` only accepts `temperature=1`. LangChain's `create_agent`
internally binds `temperature=0` for deterministic behavior, which the model
silently rejects. The symptom was an `httpx.UnsupportedProtocol` error in
the health check -- deeply misleading, because the real error was buried in
the Azure API response.

**Fix:**

```python
model = AzureChatOpenAI(
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    temperature=1,
)
```

---

## Phase 5: Debugging in Production

Every deployment revealed a new class of failure. Here are the ones that
cost the most time.

### Stale images on Kubernetes nodes

**Symptom:** Deployment succeeds, pod is `Running`, but runs old code.

**Root cause:** Same image tag + `imagePullPolicy: IfNotPresent` = cached
stale image.

**Fix:** Git SHA in every tag (see Phase 3).

### Port-forward dies on pod restart

**Symptom:** `error: lost connection to pod` after deploying a new revision.

**Root cause:** Port-forward targets a specific pod. When LangSmith replaces
the pod with a new revision, the old pod is terminated.

**Fix:** Port-forward via the Kubernetes *service* instead:

```bash
lsof -ti :8000 | xargs kill -9 2>/dev/null
kubectl port-forward svc/<service-name> 8000:8000
```

The service routes to whichever pods are currently healthy.

### 404 Not Found from the LangGraph SDK

**Symptom:** `langgraph_sdk.errors.NotFoundError: 404 Not Found`

**Root cause:** The agent API lives under a mount prefix
(`/lgp/<deployment-hash>/`). A stale port-forward or wrong prefix causes
every API call to 404.

**Fix:** Query the pod's `MOUNT_PREFIX` environment variable:

```bash
kubectl get pod <pod-name> \
  -o jsonpath='{range .spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}' \
  | grep MOUNT
```

Then pass that prefix to the SDK client.

### Health check fails with `httpx.UnsupportedProtocol`

**Symptom:** The LangSmith UI shows deployment failure with a protocol error.

**Root cause:** The dataplane constructs a health check URL from the
`ingress.hostname` Helm value. Without a hostname, the URL has no scheme.

**Fix (workaround):** Disable health checks until an ingress is configured:

```python
_ENABLE_HEALTH_CHECK = False
```

**Fix (permanent):** Configure the ingress hostname so the health check URL
is well-formed.

---

## Phase 6: Refactoring for Maintainability

With the infrastructure working, we cleaned up the codebase:

- **Extracted constants.** Moved 11 infrastructure defaults from YAML config
  into Python module-level constants. The stack config file shrank to only
  the values that are genuinely environment-specific.
- **Shortened resource names.** Renamed `langgraph-dataplane` to `dataplane`
  throughout, aligning with the LangSmith branding.
- **Shared packages.** `azure-ai` lives in `packages/python/azure-ai/` as a
  composable library that other stacks can import via `deploy_stack(extra_ips=...)`.
- **Organized IAM policies.** Moved inline policy dicts (like the cluster
  autoscaler policy) to module-level constants for readability.
- **Created a kubectl runbook.** Documented every production debugging
  session into a structured runbook with copy-paste commands, organized by
  problem and solution.

---

## Architecture Summary

```
tools/python/
├── langsmith-hosting/   # Pulumi: VPC, EKS, S3, RDS, Redis, dataplane
└── pulumi-utils/        # Shared Pulumi naming helpers

packages/python/
├── azure-ai/            # Pulumi: Azure OpenAI account, model, firewall
└── langsmith-client/    # CLI: build, deploy, list workspaces/listeners
```

The data flow:

1. `langsmith-build` reads `pyproject.toml`, appends the Git SHA, and runs
   `langgraph build` to produce a Docker image.
2. The image is tagged and pushed to ECR.
3. `langsmith-deploy-docker` calls the LangSmith API to create/update a
   deployment, specifying the ECR image URI and environment secrets.
4. The LangSmith control plane tells the dataplane listener in the EKS
   cluster to pull the image and create pods.
5. The agent pods run, connecting to Azure OpenAI through the NAT gateway.

---

## Lessons Learned

1. **Tag images uniquely.** Never reuse the same tag for different builds.
   Git SHAs are free and make debugging trivial.

2. **Port-forward to services, not pods.** Pods are ephemeral. Services
   survive restarts.

3. **Errors lie.** `httpx.UnsupportedProtocol` was really a temperature
   validation failure three layers deep. Always check pod logs before
   trusting error messages.

4. **Extract defaults into code.** YAML config files should contain only
   what varies between environments. Everything else belongs in typed Python
   constants with clear names and comments.

5. **Automate the listener lifecycle.** Managing listeners manually was a
   constant source of drift. Making it a Pulumi dynamic resource eliminated
   an entire class of errors.

6. **Document while debugging.** The kubectl runbook we wrote during
   production incidents has already saved hours. Debugging commands are
   worth more than architecture diagrams.

7. **Model APIs have quirks.** `gpt-5.1-chat` rejecting `temperature=0` is
   not documented anywhere obvious. When an agent fails in production, check
   the model's parameter constraints first.

8. **Firewall rules follow the NAT.** If your cluster uses a NAT gateway,
   every external API with IP restrictions needs that NAT IP in its
   allowlist. Export it as a stack output and wire it into downstream stacks.

---

## What's Next

- **Ingress hostname and TLS.** Configure a DNS record pointing to the ALB
  so the health check works and LangSmith Studio can reach the agent
  directly.
- **CI/CD pipeline.** Automate the build-push-deploy cycle so agents deploy
  on merge to main.
- **Tracing project management.** Build a utility to clean up stale LangSmith
  tracing projects.
- **Production stack.** Stand up a second environment with stricter IAM,
  larger nodes, and multi-AZ RDS.

---

## References

- [LangSmith Hybrid Deployment Docs](https://docs.langchain.com/langsmith/deploy-with-control-plane)
- [LangSmith Troubleshooting (Kubernetes)](https://docs.langchain.com/langsmith/troubleshooting#kubernetes)
- [Architecture](architecture.md) -- infrastructure overview
