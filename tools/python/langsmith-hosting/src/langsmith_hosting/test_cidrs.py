"""Tests for CIDR utilities."""

import pytest

from langsmith_hosting.cidrs import (
    AWS_EKS_MAX_PUBLIC_ACCESS_CIDRS,
    collapse_cidrs,
    get_cidrs,
)


class TestGetCidrs:
    def test_ipv4_bare_addresses(self):
        result = get_cidrs(("10.0.0.1", "192.168.1.1"))
        assert result == ("10.0.0.1/32", "192.168.1.1/32")

    def test_ipv6_bare_address(self):
        result = get_cidrs(("2001:db8::1",))
        assert result == ("2001:db8::1/128",)

    def test_passthrough_cidr(self):
        result = get_cidrs(("10.0.0.0/24", "192.168.0.0/16"))
        assert result == ("10.0.0.0/24", "192.168.0.0/16")

    def test_mixed_bare_and_cidr(self):
        result = get_cidrs(("10.0.0.1", "172.16.0.0/12", "2001:db8::1"))
        assert result == ("10.0.0.1/32", "172.16.0.0/12", "2001:db8::1/128")

    def test_empty_input(self):
        assert get_cidrs(()) == ()

    def test_invalid_ip_raises(self):
        with pytest.raises(ValueError):
            get_cidrs(("not-an-ip",))

    def test_invalid_cidr_raises(self):
        with pytest.raises(ValueError):
            get_cidrs(("999.999.999.999/32",))


class TestCollapseCidrs:
    def test_lossless_merge_adjacent(self):
        result = collapse_cidrs(["10.0.0.0/25", "10.0.0.128/25"], max_count=1)
        assert result == ["10.0.0.0/24"]

    def test_already_under_limit(self):
        cidrs = ["10.0.0.0/24", "192.168.0.0/24"]
        result = collapse_cidrs(cidrs, max_count=10)
        assert result == cidrs

    def test_lossy_collapse_reduces_count(self):
        cidrs = [f"10.0.0.{i}/32" for i in range(50)]
        result = collapse_cidrs(cidrs, max_count=AWS_EKS_MAX_PUBLIC_ACCESS_CIDRS)
        assert len(result) <= AWS_EKS_MAX_PUBLIC_ACCESS_CIDRS

    def test_max_count_validation(self):
        with pytest.raises(ValueError, match="max_count must be >= 1"):
            collapse_cidrs(["10.0.0.0/24"], max_count=0)

    def test_invalid_cidr_raises(self):
        with pytest.raises(ValueError):
            collapse_cidrs(["not-a-cidr"])

    def test_single_entry(self):
        assert collapse_cidrs(["10.0.0.1/32"], max_count=1) == ["10.0.0.1/32"]

    def test_empty_list(self):
        assert collapse_cidrs([], max_count=5) == []

    def test_mixed_ipv4_ipv6_collapses_ipv4_when_ipv6_is_lone(self):
        """IPv4 entries should still collapse even when a lone IPv6 /128 is present."""
        max_count = 2
        ipv4_siblings = ["10.0.0.0/32", "10.0.0.1/32"]
        ipv6_lone = ["2001:db8::1/128"]
        cidrs = ipv4_siblings + ipv6_lone
        result = collapse_cidrs(cidrs, max_count=max_count)
        assert len(result) <= max_count
        assert "2001:db8::1/128" in result

    def test_ipv6_only_collapse(self):
        result = collapse_cidrs(["2001:db8::0/128", "2001:db8::1/128"], max_count=1)
        assert result == ["2001:db8::/127"]

    def test_unrelated_hosts_may_exceed_limit(self):
        """Completely unrelated /32 hosts cannot be collapsed -- result exceeds max."""
        max_count = 2
        cidrs = [f"{i}.0.0.1/32" for i in range(1, 5)]
        result = collapse_cidrs(cidrs, max_count=max_count)
        assert len(result) >= max_count
