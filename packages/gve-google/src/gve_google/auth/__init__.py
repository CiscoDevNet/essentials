from gve_google.auth import config
import google.auth


class Auth:
    # TODO: Implement fallbacks to authenticate: https://googleapis.dev/python/google-auth/latest/user-guide.html#service-account-private-key-files
    def __init__(self):
        self.credentials, self.project = google.auth.default()
