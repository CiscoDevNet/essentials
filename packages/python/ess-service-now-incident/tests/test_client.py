"""Unit tests for parse_incident_input and helpers."""

from __future__ import annotations

import pytest
from ess_service_now_incident.client import (
    IncidentQuery,
    _is_servicenow_host,
    _normalize_url,
    parse_incident_input,
)
from ess_service_now_incident.exceptions import InputParseError

_SYS_ID = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"


class TestNormalizeUrl:
    def test_already_has_https(self):
        assert _normalize_url("https://x.com/p") == "https://x.com/p"

    def test_already_has_http(self):
        assert _normalize_url("http://x.com/p") == "http://x.com/p"

    def test_schemeless_url(self):
        assert (
            _normalize_url("example.service-now.com/foo")
            == "https://example.service-now.com/foo"
        )

    def test_bare_hostname(self):
        assert (
            _normalize_url("example.service-now.com")
            == "https://example.service-now.com"
        )

    def test_not_a_url(self):
        assert _normalize_url("INC0000001") == "INC0000001"


class TestIsServicenowHost:
    def test_exact_domain(self):
        assert _is_servicenow_host("service-now.com") is True

    def test_subdomain(self):
        assert _is_servicenow_host("example.service-now.com") is True

    def test_deep_subdomain(self):
        assert _is_servicenow_host("a.b.service-now.com") is True

    def test_malicious_prefix(self):
        assert _is_servicenow_host("evilservice-now.com") is False

    def test_malicious_suffix(self):
        assert _is_servicenow_host("service-now.com.evil.com") is False

    def test_unrelated_domain(self):
        assert _is_servicenow_host("example.com") is False


class TestParseIncidentNumber:
    def test_bare_inc_number(self):
        result = parse_incident_input("INC0000001")
        assert result == IncidentQuery("number", "INC0000001")

    def test_lowercase_inc_number(self):
        result = parse_incident_input("inc0000001")
        assert result == IncidentQuery("number", "INC0000001")

    def test_inc_with_whitespace(self):
        result = parse_incident_input("  INC0000001  ")
        assert result == IncidentQuery("number", "INC0000001")


class TestParseUrlWithSysId:
    def test_workspace_url(self):
        url = f"https://example.service-now.com/now/sow/record/incident/{_SYS_ID}"
        result = parse_incident_input(url)
        assert result == IncidentQuery("sys_id", _SYS_ID, "example.service-now.com")

    def test_classic_url_with_query_param(self):
        url = f"https://example.service-now.com/incident.do?sys_id={_SYS_ID}"
        result = parse_incident_input(url)
        assert result == IncidentQuery("sys_id", _SYS_ID, "example.service-now.com")

    def test_schemeless_url(self):
        url = f"example.service-now.com/now/sow/record/incident/{_SYS_ID}"
        result = parse_incident_input(url)
        assert result == IncidentQuery("sys_id", _SYS_ID, "example.service-now.com")

    def test_url_without_sys_id_raises(self):
        with pytest.raises(InputParseError, match="Could not extract a sys_id"):
            parse_incident_input(
                "https://example.service-now.com/nav_to.do?uri=incident_list.do"
            )


class TestHostnameValidation:
    def test_malicious_domain_rejected(self):
        url = f"https://evilservice-now.com/incident/{_SYS_ID}"
        with pytest.raises(InputParseError, match="not a ServiceNow instance"):
            parse_incident_input(url)

    def test_subdomain_attack_rejected(self):
        url = f"https://service-now.com.evil.com/incident/{_SYS_ID}"
        with pytest.raises(InputParseError, match="not a ServiceNow instance"):
            parse_incident_input(url)

    def test_valid_subdomain_accepted(self):
        url = f"https://example.service-now.com/now/sow/record/incident/{_SYS_ID}"
        result = parse_incident_input(url)
        assert result.instance == "example.service-now.com"

    def test_different_subdomain_accepted(self):
        url = f"https://acme.service-now.com/now/sow/record/incident/{_SYS_ID}"
        result = parse_incident_input(url)
        assert result.instance == "acme.service-now.com"


class TestInvalidInput:
    def test_random_string_raises(self):
        with pytest.raises(InputParseError, match="Unrecognised input"):
            parse_incident_input("hello world")

    def test_empty_string_raises(self):
        with pytest.raises(InputParseError, match="Unrecognised input"):
            parse_incident_input("")

    def test_non_servicenow_url_raises(self):
        with pytest.raises(InputParseError, match="not a ServiceNow instance"):
            parse_incident_input("https://example.com/INC123")
