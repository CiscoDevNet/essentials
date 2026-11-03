"""Unit tests for Locust security group rules."""

import pulumi_aws as aws
from ess_load_test.infra.network import (
    build_locust_security_group_egress,
    build_locust_security_group_ingress,
    has_public_internet_ingress,
)

_LOCUST_MASTER_PORT = 5557
_LOCUST_STATS_PORT = 5558
_HTTP_PORT = 80
_HTTPS_PORT = 443
_DNS_PORT = 53


class TestSecurityGroupRules:
    def test_ingress_has_no_public_cidr(self):
        ingress_rules = build_locust_security_group_ingress()
        assert has_public_internet_ingress(ingress_rules) is False

    def test_ingress_allows_locust_coordination_ports(self):
        ingress_rules = build_locust_security_group_ingress()
        assert len(ingress_rules) == 1
        rule = ingress_rules[0]
        assert rule.from_port == _LOCUST_MASTER_PORT
        assert rule.to_port == _LOCUST_STATS_PORT
        assert rule.self is True

    def test_egress_allows_http_https_and_dns(self):
        egress_rules = build_locust_security_group_egress()
        assert any(
            rule.protocol == "tcp" and rule.from_port == _HTTP_PORT
            for rule in egress_rules
        )
        assert any(
            rule.protocol == "tcp" and rule.from_port == _HTTPS_PORT
            for rule in egress_rules
        )
        assert any(
            rule.protocol == "udp" and rule.from_port == _DNS_PORT
            for rule in egress_rules
        )

    def test_egress_allows_locust_coordination_ports(self):
        egress_rules = build_locust_security_group_egress()
        assert any(
            rule.protocol == "tcp"
            and rule.from_port == _LOCUST_MASTER_PORT
            and rule.to_port == _LOCUST_STATS_PORT
            and rule.self is True
            for rule in egress_rules
        )

    def test_detects_public_ipv4_ingress(self):
        public_rule = aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["0.0.0.0/0"],
        )
        assert has_public_internet_ingress([public_rule]) is True

    def test_detects_public_ipv6_ingress(self):
        public_rule = aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            ipv6_cidr_blocks=["::/0"],
        )
        assert has_public_internet_ingress([public_rule]) is True
