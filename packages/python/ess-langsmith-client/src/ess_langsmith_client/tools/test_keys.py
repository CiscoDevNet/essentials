"""Tests for langsmith-client keys timestamp parsing and list filtering."""

import json
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from ess_langsmith_client.tools import keys
from ess_langsmith_client.tools.keys import (
    _age_days,
    _format_expires,
    _is_expired,
    _parse_dt,
    _select_targets,
    cli,
)

# Pin "now" so age/expiry calculations are deterministic.
_FIXED_NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
# Days between 2026-01-01 and _FIXED_NOW (2026 is not a leap year).
_EXPECTED_AGE_DAYS = 151


class _FrozenDatetime(datetime):
    """datetime subclass with a fixed ``now`` for deterministic tests."""

    @classmethod
    def now(cls, tz=None):
        return _FIXED_NOW if tz is None else _FIXED_NOW.astimezone(tz)


@pytest.fixture
def frozen_now(monkeypatch):
    """Pin ``keys.datetime.now`` to a fixed instant."""
    monkeypatch.setattr(keys, "datetime", _FrozenDatetime)
    return _FIXED_NOW


def _sample_keys() -> list[dict]:
    """Three keys: an old one, an expired one, and a fresh non-expiring one."""
    return [
        {
            "id": "id-a",
            "description": "old-key",
            "short_key": "aaaa",
            # 151 days before _FIXED_NOW; expires far in the future.
            "created_at": "2026-01-01T00:00:00Z",
            "expires_at": "2027-01-01T00:00:00Z",
        },
        {
            "id": "id-b",
            "description": "expired-key",
            "short_key": "bbbb",
            "created_at": "2026-05-25T00:00:00Z",
            "expires_at": "2026-05-30T00:00:00Z",
        },
        {
            "id": "id-c",
            "description": "fresh-key",
            "short_key": "cccc",
            "created_at": "2026-05-31T00:00:00Z",
            "expires_at": None,
        },
    ]


class TestParseDt:
    def test_normalizes_trailing_z(self):
        parsed = _parse_dt("2026-01-01T00:00:00Z")
        assert parsed == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert parsed.tzinfo is not None

    def test_naive_string_becomes_utc(self):
        parsed = _parse_dt("2026-01-01T00:00:00")
        assert parsed.tzinfo == timezone.utc

    def test_naive_datetime_object_becomes_utc(self):
        parsed = _parse_dt(datetime(2026, 1, 1, 12, 0, 0))
        assert parsed.tzinfo == timezone.utc

    def test_aware_datetime_object_preserved(self):
        aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _parse_dt(aware) == aware


class TestAgeDays:
    def test_parses_rfc3339_z(self, frozen_now):
        assert _age_days({"created_at": "2026-01-01T00:00:00Z"}) == _EXPECTED_AGE_DAYS

    def test_missing_created_at_returns_none(self, frozen_now):
        assert _age_days({}) is None


class TestIsExpired:
    def test_expired_z_timestamp(self, frozen_now):
        assert _is_expired({"expires_at": "2026-05-01T00:00:00Z"}) is True

    def test_future_z_timestamp_not_expired(self, frozen_now):
        assert _is_expired({"expires_at": "2026-07-01T00:00:00Z"}) is False

    def test_missing_expires_at_not_expired(self, frozen_now):
        assert _is_expired({}) is False


class TestFormatExpires:
    def test_expired_z_timestamp_labelled(self, frozen_now):
        assert _format_expires({"expires_at": "2026-05-01T00:00:00Z"}) == (
            "2026-05-01 (EXPIRED)"
        )

    def test_future_z_timestamp_plain(self, frozen_now):
        assert _format_expires({"expires_at": "2026-07-01T00:00:00Z"}) == "2026-07-01"

    def test_no_expiry(self, frozen_now):
        assert _format_expires({"expires_at": None}) == "never"


class TestListFilters:
    def _invoke(self, monkeypatch, frozen_now, args):
        monkeypatch.setattr(keys.APIKeyClient, "list_keys", lambda self: _sample_keys())
        runner = CliRunner()
        return runner.invoke(cli, ["list", "--api-key", "test-key", *args])

    def test_expired_filter(self, monkeypatch, frozen_now):
        result = self._invoke(
            monkeypatch, frozen_now, ["--expired", "--format", "json"]
        )
        assert result.exit_code == 0
        ids = {k["id"] for k in json.loads(result.output)}
        assert ids == {"id-b"}

    def test_older_than_filter(self, monkeypatch, frozen_now):
        result = self._invoke(
            monkeypatch, frozen_now, ["--older-than", "90", "--format", "json"]
        )
        assert result.exit_code == 0
        ids = {k["id"] for k in json.loads(result.output)}
        assert ids == {"id-a"}


def _keys_with_duplicate() -> list[dict]:
    """Keys where "dup-key" appears twice and "unique-key" once."""
    return [
        {"id": "id-1", "description": "dup-key", "short_key": "1111"},
        {"id": "id-2", "description": "dup-key", "short_key": "2222"},
        {"id": "id-3", "description": "unique-key", "short_key": "3333"},
    ]


class TestSelectTargets:
    def test_unique_match(self):
        targets, duplicates = _select_targets(_keys_with_duplicate(), ("unique-key",))
        assert {k["id"] for k in targets} == {"id-3"}
        assert duplicates == {}

    def test_duplicate_detection(self):
        targets, duplicates = _select_targets(_keys_with_duplicate(), ("dup-key",))
        assert {k["id"] for k in targets} == {"id-1", "id-2"}
        assert set(duplicates) == {"dup-key"}
        assert {k["id"] for k in duplicates["dup-key"]} == {"id-1", "id-2"}

    def test_non_matching_description_ignored(self):
        targets, duplicates = _select_targets(
            _keys_with_duplicate(), ("does-not-exist",)
        )
        assert targets == []
        assert duplicates == {}


class TestDelete:
    def _run(self, monkeypatch, args, deleted_ids):
        monkeypatch.setattr(
            keys.APIKeyClient, "list_keys", lambda self: _keys_with_duplicate()
        )

        def _record_delete(self, key_id):
            deleted_ids.append(key_id)
            return {"id": key_id}

        monkeypatch.setattr(keys.APIKeyClient, "delete_key", _record_delete)
        runner = CliRunner()
        return runner.invoke(cli, ["delete", "--api-key", "test-key", *args])

    def test_duplicate_without_all_errors(self, monkeypatch):
        deleted_ids: list[str] = []
        result = self._run(monkeypatch, ["dup-key", "--yes"], deleted_ids)
        assert result.exit_code != 0
        assert "dup-key" in result.output
        assert "matches 2 keys" in result.output
        assert deleted_ids == []

    def test_duplicate_with_all_deletes_both(self, monkeypatch):
        deleted_ids: list[str] = []
        result = self._run(monkeypatch, ["dup-key", "--all", "--yes"], deleted_ids)
        assert result.exit_code == 0
        assert set(deleted_ids) == {"id-1", "id-2"}

    def test_unique_deletes_single(self, monkeypatch):
        deleted_ids: list[str] = []
        result = self._run(monkeypatch, ["unique-key", "--yes"], deleted_ids)
        assert result.exit_code == 0
        assert deleted_ids == ["id-3"]
