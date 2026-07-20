"""Tests for summarize-change-log summary validation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_summary import (  # noqa: E402
    ValidationError,
    is_vague_subject,
    parse_document,
    validate_summary_text,
)

_REPO_ROOT = Path(__file__).resolve().parents[5]


def test_parse_document_extracts_subjects() -> None:
    text = "- **fix(api): short subject** — Details.\n"
    document = parse_document(text)
    assert document.subjects == ["fix(api): short subject"]
    assert document.footers == []


def test_parse_document_allows_footer_after_blank_line() -> None:
    text = (
        "- **fix(api): short subject** — Details.\n"
        "\n"
        "Co-authored-by: Alice <alice@example.com>\n"
    )
    document = parse_document(text)
    assert len(document.subjects) == 1
    assert len(document.footers) == 1


def test_parse_document_rejects_footer_without_blank_line() -> None:
    text = (
        "- **fix(api): short subject** — Details.\n"
        "Co-authored-by: Alice <alice@example.com>\n"
    )
    with pytest.raises(ValidationError, match="blank line required"):
        parse_document(text)


def test_parse_document_rejects_footer_between_bullets() -> None:
    text = (
        "- **fix(api): first** — One.\n"
        "\n"
        "Co-authored-by: Alice <alice@example.com>\n"
        "- **fix(api): second** — Two.\n"
    )
    with pytest.raises(ValidationError, match="must follow all bullets"):
        parse_document(text)


def test_parse_document_rejects_malformed_bullet() -> None:
    with pytest.raises(ValidationError, match="malformed bullet"):
        parse_document("- fix(api): missing bold wrapper — Details.\n")


def test_parse_document_rejects_unexpected_line() -> None:
    with pytest.raises(ValidationError, match="unexpected non-bullet"):
        parse_document("Intro prose\n- **fix(api): ok** — Details.\n")


def test_is_vague_subject_detects_port_from_inside_support() -> None:
    assert not is_vague_subject("fix(api): support migration from #123")


def test_is_vague_subject_detects_port_from_phrase() -> None:
    assert is_vague_subject("docs: port deployment naming docs from #510")


@patch("validate_summary.run_commitizen_check")
def test_validate_summary_text_checks_each_subject(mock_cz: MagicMock) -> None:
    text = (
        "- **fix(api): short subject** — Details.\n"
        "- **docs(web): update guide** — More.\n"
    )
    expected_count = len(parse_document(text).subjects)
    count = validate_summary_text(text, repo_root=_REPO_ROOT)
    assert count == expected_count
    assert mock_cz.call_count == expected_count


@patch("validate_summary.run_commitizen_check")
def test_validate_summary_text_rejects_vague_subject(mock_cz: MagicMock) -> None:
    text = "- **fix: address PR #123** — Process-only subject.\n"
    with pytest.raises(ValidationError, match="vague subject"):
        validate_summary_text(text, repo_root=_REPO_ROOT)
    mock_cz.assert_not_called()
