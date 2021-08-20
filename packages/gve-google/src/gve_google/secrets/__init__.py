from google.cloud import secretmanager
from google.oauth2 import service_account

from gve_google.auth import Auth
from google.api_core.exceptions import AlreadyExists as SecretAlreadyExists

_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


class Manager:
    def __init__(self, config):
        self.secrets = set()

        # https://stackoverflow.com/a/56099099/154065
        print(str(config))
        expanded_config = config.copy()
        expanded_config["token_uri"] = _DEFAULT_TOKEN_URI
        raw_key = expanded_config.get("private_key", "")
        formatted_key = Auth.format_key(raw_key)
        # print("Manager formatted key:", formatted_key)
        expanded_config["private_key"] = formatted_key
        self.config = expanded_config

        credentials = service_account.Credentials.from_service_account_info(
            expanded_config
        )
        # print("Formatted credentials:", credentials)
        self.client = secretmanager.SecretManagerServiceClient(credentials=credentials)

        self.project_id = expanded_config.get("project_id")
        self.project_path = f"projects/{self.project_id}"
        self.secret_settings = {"replication": {"automatic": {}}}

    def create_secret(self, secret_id):
        secret_id_name = None
        try:
            response = self.client.create_secret(
                secret_id=secret_id,
                parent=self.project_path,
                secret=self.secret_settings,
            )
            secret_id_name = response.name
        except SecretAlreadyExists as e:
            # Get the secret ID from the error message:
            # "Secret [projects/{project_number}/secrets/{secret_id}] already exists."
            secret_path = e.message.split()[1].strip("[]")
            secret_id_name = secret_path.split("/")[-1]

        if secret_id_name:
            self.secrets.add(secret_id_name)

        return secret_id_name

    def update_secret(self, secret_id, secret_value):
        secret_path = f"{self.project_path}/secrets/{secret_id}"
        encoded_value = str(secret_value).encode("utf-8")
        response = self.client.add_secret_version(
            parent=secret_path, payload={"data": encoded_value}
        )
        return response

    def get_secret(self, secret_id):
        # TODO: https://codelabs.developers.google.com/codelabs/secret-manager-python#6
        pass
