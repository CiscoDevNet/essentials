"""Tests for readable password generation."""

from __future__ import annotations

import re

import pytest
from xkcdpass import xkcd_password

from ess_passwords.exceptions import PasswordPolicyError
from ess_passwords.password import (
    DEFAULT_SEPARATOR,
    DEFAULT_WORD_COUNT,
    PasswordOptions,
    generate_password,
)
from ess_passwords.wordlist import excluded_words, load_wordlist


def _words(value: str, separator: str = DEFAULT_SEPARATOR) -> list[str]:
    return value.split(separator)


def _capitalized_index(value: str, separator: str = DEFAULT_SEPARATOR) -> int:
    return next(
        position
        for position, word in enumerate(_words(value, separator))
        if word.isupper()
    )


def test_default_shape() -> None:
    result = generate_password(PasswordOptions(capitalized_index=0))

    assert re.fullmatch(r"[A-Z]+(-[a-z]+){4}", result.value)


def test_one_word_is_upper_and_the_rest_are_lower() -> None:
    words = _words(generate_password().value)
    upper = [word for word in words if word.isupper()]

    assert len(upper) == 1
    assert len(words) == DEFAULT_WORD_COUNT
    assert all(word.islower() for word in words if not word.isupper())


def test_word_count_is_configurable() -> None:
    result = generate_password(PasswordOptions(word_count=7))

    assert len(_words(result.value)) == 7


def test_separator_is_configurable() -> None:
    result = generate_password(PasswordOptions(separator="."))

    assert len(_words(result.value, ".")) == DEFAULT_WORD_COUNT
    assert "-" not in result.value


def test_capitalized_index_selects_the_position() -> None:
    for position in range(DEFAULT_WORD_COUNT):
        result = generate_password(PasswordOptions(capitalized_index=position))

        assert _capitalized_index(result.value) == position


def test_capitalized_position_varies_by_default() -> None:
    # The position is drawn per password, so over many draws it must not
    # land on the same word every time.
    positions = {_capitalized_index(generate_password().value) for _ in range(200)}

    assert len(positions) > 1


def test_out_of_range_capitalized_index_raises() -> None:
    with pytest.raises(PasswordPolicyError, match="capitalized_index"):
        generate_password(PasswordOptions(word_count=3, capitalized_index=3))


def test_no_digits_by_default() -> None:
    assert not any(char.isdigit() for char in generate_password().value)


def test_digits_are_appended_after_the_words() -> None:
    result = generate_password(PasswordOptions(digit_count=4))
    *words, digits = _words(result.value)

    assert len(words) == DEFAULT_WORD_COUNT
    assert re.fullmatch(r"\d{4}", digits)


def test_digits_raise_entropy() -> None:
    without = generate_password().entropy_bits
    with_digits = generate_password(PasswordOptions(digit_count=4)).entropy_bits

    # Four decimal digits are worth 4 * log2(10), a little over 13 bits.
    assert with_digits > without + 13


def test_negative_digit_count_raises() -> None:
    with pytest.raises(PasswordPolicyError, match="digit_count"):
        generate_password(PasswordOptions(digit_count=-1))


def test_passwords_are_not_repeated() -> None:
    values = {generate_password().value for _ in range(20)}

    assert len(values) == 20


def test_reports_entropy_from_actual_wordlist() -> None:
    result = generate_password()

    assert result.wordlist_size > 1000
    # Five words from a wordlist of a few thousand clears 50 bits easily.
    assert result.entropy_bits > 50


def test_max_length_is_respected() -> None:
    result = generate_password(PasswordOptions(word_count=3, max_length=30))

    assert len(result.value) <= 30


def test_impossible_max_length_raises() -> None:
    with pytest.raises(PasswordPolicyError, match="Reduce the word count"):
        generate_password(PasswordOptions(word_count=8, max_length=20))


def test_impossible_max_length_is_rejected_before_generating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Eight words need roughly 39 characters, so no draw can fit 20. The
    # bound is known up front, so nothing should be composed at all.
    def unreachable(*args: object, **kwargs: object) -> str:
        raise AssertionError("no password should have been composed")

    monkeypatch.setattr(xkcd_password, "generate_xkcdpassword", unreachable)

    with pytest.raises(PasswordPolicyError, match="Reduce the word count"):
        generate_password(PasswordOptions(word_count=8, max_length=20))


def test_zero_words_raises() -> None:
    with pytest.raises(PasswordPolicyError, match="at least 1"):
        generate_password(PasswordOptions(word_count=0))


def test_zero_max_length_raises() -> None:
    with pytest.raises(PasswordPolicyError, match="max_length must be at least 1"):
        generate_password(PasswordOptions(max_length=0))


def test_negative_max_length_raises() -> None:
    # Rejected up front rather than after a hundred doomed attempts,
    # whose message would quote a nonsensical "at most -1 characters".
    with pytest.raises(PasswordPolicyError, match="max_length must be at least 1"):
        generate_password(PasswordOptions(max_length=-1))


def test_wordlist_is_loaded_once_across_generations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Every generate_password() asks for the wordlist, so reading and
    # filtering the EFF file has to happen on the first call only.
    loads = 0
    read_and_filter = xkcd_password.generate_wordlist

    def counting_generate_wordlist(**kwargs: object) -> list[str]:
        nonlocal loads
        loads += 1
        return read_and_filter(**kwargs)

    monkeypatch.setattr(xkcd_password, "generate_wordlist", counting_generate_wordlist)
    load_wordlist.cache_clear()

    values = {generate_password().value for _ in range(5)}

    assert loads == 1
    assert load_wordlist.cache_info().hits == 4
    # The cache holds the candidate words, not a password: selection is
    # still per call, so the results must all differ.
    assert len(values) == 5


def test_wordlist_excludes_unsuitable_words() -> None:
    words = {word.lower() for word in load_wordlist()}

    assert not words & excluded_words()


def test_badass_is_gone() -> None:
    # The word that prompted the filter. Named explicitly so a wordlist
    # or upstream change that reintroduces it fails loudly.
    assert "badass" not in {word.lower() for word in load_wordlist()}


def test_generated_passwords_avoid_excluded_words() -> None:
    excluded = excluded_words()
    for _ in range(200):
        words = {word.lower() for word in _words(generate_password().value)}

        assert not words & excluded


def test_reported_wordlist_size_matches_the_filtered_list() -> None:
    result = generate_password()

    # Entropy is derived from this number, so it must describe the list
    # actually drawn from rather than the unfiltered one.
    assert result.wordlist_size == len(load_wordlist())


def test_filtering_leaves_entropy_intact() -> None:
    # Removing a handful of words from several thousand must not
    # meaningfully weaken the scheme.
    assert generate_password().entropy_bits > 60
