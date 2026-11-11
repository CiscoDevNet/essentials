"""Tests for ess_aws_bedrock.config — config parsing and validation."""

import pytest

from ess_aws_bedrock.config import (
    _DEFAULT_BEDROCK_API_KEY_AGE_DAYS,
    _DEFAULT_MODEL_PATTERNS,
    AwsBedrockConfig,
    _compose_tags,
    _parse_bedrock_api_key_age_days,
    _parse_model_patterns,
)


class TestParseModelPatterns:
    """Tests for _parse_model_patterns."""

    def test_none_returns_defaults(self):
        assert _parse_model_patterns(None) == _DEFAULT_MODEL_PATTERNS

    def test_valid_list(self):
        assert _parse_model_patterns(["anthropic.*"]) == ("anthropic.*",)

    def test_multiple_patterns(self):
        result = _parse_model_patterns(["anthropic.*", "meta.*"])
        assert result == ("anthropic.*", "meta.*")

    def test_filters_blank_strings(self):
        result = _parse_model_patterns(["anthropic.*", "", "meta.*"])
        assert result == ("anthropic.*", "meta.*")

    def test_empty_list_raises_value_error(self):
        with pytest.raises(ValueError, match="no valid patterns"):
            _parse_model_patterns([])

    def test_all_blank_strings_raises_value_error(self):
        with pytest.raises(ValueError, match="no valid patterns"):
            _parse_model_patterns(["", ""])

    def test_string_wraps_to_list(self):
        assert _parse_model_patterns("anthropic.*") == ("anthropic.*",)

    def test_blank_string_raises_value_error(self):
        with pytest.raises(ValueError, match="no valid patterns"):
            _parse_model_patterns("")

    def test_dict_instead_of_list_raises_type_error(self):
        with pytest.raises(TypeError, match="must be a list"):
            _parse_model_patterns({"pattern": "anthropic.*"})

    def test_int_instead_of_list_raises_type_error(self):
        with pytest.raises(TypeError, match="must be a list"):
            _parse_model_patterns(42)

    def test_list_with_non_string_entry_raises_type_error(self):
        with pytest.raises(TypeError, match="each entry.*must be a string"):
            _parse_model_patterns(["anthropic.*", 123])

    def test_list_with_none_entry_raises_type_error(self):
        with pytest.raises(TypeError, match="each entry.*must be a string"):
            _parse_model_patterns(["anthropic.*", None])

    def test_list_with_dict_entry_raises_type_error(self):
        with pytest.raises(TypeError, match="each entry.*must be a string"):
            _parse_model_patterns([{"pattern": "anthropic.*"}])

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError, match="no valid patterns"):
            _parse_model_patterns(["   ", "\t"])

    def test_whitespace_string_raises_value_error(self):
        with pytest.raises(ValueError, match="no valid patterns"):
            _parse_model_patterns("   ")

    def test_strips_whitespace_from_patterns(self):
        result = _parse_model_patterns(["  anthropic.*  ", " meta.* "])
        assert result == ("anthropic.*", "meta.*")


class TestParseBedrockApiKeyAgeDays:
    """Tests for _parse_bedrock_api_key_age_days."""

    def test_none_returns_default(self):
        assert (
            _parse_bedrock_api_key_age_days(None) == _DEFAULT_BEDROCK_API_KEY_AGE_DAYS
        )

    @pytest.mark.parametrize("days", [1, 90, 36600])
    def test_in_range_passes_through(self, days):
        assert _parse_bedrock_api_key_age_days(days) == days

    @pytest.mark.parametrize("days", [0, -1, 36601])
    def test_out_of_range_raises_value_error(self, days):
        with pytest.raises(ValueError, match="between 1 and 36600"):
            _parse_bedrock_api_key_age_days(days)


class TestCredentialDefaults:
    """Credential flags keep the original behavior when unset."""

    def test_access_key_on_api_key_off(self):
        cfg = AwsBedrockConfig(
            project_name="ess-aws-bedrock",
            region="us-east-1",
            team_name="team",
            environment="development",
            user_name="user",
            policy_name="policy",
            model_patterns=_DEFAULT_MODEL_PATTERNS,
        )
        assert cfg.create_access_key is True
        assert cfg.create_bedrock_api_key is False
        assert cfg.bedrock_api_key_age_days == _DEFAULT_BEDROCK_API_KEY_AGE_DAYS


class TestComposeTags:
    """Tests for _compose_tags."""

    @pytest.mark.parametrize("tag_prefix", [None, ""])
    def test_no_prefix_leaves_keys_unprefixed(self, tag_prefix):
        assert _compose_tags("proj", "development", tag_prefix) == {
            "project": "proj",
            "managed-by": "pulumi",
            "environment": "development",
        }

    def test_prefix_namespaces_every_key(self):
        assert _compose_tags("proj", "production", "myteam") == {
            "myteam:project": "proj",
            "myteam:managed-by": "pulumi",
            "myteam:environment": "production",
        }

    @pytest.mark.parametrize("tag_prefix", ["aws", "AWS", "aws:team"])
    def test_reserved_namespace_raises_value_error(self, tag_prefix):
        with pytest.raises(ValueError, match="reserved"):
            _compose_tags("proj", "development", tag_prefix)

    def test_prefix_merely_starting_with_aws_is_allowed(self):
        assert "awsome:project" in _compose_tags("proj", "development", "awsome")
