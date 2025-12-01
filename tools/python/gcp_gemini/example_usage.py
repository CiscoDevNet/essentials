"""
Example script showing how to use Gemini 2.5 Flash-Lite after Pulumi deployment.

This script demonstrates various ways to interact with Gemini 2.5 Flash-Lite through Vertex AI.

Prerequisites:
1. Deploy the infrastructure: pulumi up
2. Authenticate with GCP: gcloud auth application-default login

Configuration is automatically read from Pulumi stack outputs.
No environment variables or .env files needed!

To set Pulumi configuration (all optional):
  pulumi config set gcp:project YOUR_PROJECT_ID    # Optional (default: active gcloud project)
  pulumi config set region us-central1             # Optional (default: us-central1)
  pulumi config set resource_prefix my-app         # Optional (default: project ID)
"""

import json
import subprocess
import sys

from google import genai


def get_pulumi_outputs():
    """Get configuration from Pulumi stack outputs."""
    try:
        result = subprocess.run(
            ["pulumi", "stack", "output", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error reading Pulumi stack outputs: {e}")
        print("\nMake sure you have:")
        print("1. Run 'pulumi up' to deploy the infrastructure")
        print("2. Run this script from the gcp_gemini directory")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Error: Pulumi CLI not found")
        print("Install Pulumi: https://www.pulumi.com/docs/get-started/install/")
        sys.exit(1)


# Get configuration from Pulumi stack outputs
outputs = get_pulumi_outputs()
PROJECT_ID = outputs["project_id"]
LOCATION = outputs["usage_info"]["location"]
MODEL_NAME = outputs["usage_info"]["model_id"]

# Initialize the client for Vertex AI
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def initialize_vertex_ai():
    """Initialize Vertex AI with project and location."""
    # Client initialized globally above
    print(f"✅ Using project: {PROJECT_ID} in location: {LOCATION}")
    print(f"✅ Model: {MODEL_NAME}")


def simple_text_generation():
    """Demonstrate basic text generation with Gemini 2.5 Flash-Lite."""
    print("\n🤖 Simple Text Generation Example:")

    # Generate response
    prompt = "Explain quantum computing in simple terms."
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)

    print(f"Prompt: {prompt}")
    print(f"Response: {response.text}")

    return response


def chat_conversation():
    """Demonstrate a multi-turn chat conversation."""
    print("\n💬 Chat Conversation Example:")

    # First message
    message1 = "Hi! I'm learning about AI. Can you help?"
    response1 = client.models.generate_content(model=MODEL_NAME, contents=message1)
    print(f"User: {message1}")
    print(f"Gemini: {response1.text}")

    # Follow-up message (simple approach without conversation history)
    message2 = "What's the difference between machine learning and deep learning?"
    response2 = client.models.generate_content(model=MODEL_NAME, contents=message2)
    print(f"User: {message2}")
    print(f"Gemini: {response2.text}")

    return response2


def structured_output_example():
    """Demonstrate structured output generation."""
    print("\n📋 Structured Output Example:")

    prompt = """
    Create a JSON response with information about Python programming language.
    Include: name, creator, year_created, main_uses (array), and popularity_rank.
    Format the response as valid JSON.
    """

    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    print(f"Structured Response: {response.text}")

    return response


def multimodal_example():
    """Demonstrate multimodal capabilities (text + image)."""
    print("\n🖼️ Multimodal Example (requires image):")

    # Note: This is an example - you'd need to provide an actual image
    # For now, we'll just show the text-only approach
    prompt = """
    Describe what you would look for when analyzing an image of a sunset.
    What visual elements would you identify?
    """

    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    print(f"Response: {response.text}")

    return response


def function_calling_example():
    """Demonstrate function calling capabilities."""
    print("\n🔧 Function Calling Example:")

    # Note: Function calling format may differ in google-genai SDK
    # This example shows basic usage without tools for now
    response = client.models.generate_content(
        model=MODEL_NAME, contents="What's the weather like in San Francisco?"
    )
    print(f"Response: {response.text}")

    return response


def streaming_example():
    """Demonstrate streaming responses."""
    print("\n🌊 Streaming Response Example:")

    prompt = "Write a short story about a robot learning to paint."

    print("Streaming response:")
    response = client.models.generate_content_stream(model=MODEL_NAME, contents=prompt)

    full_response = ""
    for chunk in response:
        if chunk.text:
            print(chunk.text, end="", flush=True)
            full_response += chunk.text

    print("\n")
    return full_response


def batch_processing_example():
    """Demonstrate processing multiple prompts."""
    print("\n📦 Batch Processing Example:")

    prompts = [
        "What is artificial intelligence?",
        "Explain machine learning in one sentence.",
        "What are the benefits of cloud computing?",
        "How does blockchain work?",
    ]

    responses = []
    for i, prompt in enumerate(prompts, 1):
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        responses.append(response.text)
        print(f"{i}. Q: {prompt}")
        print(f"   A: {response.text[:100]}...")
        print()

    return responses


def main():
    """Run all examples."""
    print("🚀 Gemini 2.5 Flash-Lite Examples")
    print("=" * 50)

    try:
        # Initialize
        initialize_vertex_ai()

        # Run examples
        simple_text_generation()
        chat_conversation()
        structured_output_example()
        multimodal_example()
        function_calling_example()
        streaming_example()
        batch_processing_example()

        print("\n✅ All examples completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure you have:")
        print("1. Run 'pulumi up' to deploy the infrastructure")
        print("2. Set up authentication (gcloud auth application-default login)")
        print("3. Set Pulumi config (pulumi config set gcp:project YOUR_PROJECT_ID)")
        print("4. Installed required dependencies")


if __name__ == "__main__":
    main()
