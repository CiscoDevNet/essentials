---
description: LangSmith branding and naming conventions for resource names, comments, and docs
alwaysApply: true
---

# LangSmith Naming Convention

The LangChain company has rebranded around **LangSmith**. When choosing names for resources, variables, comments, or documentation:

- Use **"langsmith"** (or **"LangSmith"**) as the prefix/brand, not "langgraph".
- Drop prefixes entirely when the context already implies LangSmith (e.g., inside a `langsmith-hosting` package, use `dataplane` not `langsmith-dataplane`).

## What you CAN rename

- Pulumi resource names (`f"{cluster_name}-dataplane"`)
- Helm release names (`name="dataplane"`)
- Comments, docstrings, and documentation
- Variable names, constant names, file names

## What you CANNOT rename

Values that are API contracts controlled by upstream (LangChain's Helm repo, REST APIs):

- Helm chart names (`chart="langgraph-dataplane"` -- published chart name)
- Helm values schema keys (`"langgraphListenerId"` -- expected by the chart)
- API endpoint paths and request/response field names
- CRD names (`lgps.apps.langchain.ai`)

When an upstream contract uses "langgraph", keep it as-is and add a brief inline note if clarity helps.
