from copy import copy
from gve_google.auth import config
import google.auth

# _PKCS8_MARKER
BEGIN_KEY = "-----BEGIN PRIVATE KEY-----\n"
END_KEY = "\n-----END PRIVATE KEY-----\n"


class Auth:
    # TODO: Implement fallbacks to authenticate: https://googleapis.dev/python/google-auth/latest/user-guide.html#service-account-private-key-files
    def __init__(self):
        self.credentials, self.project = google.auth.default()

    @classmethod
    def format_key(cls, key):
        formatted_key = "\n".join(key.split("\\\\n"))
        if not formatted_key.startswith(BEGIN_KEY):
            formatted_key = f"{BEGIN_KEY}{formatted_key}"
        if not formatted_key.endswith(END_KEY):
            formatted_key = f"{formatted_key}{END_KEY}"

        return formatted_key
