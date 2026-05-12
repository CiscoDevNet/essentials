"""Pretends to talk to an internal Cisco service. Fixture only."""

INTERNAL_HOST = "auth.cisco.com"
CONTACT_EMAIL = "internal-team@cisco.com"


def build_url(path: str) -> str:
    return f"https://{INTERNAL_HOST}{path}"
