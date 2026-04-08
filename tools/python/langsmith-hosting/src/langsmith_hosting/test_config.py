"""Tests for config utilities."""

import pytest

from langsmith_hosting.config import _parse_cidrs


class TestParseCidrs:
    """Tests for _parse_cidrs()."""

    def test_none_returns_empty(self):
        assert _parse_cidrs(None) == ()

    def test_empty_string_returns_empty(self):
        assert _parse_cidrs("") == ()

    def test_single_cidr(self):
        assert _parse_cidrs("10.0.0.0/24") == ("10.0.0.0/24",)

    def test_comma_separated(self):
        result = _parse_cidrs("10.0.0.0/24, 192.168.1.0/24")
        assert result == ("10.0.0.0/24", "192.168.1.0/24")

    def test_blank_entries_dropped(self):
        result = _parse_cidrs("10.0.0.0/24, , ,192.168.1.0/24")
        assert result == ("10.0.0.0/24", "192.168.1.0/24")

    def test_bare_ip_normalized_to_cidr(self):
        result = _parse_cidrs("10.0.0.1")
        assert result == ("10.0.0.1/32",)

    def test_host_bits_normalized(self):
        result = _parse_cidrs("10.0.0.5/24")
        assert result == ("10.0.0.0/24",)

    def test_invalid_cidr_raises(self):
        with pytest.raises(ValueError):
            _parse_cidrs("not-a-cidr")

    def test_ipv6_normalized(self):
        result = _parse_cidrs("2001:db8::1")
        assert result == ("2001:db8::1/128",)
