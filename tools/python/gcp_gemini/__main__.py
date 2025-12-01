"""A Google Cloud Python Pulumi program for Gemini 2.5 Flash-Lite access"""

import pulumi
import pulumi_gcp as gcp

MODEL_ID = "gemini-2.5-flash-lite"

# Get current project information
current = gcp.organizations.get_client_config()

# Get stack name for consistent naming
stack_name = pulumi.get_stack()

# Get configuration for resource naming and region
config = pulumi.Config()
sa_prefix = config.get("resource_prefix") or current.project
region = config.get("region") or "us-central1"
existing_sa_email = config.get("service_account_email")

# Enable required APIs for Vertex AI and Gemini
apis_to_enable = [
    "aiplatform.googleapis.com",  # Vertex AI API
    "ml.googleapis.com",  # Machine Learning API
    "storage.googleapis.com",  # Cloud Storage (often needed for ML workflows)
    # Generative Language API (for Google AI Studio). This is required to use ADC JSON files.
    "generativelanguage.googleapis.com",
]

enabled_apis = []
for api in apis_to_enable:
    enabled_api = gcp.projects.Service(
        f"enable-{api.replace('.', '-')}",
        service=api,
        disable_on_destroy=False,  # Keep APIs enabled even if stack is destroyed.
    )
    enabled_apis.append(enabled_api)

# Create or import a service account for Vertex AI access.
if existing_sa_email:
    # Use the provided service account email to determine the account ID
    # Format: account-id@project.iam.gserviceaccount.com
    sa_name, _, _ = existing_sa_email.partition("@")
    sa_email = existing_sa_email

    # Try to import the existing service account
    # The import ID format for service accounts is: projects/{project}/serviceAccounts/{email}
    service_account = gcp.serviceaccount.Account(
        sa_name,
        account_id=sa_name,
        display_name=f"{sa_prefix} Service Account (imported)",
        opts=pulumi.ResourceOptions(
            protect=True,  # Protect against deletion
            import_=f"projects/{current.project}/serviceAccounts/{sa_email}",
        ),
    )
else:
    # Create a new service account
    sa_name = sa_prefix
    sa_email = f"{sa_name}@{current.project}.iam.gserviceaccount.com"

    service_account = gcp.serviceaccount.Account(
        sa_name,
        account_id=sa_name,
        display_name=f"{sa_prefix} Service Account",
        opts=pulumi.ResourceOptions(
            protect=False,  # We created it, so we can destroy it
        ),
    )

# Grant necessary IAM roles to the service account
roles_to_grant = [
    "roles/aiplatform.user",  # Access Vertex AI services
    "roles/ml.developer",  # ML API access
    "roles/storage.objectAdmin",  # Storage access (if needed for data)
]

for role in roles_to_grant:
    # Create a meaningful name from the role by removing 'roles/' prefix and
    # replacing dots with dashes.
    role_suffix = role.replace("roles/", "").replace(".", "-")
    gcp.projects.IAMMember(
        f"gemini-sa-{role_suffix}",
        project=current.project,
        role=role,
        member=pulumi.Output.concat("serviceAccount:", service_account.email),
    )

# This bucket is needed to store any data, logs, or artifacts
# that your Gemini workflows may require. For example, you might upload input data,
# save model outputs, or share files between Vertex AI and your application.

# NOTE: Bucket location can be regional (lowercase like us-central1) or multi-regional (US, EU, ASIA).
# Default to US for multi-regional buckets.
BUCKET_LOCATION = "US"
gemini_bucket = gcp.storage.Bucket(
    "gemini-data-bucket",
    name=pulumi.Output.concat(current.project, "-gemini-data"),
    location=BUCKET_LOCATION,
    uniform_bucket_level_access=True,
    public_access_prevention="enforced",
    # Enable versioning for model artifacts
    versioning=gcp.storage.BucketVersioningArgs(enabled=True),
)

# Grant the service account access to the bucket
gcp.storage.BucketIAMMember(
    "gemini-bucket-access",
    bucket=gemini_bucket.name,
    role="roles/storage.objectAdmin",
    member=pulumi.Output.concat("serviceAccount:", service_account.email),
)

# Export important information
pulumi.export("project_id", current.project)
pulumi.export("gemini_service_account_email", service_account.email)
pulumi.export("data_bucket_name", gemini_bucket.name)

# Export example usage information
pulumi.export(
    "usage_info",
    {
        "model_id": MODEL_ID,
        "endpoint_base": f"https://{region}-aiplatform.googleapis.com",
        "location": region,
    },
)
