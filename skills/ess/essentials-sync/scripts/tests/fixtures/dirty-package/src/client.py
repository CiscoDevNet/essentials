"""Pretends to talk to an Acme-Internal service. Fixture only."""

INTERNAL_HOST = "auth.corp.example"
CONTACT_EMAIL = "internal-team@acme-internal.com"


def build_url(path: str) -> str:
    return f"https://{INTERNAL_HOST}{path}"
