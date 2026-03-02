# LangSmith AWS resources and costs

Here is what LangChain's BYOC provisions:

## ECS Cluster

**LangChain provisions ECS Fargate tasks** to run your LangGraph agents:

- Serverless compute (no EC2 instances to manage)
- CPU/memory sized per deployment (you configure this when creating the deployment)
- Tasks run in your tagged VPC subnets
- LangChain uses `AmazonECS_FullAccess` to create/update/delete these resources

You don't directly control the ECS task definition - LangChain's control plane creates it based on your deployment configuration (min/max scale, CPU, memory).

## RDS Database

**LangChain provisions an RDS PostgreSQL instance** for each deployment to store:

- Agent state (checkpoints, threads)
- Run history
- Persistent data

**Key point:** You can **skip RDS provisioning** by providing your own PostgreSQL:

```
POSTGRES_URI_CUSTOM=postgresql://<USER>:<PASSWORD>@<HOST>:5432/langgraph
```

This is useful if you:

- Want to control database sizing/costs
- Already have a PostgreSQL cluster
- Want to use Aurora Serverless instead of RDS

## Cost Implications

You pay AWS directly for:

- **ECS Fargate**: ~$0.04/vCPU-hour + ~$0.004/GB-hour
- **RDS**: Varies by instance type (db.t3.micro ~$15/mo, db.t3.small ~$30/mo)
- **Data transfer, CloudWatch logs, Secrets Manager**

Plus LangGraph Platform fees (Enterprise tier for BYOC).

---

**Recommendation:** If cost control matters, consider using `POSTGRES_URI_CUSTOM` with an existing database or Aurora Serverless rather than letting LangChain provision RDS instances per deployment.
