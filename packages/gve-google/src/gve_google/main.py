from gve_google import config, auth
import os
import sys

import gve_google.auth
import gve_google.secrets


def main(*args):
    print("main")
    print("Arguments Passed:", args)
    # auth_client = gve_google.auth.Auth()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    client_email = os.environ.get("GVE_GOOGLE_EMAIL")
    private_key = os.environ.get("GVE_GOOGLE_KEY")

    print("Creating secrets manager...")
    secrets_client = gve_google.secrets.Manager(
        {
            "project_id": project_id,
            "client_email": client_email,
            "private_key": private_key,
        }
    )
    # print("Secrets client config:", secrets_client.config)
    SECRET_ID = "connection"
    SECRET_VALUE = {
        "client_id": None,
        "client_secret": None,
        "username": None,
        "password": None,
    }

    secret_path = secrets_client.create_secret(SECRET_ID)
    print(f"Created secret: {secret_path}")
    print(f"Secret IDs:", secrets_client.secrets)

    print(f"Updating secret:{secret_path}...")
    response = secrets_client.update_secret(SECRET_ID, SECRET_VALUE)
    print(response)


# Check to see if this file is the "__main__" script being executed
if __name__ == "__main__":
    # We don't care about the first unpacked value.
    # Use _ to "throw it away".
    _, *script_args = sys.argv
    main(*script_args)
