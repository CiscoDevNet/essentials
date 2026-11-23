"""Generate role passwords and the SCRAM verifiers the server receives instead."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import psycopg
from ess_passwords import PasswordOptions, generate_password

from .exceptions import ProvisioningError
from .naming import Names

DEFAULT_DIGITS = 4
MIN_DIGITS = 4

_WORD_COUNT = 5
_SCRAM_PREFIX = "SCRAM-SHA-256$"


@dataclass(frozen=True)
class RolePassword:
    """A generated password and its verifier for one role.

    Attributes:
        kind: The role kind.
        role: The role name.
        password: The plaintext. Never sent to the server.
        verifier: The SCRAM-SHA-256 verifier sent in `PASSWORD`.
        entropy_bits: Strength of the generation scheme.
    """

    kind: str
    role: str
    password: str = field(repr=False)
    verifier: str = field(repr=False)
    entropy_bits: float


def generate_role_passwords(
    conn: psycopg.Connection, names: Names, kinds: Sequence[str], digits: int
) -> dict[str, RolePassword]:
    """One independent password and verifier per role kind.

    Raises:
        ProvisioningError: libpq did not return a SCRAM-SHA-256 verifier.
    """
    options = PasswordOptions(word_count=_WORD_COUNT, digit_count=digits)
    passwords: dict[str, RolePassword] = {}
    for kind in kinds:
        role = names.role(kind)
        generated = generate_password(options)
        passwords[kind] = RolePassword(
            kind=kind,
            role=role,
            password=generated.value,
            verifier=scram_verifier(conn, role, generated.value),
            entropy_bits=generated.entropy_bits,
        )
    return passwords


def scram_verifier(conn: psycopg.Connection, role: str, password: str) -> str:
    """Hash `password` client-side so the plaintext never reaches the server.

    Naming the algorithm makes the result independent of the server's
    `password_encryption`, even `md5`.

    Raises:
        ProvisioningError: The result is not a SCRAM-SHA-256 verifier.
    """
    encoding = conn.info.encoding
    verifier = conn.pgconn.encrypt_password(
        password.encode(encoding), role.encode(encoding), b"scram-sha-256"
    ).decode("ascii")
    if not verifier.startswith(_SCRAM_PREFIX):
        msg = f"libpq returned a non-SCRAM verifier for {role}; refusing to use it."
        raise ProvisioningError(msg)
    return verifier
