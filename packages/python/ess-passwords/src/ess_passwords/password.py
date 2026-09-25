"""Readable password generation.

Thin wrapper around `xkcdpass`, which draws from
:class:`random.SystemRandom`. The candidate words come from
:mod:`ess_passwords.wordlist`, which filters the EFF long list.
"""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass

from xkcdpass import xkcd_password

from .exceptions import PasswordPolicyError
from .wordlist import load_wordlist

DEFAULT_WORD_COUNT = 5
DEFAULT_SEPARATOR = "-"

_DIGITS = "0123456789"

# Give up rather than loop forever when max_length is set too low.
_MAX_GENERATION_ATTEMPTS = 100

# Shortest possible word, used only to explain an impossible max_length.
_MIN_WORD_LENGTH = 4


@dataclass(frozen=True)
class PasswordOptions:
    """Knobs for password generation.

    Attributes:
        word_count: Number of words in the password.
        separator: String joining the words, and the digits when asked for.
        max_length: Reject and regenerate passwords longer than this.
        capitalized_index: Position of the one upper-cased word, counting
            from 0. Defaults to a position chosen at random.
        digit_count: Digits appended after the last word. Defaults to none.
    """

    word_count: int = DEFAULT_WORD_COUNT
    separator: str = DEFAULT_SEPARATOR
    max_length: int | None = None
    capitalized_index: int | None = None
    digit_count: int = 0


@dataclass(frozen=True)
class GeneratedPassword:
    """A generated password and the strength of the scheme behind it.

    Attributes:
        value: The password itself.
        entropy_bits: Entropy contributed by the random word and digit
            choices. Which word is capitalised is not counted: it is worth
            only log2(word_count) against a scheme an attacker already
            knows, and understating strength is the safe direction.
        wordlist_size: Number of candidate words after length filtering.
    """

    value: str
    entropy_bits: float
    wordlist_size: int

    def __str__(self) -> str:
        return self.value


def _require_valid(options: PasswordOptions) -> None:
    """Reject options that can never produce a password."""
    if options.word_count < 1:
        msg = f"word_count must be at least 1, got {options.word_count}."
        raise PasswordPolicyError(msg)

    if options.digit_count < 0:
        msg = f"digit_count cannot be negative, got {options.digit_count}."
        raise PasswordPolicyError(msg)

    if options.max_length is not None and options.max_length < 1:
        msg = f"max_length must be at least 1, got {options.max_length}."
        raise PasswordPolicyError(msg)

    index = options.capitalized_index
    if index is not None and not 0 <= index < options.word_count:
        msg = (
            f"capitalized_index must be between 0 and {options.word_count - 1} "
            f"for {options.word_count} words, got {index}."
        )
        raise PasswordPolicyError(msg)

    if options.max_length is not None and options.max_length < _shortest_possible(
        options
    ):
        msg = _impossible_length_message(options)
        raise PasswordPolicyError(msg)


def _compose(words: list[str], options: PasswordOptions) -> str:
    """Join the words with one upper-cased, then append any digits."""
    capitalized = options.capitalized_index
    if capitalized is None:
        capitalized = secrets.randbelow(options.word_count)

    parts = [
        word.upper() if position == capitalized else word.lower()
        for position, word in enumerate(words)
    ]
    if options.digit_count:
        parts.append(
            "".join(secrets.choice(_DIGITS) for _ in range(options.digit_count))
        )
    return options.separator.join(parts)


def _shortest_possible(options: PasswordOptions) -> int:
    """Roughly the shortest password these options could produce."""
    groups = options.word_count + (1 if options.digit_count else 0)
    return (
        options.word_count * _MIN_WORD_LENGTH
        + options.digit_count
        + (groups - 1) * len(options.separator)
    )


def _impossible_length_message(options: PasswordOptions) -> str:
    """Why these options can never fit inside `max_length`."""
    needed = _shortest_possible(options)
    return (
        f"Could not generate a password of at most {options.max_length} characters "
        f"with {options.word_count} words (needs roughly {needed}). "
        f"Reduce the word count or raise the length limit."
    )


def generate_password(options: PasswordOptions | None = None) -> GeneratedPassword:
    """Generate a readable password such as `marble-TUNDRA-lantern-copper-bison`.

    Exactly one word is upper-cased. The result carries no date, symbol,
    or other tail -- append whatever the consuming system's complexity
    rules require, and size `max_length` to leave room for it.

    Args:
        options: Generation knobs. Defaults to five words joined by
            hyphens, one of them capitalised at random, no digits, and no
            length ceiling.

    Returns:
        The password plus the entropy of the scheme that produced it.

    Raises:
        PasswordPolicyError: The options cannot produce a password --
            `word_count` or `max_length` below 1, `capitalized_index`
            outside the words, or a `max_length` the word count cannot fit.
    """
    opts = options or PasswordOptions()
    _require_valid(opts)

    wordlist = load_wordlist()
    entropy_bits = opts.word_count * math.log2(len(wordlist))
    if opts.digit_count:
        entropy_bits += opts.digit_count * math.log2(len(_DIGITS))

    for _ in range(_MAX_GENERATION_ATTEMPTS):
        words = xkcd_password.generate_xkcdpassword(
            wordlist,
            numwords=opts.word_count,
            delimiter="\n",
            case="lower",
        ).split("\n")
        candidate = _compose(words, opts)
        if opts.max_length is None or len(candidate) <= opts.max_length:
            return GeneratedPassword(
                value=candidate,
                entropy_bits=entropy_bits,
                wordlist_size=len(wordlist),
            )

    msg = _impossible_length_message(opts)
    raise PasswordPolicyError(msg)
