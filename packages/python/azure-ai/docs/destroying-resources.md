# Destroying Azure OpenAI Resources

This guide explains how to safely destroy Azure OpenAI resources managed by Pulumi, including how to handle the **protect flag** that prevents accidental deletion.

## Understanding Resource Protection

When resources are **imported** into Pulumi (rather than created fresh), they are automatically marked as **protected**. This is a safety feature to prevent accidental deletion of existing infrastructure.

### What is the Protect Flag?

The protect flag is a Pulumi feature that:

- Prevents `pulumi destroy` from deleting protected resources
- Is automatically applied to imported resources
- Must be explicitly removed before destruction can occur

### Why Resources Are Protected

When you import existing Azure resources into Pulumi, the system assumes:

1. These resources were created outside of Pulumi
2. They may be critical production resources
3. Accidental deletion could cause significant problems

Therefore, Pulumi protects them by default until you explicitly indicate you want to manage their lifecycle.

## Checking Resource Protection Status

Before attempting to destroy resources, check if they're protected:

```bash
cd tools/python/azure-ai
export PULUMI_CONFIG_PASSPHRASE="your-passphrase"
pulumi preview
```

If resources are protected, you'll see output like:

```
~  azure-native:resources:ResourceGroup openai-resource-group [diff: ~protect]
~  azure-native:cognitiveservices:Account openai-account [diff: ~protect]
```

The `[diff: ~protect]` indicates the protect flag is set.

You can also check the resource state directly:

```bash
pulumi stack --show-urns
```

## Removing Protection

To remove the protect flag, you need to update your Pulumi code to explicitly set `protect=False` on each resource, then run `pulumi up`.

### Method 1: Update Code (Recommended)

Edit `__main__.py` and add `opts=pulumi.ResourceOptions(protect=False)` to each resource:

```python
# Resource Group
resource_group = azure_native.resources.ResourceGroup(
    "openai-resource-group",
    resource_group_name=resource_group_name,
    location=location,
    opts=pulumi.ResourceOptions(protect=False)  # Add this line
)

# OpenAI Account
openai_account = azure_native.cognitiveservices.Account(
    "openai-account",
    account_name=account_name,
    resource_group_name=resource_group.name,
    location=location,
    kind="OpenAI",
    sku=azure_native.cognitiveservices.SkuArgs(name="S0"),
    properties=azure_native.cognitiveservices.AccountPropertiesArgs(**account_properties),
    opts=pulumi.ResourceOptions(protect=False)  # Add this line
)

# Deployment
model_deployment = azure_native.cognitiveservices.Deployment(
    "gpt5chat-deployment",
    deployment_name=deployment_name,
    resource_group_name=resource_group.name,
    account_name=openai_account.name,
    properties=azure_native.cognitiveservices.DeploymentPropertiesArgs(
        model=azure_native.cognitiveservices.DeploymentModelArgs(**model_args),
    ),
    sku=azure_native.cognitiveservices.SkuArgs(
        name="GlobalStandard",
        capacity=capacity,
    ),
    opts=pulumi.ResourceOptions(protect=False)  # Add this line
)
```

Then apply the change:

```bash
pulumi up
```

This will update the resources to remove protection without making any changes to the actual Azure resources.

### Method 2: Using Pulumi CLI (Alternative)

You can also use the Pulumi CLI to unprotect resources without modifying code:

```bash
# Unprotect all resources in the stack
pulumi state unprotect --all

# Or unprotect specific resources
pulumi state unprotect "urn:pulumi:dev::azure-ai::azure-native:resources:ResourceGroup::openai-resource-group"
pulumi state unprotect "urn:pulumi:dev::azure-ai::azure-native:cognitiveservices:Account::openai-account"
pulumi state unprotect "urn:pulumi:dev::azure-ai::azure-native:cognitiveservices:Deployment::gpt5chat-deployment"
```

To get the exact URNs, use:

```bash
pulumi stack --show-urns
```

## Destroying Resources

Once protection is removed, you can destroy the resources:

### Step 1: Verify Resources Are Unprotected

```bash
pulumi preview
```

You should **not** see `[diff: ~protect]` in the output. If you do, the resources are still protected.

### Step 2: Destroy the Stack

```bash
pulumi destroy
```

Pulumi will show you a preview of what will be deleted:

```
Previewing destroy (dev):
     Type                                          Name                   Plan
 -   pulumi:pulumi:Stack                           azure-ai-dev           delete
 -   ├─ azure-native:cognitiveservices:Deployment  gpt5chat-deployment    delete
 -   ├─ azure-native:cognitiveservices:Account     openai-account         delete
 -   └─ azure-native:resources:ResourceGroup       openai-resource-group  delete

Resources:
    - 4 to delete
```

Review the plan carefully, then confirm the destruction.

### Step 3: Confirm Destruction

Type `yes` when prompted. The resources will be deleted in this order:

1. **Model Deployment** - The GPT-5 deployment
2. **OpenAI Account** - The Cognitive Services account
3. **Resource Group** - The resource group (and any remaining resources)

**Warning**: This action is **irreversible**. Once destroyed, you cannot recover:

- API keys
- Deployment configurations
- Any data or models associated with the account

## Complete Example Workflow

Here's a complete example of destroying protected resources:

```bash
# 1. Navigate to the project directory
cd tools/python/azure-ai

# 2. Set your passphrase (if using encrypted secrets)
export PULUMI_CONFIG_PASSPHRASE="your-passphrase"

# 3. Check current protection status
pulumi preview

# 4. Remove protection using CLI (or update code as shown above)
pulumi state unprotect --all

# 5. Verify protection is removed
pulumi preview

# 6. Destroy the resources
pulumi destroy

# 7. Confirm when prompted
yes
```

## Troubleshooting

### Error: "Cannot delete protected resource"

**Problem**: You tried to destroy resources that are still protected.

**Solution**: Remove protection first using one of the methods above, then try destroying again.

### Error: "Resource is locked"

**Problem**: Azure has a lock on the resource (separate from Pulumi's protect flag).

**Solution**: Remove Azure resource locks in the Azure Portal or using Azure CLI:

```bash
az lock delete --name <lock-name> --resource-group <resource-group-name>
```

### Resources Not Appearing in Destroy Preview

**Problem**: Resources might not be in the Pulumi state.

**Solution**: Verify resources are tracked:

```bash
pulumi stack --show-urns
```

If resources are missing, you may need to re-import them or they may have been deleted outside of Pulumi.

## Best Practices

1. **Always check protection status** before attempting to destroy
2. **Use `pulumi preview`** to see what will be deleted before confirming
3. **Backup important data** before destroying production resources
4. **Remove protection explicitly** rather than relying on defaults
5. **Document your destroy process** for team members

## Related Documentation

- [Pulumi Resource Protection](https://www.pulumi.com/docs/concepts/resources/options/protect/)
- [Pulumi Destroy Command](https://www.pulumi.com/docs/cli/commands/pulumi_destroy/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/overview)
