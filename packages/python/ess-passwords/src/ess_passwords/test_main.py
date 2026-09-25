"""Tests for the ess-passwords CLI."""

from __future__ import annotations

import json
import re

from click.testing import CliRunner

from ess_passwords.__main__ import main


def _lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line]


def test_generate_prints_one_password() -> None:
    result = CliRunner().invoke(main, ["generate"])

    assert result.exit_code == 0
    assert re.fullmatch(r"[a-zA-Z]+(-[a-zA-Z]+){4}", _lines(result.stdout)[0])


def test_entropy_note_goes_to_stderr_only() -> None:
    result = CliRunner().invoke(main, ["generate"])

    # The password must pipe cleanly into a secret store, so stdout
    # carries nothing but the password itself.
    assert len(_lines(result.stdout)) == 1
    assert "entropy" not in result.stdout
    assert "bits of entropy" in result.stderr


def test_json_carries_the_password_and_its_strength() -> None:
    result = CliRunner().invoke(main, ["generate", "--json"])
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload.keys() == {"password", "entropy_bits", "wordlist_size"}
    assert payload["entropy_bits"] > 50


def test_json_with_count_is_a_list() -> None:
    result = CliRunner().invoke(main, ["generate", "--json", "--count", "3"])
    payload = json.loads(result.stdout)

    assert isinstance(payload, list)
    assert len({item["password"] for item in payload}) == 3


def test_count_prints_that_many_distinct_passwords() -> None:
    result = CliRunner().invoke(main, ["generate", "--count", "3"])

    assert result.exit_code == 0
    assert len(set(_lines(result.stdout))) == 3


def test_words_separator_and_digits_are_honoured() -> None:
    result = CliRunner().invoke(
        main,
        ["generate", "--words", "3", "--separator", ".", "--digits", "4"],
    )
    *words, digits = _lines(result.stdout)[0].split(".")

    assert len(words) == 3
    assert re.fullmatch(r"\d{4}", digits)


def test_capitalize_at_selects_the_position() -> None:
    result = CliRunner().invoke(main, ["generate", "--capitalize-at", "0"])

    assert re.fullmatch(r"[A-Z]+(-[a-z]+){4}", _lines(result.stdout)[0])


def test_out_of_range_capitalize_at_reports_the_policy_error() -> None:
    result = CliRunner().invoke(
        main,
        ["generate", "--words", "3", "--capitalize-at", "3"],
    )

    assert result.exit_code != 0
    assert "capitalized_index" in result.stderr


def test_impossible_max_length_reports_the_policy_error() -> None:
    result = CliRunner().invoke(
        main,
        ["generate", "--words", "8", "--max-length", "20"],
    )

    assert result.exit_code != 0
    assert "Reduce the word count" in result.stderr


def test_generate_offers_no_dry_run() -> None:
    # Read-only per cli-write-safety.mdc: there is nothing to preview,
    # so the flag must not exist rather than being a silent no-op.
    result = CliRunner().invoke(main, ["generate", "--dry-run"])

    assert result.exit_code != 0
    assert "no such option" in result.stderr.lower()
