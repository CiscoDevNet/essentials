# Gemini 2.0 Flash with Pulumi GCP

This project sets up the necessary Google Cloud infrastructure to work with Gemini 2.0 Flash through Vertex AI using Pulumi.

## Overview

Unlike traditional infrastructure resources (like storage buckets), Gemini 2.0 Flash is a **managed AI service** provided by Google through Vertex AI. You don't deploy the model itself as infrastructure, but rather:

1. **Set up the required infrastructure** (APIs, service accounts, permissions)
2. **Access the model through Vertex AI APIs** in your application code

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your App      │───▶│  Vertex AI API   │───▶│ Gemini 2.0 Flash│
│                 │    │                  │    │   (Managed)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│ Service Account │    │   GCS Bucket     │
│ (Pulumi created)│    │ (for data/logs)  │
└─────────────────┘    └──────────────────┘
```

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Pulumi CLI** installed
3. **Google Cloud SDK** installed and configured
4. **Python 3.8+**

## ⚠️ Security Note

This repository does **NOT** include:

- Stack configuration files (`Pulumi.*.yaml`) - These contain project-specific settings
- Service account keys (`key.json`, `*.pem`) - These contain sensitive credentials
- Environment files (`.env`) - These may contain secrets

These files are in `.gitignore` and must be created by each user for their own GCP project.

## Setup Instructions

### 1. Install Dependencies

```bash
cd tools/python/gcp_gemini
pip install -r requirements.txt
```

### 2. Configure Google Cloud Authentication

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID
```

### 3. Initialize Pulumi Stack

**Note**: Stack configuration files (`Pulumi.*.yaml`) are project-specific and contain your GCP project ID. These files are **not committed to the repository** (they're in `.gitignore`). Each user must create their own stack.

```bash
# Initialize a new Pulumi stack (use any name you like: dev, prod, staging, etc.)
pulumi stack init dev

# Configure required settings for your Google Cloud project
pulumi config set gcp:project YOUR_PROJECT_ID

# Optional: Set a specific region for Vertex AI (defaults to us-central1)
pulumi config set region us-central1

# Optional: Customize resource naming prefix (defaults to project ID)
pulumi config set resource_prefix my-app
```

This creates a `Pulumi.dev.yaml` file locally with your project-specific configuration.

#### Configuration Options

| Config Key        | Description                                                             | Default         | Example          |
| ----------------- | ----------------------------------------------------------------------- | --------------- | ---------------- |
| `gcp:project`     | **Required**. Your Google Cloud project ID                              | None            | `my-gcp-project` |
| `region`          | Vertex AI region                                                        | `us-central1`   | `europe-west1`   |
| `resource_prefix` | Prefix for resource naming. Resources will be named `{prefix}-{stack}`. | Your project ID | `my-app`         |

**Resource Details:**

- **Vertex AI Region**: Configurable via `region` parameter (default: `us-central1`). This determines where your AI model runs.
- **GCS Bucket Location**: Hard-coded to `US` (multi-regional) for high availability and geo-redundancy across all US regions.

**Service Account Naming Examples:**

- With default prefix: `my-gcp-project-dev@my-gcp-project.iam.gserviceaccount.com`
- With custom prefix: `my-app-dev@my-gcp-project.iam.gserviceaccount.com`

### 4. Deploy Infrastructure

```bash
# Review the resources that will be created
pulumi preview

# Deploy the infrastructure
pulumi up
```

This will create:

- ✅ Enable required APIs (Vertex AI, ML, Storage)
- ✅ Create a service account with appropriate permissions
- ✅ Create a GCS bucket for data storage
- ✅ Set up IAM roles and permissions

### 5. Get Deployment Information

After deployment, note the outputs:

```bash
pulumi stack output
```

You'll see information like:

- `project_id`: Your Google Cloud project ID
- `gemini_service_account_email`: Service account for API access
- `data_bucket_name`: Bucket for storing data/artifacts
- `usage_info`: Model details and endpoints

## Using Gemini 2.0 Flash

### Option 1: Use the Example Script

1. **Update the configuration** in `example_usage.py`:

   ```python
   PROJECT_ID = "your-actual-project-id"  # From pulumi output
   LOCATION = "us-central1"               # Your chosen region
   ```

2. **Run the examples**:
   ```bash
   python example_usage.py
   ```

### Option 2: Integrate into Your Application

```python
import vertexai
from vertexai.generative_models import GenerativeModel

# Initialize Vertex AI
vertexai.init(project="your-project-id", location="us-central1")

# Create model instance
model = GenerativeModel("gemini-2.0-flash-001")

# Generate content
response = model.generate_content("Explain quantum computing simply")
print(response.text)
```

## Available Gemini 2.0 Flash Features

### 🤖 **Text Generation**

```python
model = GenerativeModel("gemini-2.0-flash-001")
response = model.generate_content("Your prompt here")
```

### 💬 **Multi-turn Chat**

```python
chat = model.start_chat()
response1 = chat.send_message("Hello!")
response2 = chat.send_message("Tell me about AI")
```

### 🖼️ **Multimodal (Text + Images)**

```python
response = model.generate_content([
    "What's in this image?",
    Part.from_image(image_data)
])
```

### 🌊 **Streaming Responses**

```python
response = model.generate_content("Write a story", stream=True)
for chunk in response:
    print(chunk.text, end="")
```

### 🔧 **Function Calling**

```python
model = GenerativeModel("gemini-2.0-flash-001", tools=[your_function])
response = model.generate_content("What's the weather like?")
```

### 📋 **Structured Output**

```python
response = model.generate_content(
    "Generate JSON with user info",
    generation_config={"response_mime_type": "application/json"}
)
```

## Model Variants

| Model ID                        | Description                | Best For                          |
| ------------------------------- | -------------------------- | --------------------------------- |
| `gemini-2.0-flash-001`          | Standard Gemini 2.0 Flash  | General use, balanced performance |
| `gemini-2.0-flash-thinking-exp` | With thinking capabilities | Complex reasoning tasks           |

## Authentication Options

### 1. Service Account (Recommended for Production)

```python
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    "path/to/service-account-key.json"
)
vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
```

### 2. Application Default Credentials (Development)

```bash
gcloud auth application-default login
```

### 3. Using the Pulumi-created Service Account

The deployed service account has the necessary permissions. You can:

1. Download its key from Google Cloud Console
2. Use it in your application
3. Or impersonate it programmatically

## Cost Considerations

Gemini 2.0 Flash pricing is based on:

- **Input tokens**: Text you send to the model
- **Output tokens**: Text the model generates
- **Image processing**: When using multimodal features

💡 **Tip**: Use shorter prompts and limit output length to optimize costs.

## Monitoring and Logging

Enable monitoring in your code:

```python
from google.cloud import aiplatform

# Enable detailed logging
aiplatform.init(
    project=PROJECT_ID,
    location=LOCATION,
    experiment="gemini-experiments"
)
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**

   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **API Not Enabled**

   ```bash
   gcloud services enable aiplatform.googleapis.com
   ```

3. **Permission Denied**

   - Ensure your account has `roles/aiplatform.user`
   - Check service account permissions

4. **Quota Exceeded**
   - Check your Vertex AI quotas in Google Cloud Console
   - Request quota increases if needed

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Clean Up

To remove all created resources:

```bash
pulumi destroy
```

This will:

- Delete the service account
- Remove IAM bindings
- Delete the GCS bucket
- Keep APIs enabled (disable_on_destroy=False)

## Example Use Cases

1. **Content Generation**: Blog posts, articles, creative writing
2. **Code Assistance**: Code explanation, generation, debugging
3. **Data Analysis**: Summarizing reports, extracting insights
4. **Customer Support**: Automated responses, FAQ generation
5. **Education**: Tutoring, explanation of complex topics

## Further Resources

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Gemini API Reference](https://cloud.google.com/vertex-ai/generative-ai/docs)
- [Pulumi GCP Provider](https://www.pulumi.com/registry/packages/gcp/)
- [Google AI Studio](https://aistudio.google.com/) - Test prompts before coding

## Support

For issues:

1. Check the troubleshooting section above
2. Refer to Google Cloud documentation
3. Check Pulumi logs: `pulumi logs`
4. Review Google Cloud Console for API/permission issues
