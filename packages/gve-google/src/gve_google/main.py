from gve_google import config, auth
import os
import sys

import gve_google.auth


def main(*args):
    print("main")
    print("Arguments Passed:", args)
    print("config:", config)
    print("environment:", os.environ.get("GOOGLE_CLOUD_PROJECT"))
    auth_client = gve_google.auth.Auth()
    print(auth_client.credentials, auth_client.project)


# Check to see if this file is the "__main__" script being executed
if __name__ == "__main__":
    # We don't care about the first unpacked value.
    # Use _ to "throw it away".
    _, *script_args = sys.argv
    main(*script_args)
