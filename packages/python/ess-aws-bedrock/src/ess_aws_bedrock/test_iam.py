"""Tests for ess_aws_bedrock.iam — policy document."""

import json

from ess_aws_bedrock.iam import _build_policy_document


def _actions(policy_json: str) -> list:
    return [stmt["Action"] for stmt in json.loads(policy_json)["Statement"]]


class TestBuildPolicyDocument:
    """Tests for _build_policy_document."""

    def test_default_has_no_bearer_token_statement(self):
        policy = _build_policy_document(["anthropic.*"])
        assert "bedrock:CallWithBearerToken" not in _actions(policy)

    def test_bearer_token_statement_when_enabled(self):
        policy = _build_policy_document(["anthropic.*"], allow_bearer_token=True)
        statements = json.loads(policy)["Statement"]
        assert {
            "Effect": "Allow",
            "Action": "bedrock:CallWithBearerToken",
            "Resource": "*",
        } in statements

    def test_extra_statements_follow_base_statements(self):
        extra = {"Effect": "Allow", "Action": "bedrock:Retrieve", "Resource": "*"}
        policy = _build_policy_document(
            ["anthropic.*"], [extra], allow_bearer_token=True
        )
        assert json.loads(policy)["Statement"][-1] == extra

    def test_model_patterns_become_foundation_model_arns(self):
        policy = _build_policy_document(["anthropic.*", "meta.*"])
        assert json.loads(policy)["Statement"][0]["Resource"] == [
            "arn:aws:bedrock:*::foundation-model/anthropic.*",
            "arn:aws:bedrock:*::foundation-model/meta.*",
        ]
