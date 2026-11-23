"""Provision a Postgres database, schema, and four separated login roles."""

from .connection import Connector, Target
from .exceptions import (
    DeliveryError,
    InvalidNameError,
    PreflightError,
    ProvisionError,
    ProvisioningError,
    VerificationError,
)
from .lifecycle import rotate, teardown
from .naming import ROLE_KINDS, Names, derive_names
from .options import (
    CreateOptions,
    DeliveryOptions,
    RotateOptions,
    TeardownOptions,
    VerifyOptions,
)
from .provision import CreateResult, create
from .sql.database import ReaderGuards
from .ui import Ui
from .verify import Check, verify

__all__ = [
    "ROLE_KINDS",
    "Check",
    "Connector",
    "CreateOptions",
    "CreateResult",
    "DeliveryError",
    "DeliveryOptions",
    "InvalidNameError",
    "Names",
    "PreflightError",
    "ProvisionError",
    "ProvisioningError",
    "ReaderGuards",
    "RotateOptions",
    "Target",
    "TeardownOptions",
    "Ui",
    "VerificationError",
    "VerifyOptions",
    "create",
    "derive_names",
    "rotate",
    "teardown",
    "verify",
]
