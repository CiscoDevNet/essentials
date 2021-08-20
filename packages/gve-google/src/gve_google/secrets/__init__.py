from google.cloud import secretmanager
from google.oauth2 import service_account

from gve_google.auth import Auth

_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


class Manager:
    def __init__(self, config):
        # https://stackoverflow.com/a/56099099/154065
        print(str(config))
        expanded_config = config.copy()
        expanded_config["token_uri"] = _DEFAULT_TOKEN_URI
        raw_key = expanded_config.get("private_key", "")
        formatted_key = Auth.format_key(raw_key)
        print("Manager formatted key:", formatted_key)
        expanded_config["private_key"] = formatted_key
        self.config = expanded_config

        credentials = service_account.Credentials.from_service_account_info(
            expanded_config
        )
        print("Formatted credentials:", credentials)
        self.client = secretmanager.SecretManagerServiceClient(credentials=credentials)

        self.project_id = expanded_config.get("project_id")
        self.project_path = f"projects/{self.project_id}"
        self.secret_settings = {"replication": {"automatic": {}}}

    def create_secret(self, secret_id):
        return self.client.create_secret(
            secret_id=secret_id, parent=self.project_path, secret=self.secret_settings
        )
