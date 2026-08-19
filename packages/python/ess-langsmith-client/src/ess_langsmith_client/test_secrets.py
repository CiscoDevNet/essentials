"""Tests for secret parsing and merging."""

import pytest

from ess_langsmith_client.secrets import get_env_secrets, merge_secrets, parse_secrets


def test_parse_secrets_splits_on_first_equals():
    assert parse_secrets(["TOKEN=abc=def"]) == [{"name": "TOKEN", "value": "abc=def"}]


def test_parse_secrets_handles_none():
    assert parse_secrets(None) == []


def test_get_env_secrets_reads_named_keys(monkeypatch):
    monkeypatch.setenv("WANTED", "yes")
    assert get_env_secrets(["WANTED"]) == [{"name": "WANTED", "value": "yes"}]


def test_get_env_secrets_skips_unset_and_empty(monkeypatch):
    monkeypatch.setenv("EMPTY", "")
    monkeypatch.delenv("ABSENT", raising=False)
    assert get_env_secrets(["EMPTY", "ABSENT"]) == []


def test_merge_secrets_ignores_environment_by_default(monkeypatch):
    """A deploy must not ship credentials the caller never named."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "leaked")
    monkeypatch.setenv("TAVILY_API_KEY", "leaked")
    assert merge_secrets([]) == []


def test_merge_secrets_adds_only_requested_env_keys(monkeypatch):
    monkeypatch.setenv("OPTED_IN", "value")
    monkeypatch.setenv("NOT_REQUESTED", "value")
    assert merge_secrets([], auto_detect_keys=["OPTED_IN"]) == [
        {"name": "OPTED_IN", "value": "value"}
    ]


def test_merge_secrets_cli_wins_over_environment(monkeypatch):
    monkeypatch.setenv("TOKEN", "from-env")
    assert merge_secrets(["TOKEN=from-cli"], auto_detect_keys=["TOKEN"]) == [
        {"name": "TOKEN", "value": "from-cli"}
    ]


@pytest.mark.parametrize("cli_secrets", [(), []])
def test_merge_secrets_accepts_tuple_or_list(cli_secrets):
    assert merge_secrets(cli_secrets) == []
