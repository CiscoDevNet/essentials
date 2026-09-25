"""Domain exceptions for password generation."""

from __future__ import annotations


class EssPasswordsError(Exception):
    """Base class for every error raised by this package."""


class PasswordPolicyError(EssPasswordsError):
    """The requested password options cannot produce a valid password."""
