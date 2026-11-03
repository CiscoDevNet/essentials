"""Identify our token traffic to the edge in front of the token endpoint.

Operators of an identity platform can match an agreed header key/value pair
at their edge or CDN layer and treat the traffic as a known service rather
than an anonymous source behind a shared NAT address. The pair is agreed out
of band, so it is configured through the environment (seeded from a secret
store) and never committed:

* ``OAUTH_TOKEN_CLIENT_HEADER_NAME`` -- header name, e.g. ``X-Client-App``
* ``OAUTH_TOKEN_CLIENT_HEADER_VALUE`` -- agreed value; treat as a secret

Both must be set for the header to be sent. The value is never logged.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

HEADER_NAME_ENV = "OAUTH_TOKEN_CLIENT_HEADER_NAME"
HEADER_VALUE_ENV = "OAUTH_TOKEN_CLIENT_HEADER_VALUE"

# RFC 9110 ``token`` characters. A name outside this set would make httpx
# raise on every request, which is worse than not identifying at all.
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
# Header names that would change how the token request authenticates or is
# routed rather than merely labelling it.
_RESERVED_NAMES = frozenset(
    {"authorization", "content-type", "content-length", "host", "cookie"}
)


def client_identity_headers() -> dict[str, str]:
    """Return the configured identification header, or an empty dict.

    Returns:
        ``{name: value}`` when both environment variables are set and the
        name is a valid, non-reserved header name; otherwise ``{}``.
    """
    name = os.environ.get(HEADER_NAME_ENV, "").strip()
    value = os.environ.get(HEADER_VALUE_ENV, "").strip()
    if not name and not value:
        return {}
    if not name or not value:
        logger.warning(
            "%s and %s must both be set; token requests will not carry an "
            "identification header",
            HEADER_NAME_ENV,
            HEADER_VALUE_ENV,
        )
        return {}
    if not _HEADER_NAME_RE.match(name) or name.lower() in _RESERVED_NAMES:
        logger.warning(
            "%s=%r is not an allowed header name; token requests will not "
            "carry an identification header",
            HEADER_NAME_ENV,
            name,
        )
        return {}
    return {name: value}
