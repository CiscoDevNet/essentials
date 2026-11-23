"""The word source for generated passwords, with unsuitable words removed.

Generated passwords get pasted into tickets, chat, and runbooks, so they
have to read professionally. The EFF long list is mostly clean but not
entirely -- it contains `badass`, which is how this filter came to exist.

`xkcdpass` cannot do this for us. Its only filters are `min_length`,
`max_length`, and `valid_chars` (a per-character pattern, not a word
filter), and no bundled list avoids the problem: `eff-special` also
contains `badass`, `eff-short` contains `grope`, and both are small
enough to cost around 12 bits of entropy compared with `eff-long`.
Filtering the long list ourselves keeps the strength and fixes the words.
"""

from __future__ import annotations

from functools import lru_cache

from xkcdpass import xkcd_password

WORDFILE = "eff-long"

# Readability bounds -- long enough to be distinct, short enough to type.
_MIN_WORD_LENGTH = 4
_MAX_WORD_LENGTH = 8

# Profanity and sexual terms present in the length-filtered EFF long
# list. Compared whole-word and case-insensitively: a substring test
# would take `class`, `grass`, and `assess` with it.
#
# Deliberately narrow. The same list also holds bleak-but-inoffensive
# words (`treason`, `carnage`, `obituary` and about 55 others); add them
# here if passwords should avoid a grim tone as well, which costs well
# under a tenth of a bit.
_EXCLUDED_WORDS = frozenset(
    {
        "badass",
        "gigolo",
        "grope",
        "impure",
        "rectal",
        "seduce",
    }
)


@lru_cache(maxsize=1)
def load_wordlist() -> tuple[str, ...]:
    """Candidate words for password generation.

    Reading and filtering the EFF list costs the same every time, and a
    password is generated per call, so the result is cached for the
    lifetime of the process. Word selection happens in the caller, so
    caching here does not make passwords repeat. The tuple is immutable
    because every caller is handed the same object.

    Returns:
        The EFF long list, filtered to readable lengths, with unsuitable
        words removed. Callers derive entropy from its length, so the
        exclusions are reflected in the reported strength automatically.
    """
    words = xkcd_password.generate_wordlist(
        wordfile=xkcd_password.locate_wordfile(WORDFILE),
        min_length=_MIN_WORD_LENGTH,
        max_length=_MAX_WORD_LENGTH,
    )
    return tuple(word for word in words if word.lower() not in _EXCLUDED_WORDS)


def excluded_words() -> frozenset[str]:
    """The words this module refuses to put in a password."""
    return _EXCLUDED_WORDS
