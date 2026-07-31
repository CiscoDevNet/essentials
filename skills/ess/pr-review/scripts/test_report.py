"""Tests for the pr-review linter merge/rank logic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

EXPECTED_BANDIT_LINE = 42

from report import (  # noqa: E402
    Finding,
    build_report,
    eslint_severity,
    load_all,
    load_bandit,
    load_eslint,
    load_pylint,
    load_ruff,
    load_tools,
    normalize_path,
    pylint_severity,
    rank,
    ruff_severity,
)


def test_normalize_path_strips_dot_slash() -> None:
    assert normalize_path("./pkg/mod.py") == "pkg/mod.py"
    assert normalize_path("pkg/mod.py") == "pkg/mod.py"
    # An absolute path outside cwd is left unchanged (no crash).
    assert normalize_path("/elsewhere/x.ts") == "/elsewhere/x.ts"


def test_ruff_severity_buckets() -> None:
    assert ruff_severity("PLR0913") == "MEDIUM"  # too-many-arguments -> smell
    assert ruff_severity("C901") == "MEDIUM"  # complexity
    assert ruff_severity("PLR2004") == "LOW"  # magic value
    assert ruff_severity("F821") == "HIGH"  # undefined name
    assert ruff_severity("F401") == "LOW"  # unused import
    assert ruff_severity("PERF401") == "MEDIUM"
    assert ruff_severity("N802") == "LOW"
    assert ruff_severity("E999") == "HIGH"  # syntax/parse error -> can't run
    assert ruff_severity("E902") == "HIGH"  # IO error -> can't run
    assert ruff_severity("E501") == "LOW"  # line too long -> style


def test_pylint_severity_buckets() -> None:
    assert pylint_severity("R0801", "duplicate-code") == "MEDIUM"
    assert pylint_severity("W8101", "use-list-literal") == "MEDIUM"
    assert pylint_severity("E0602", "undefined-variable") == "HIGH"


def test_eslint_severity_buckets() -> None:
    assert eslint_severity("sonarjs/no-identical-functions", 1) == "MEDIUM"
    assert eslint_severity("sonarjs/cognitive-complexity", 2) == "MEDIUM"
    assert eslint_severity("@typescript-eslint/no-explicit-any", 2) == "MEDIUM"
    assert eslint_severity("prefer-const", 1) == "LOW"


def test_load_ruff_parses_findings(tmp_path: Path) -> None:
    (tmp_path / "ruff.json").write_text(
        json.dumps(
            [
                {
                    "code": "F401",
                    "message": "`os` imported but unused",
                    "filename": "pkg/mod.py",
                    "location": {"row": 3, "column": 1},
                }
            ]
        ),
        encoding="utf-8",
    )
    findings = load_ruff(tmp_path / "ruff.json")
    assert findings == [
        Finding(
            tool="ruff",
            rule="F401",
            severity="LOW",
            path="pkg/mod.py",
            line=3,
            message="`os` imported but unused",
        )
    ]


def test_load_bandit_uses_own_severity(tmp_path: Path) -> None:
    (tmp_path / "bandit.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "test_id": "B608",
                        "issue_severity": "HIGH",
                        "issue_text": "Possible SQL injection",
                        "filename": "pkg/db.py",
                        "line_number": 42,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    findings = load_bandit(tmp_path / "bandit.json")
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert findings[0].tool == "bandit"
    assert findings[0].line == EXPECTED_BANDIT_LINE


def test_load_pylint_duplicate_code(tmp_path: Path) -> None:
    (tmp_path / "pylint.json").write_text(
        json.dumps(
            [
                {
                    "message-id": "R0801",
                    "symbol": "duplicate-code",
                    "message": "Similar lines in 2 files",
                    "path": "pkg/a.py",
                    "line": 10,
                }
            ]
        ),
        encoding="utf-8",
    )
    findings = load_pylint(tmp_path / "pylint.json")
    assert findings[0].rule == "duplicate-code"
    assert findings[0].severity == "MEDIUM"


def test_load_eslint_flattens_messages(tmp_path: Path) -> None:
    (tmp_path / "eslint.json").write_text(
        json.dumps(
            [
                {
                    "filePath": "/repo/app/x.ts",
                    "messages": [
                        {
                            "ruleId": "sonarjs/no-duplicate-string",
                            "severity": 1,
                            "message": "Define a constant",
                            "line": 7,
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    findings = load_eslint(tmp_path)
    assert findings[0].tool == "eslint"
    assert findings[0].severity == "MEDIUM"
    assert findings[0].path == "/repo/app/x.ts"


def test_load_eslint_merges_multiple_parts(tmp_path: Path) -> None:
    (tmp_path / "eslint-1.json").write_text(
        '[{"filePath": "/r/a.ts", "messages": [{"ruleId": "no-x", '
        '"severity": 2, "message": "a", "line": 1}]}]',
        encoding="utf-8",
    )
    (tmp_path / "eslint-2.json").write_text(
        '[{"filePath": "/r/b.ts", "messages": [{"ruleId": "no-y", '
        '"severity": 1, "message": "b", "line": 2}]}]',
        encoding="utf-8",
    )
    findings = load_eslint(tmp_path)
    assert {f.path for f in findings} == {"/r/a.ts", "/r/b.ts"}


def test_load_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_ruff(tmp_path / "nope.json") == []


def test_rank_orders_by_severity_then_location() -> None:
    findings = [
        Finding("ruff", "N802", "LOW", "b.py", 1, ""),
        Finding("bandit", "B608", "HIGH", "z.py", 9, ""),
        Finding("ruff", "C901", "MEDIUM", "a.py", 5, ""),
        Finding("ruff", "F821", "HIGH", "a.py", 2, ""),
    ]
    ordered = rank(findings)
    assert [f.severity for f in ordered] == ["HIGH", "HIGH", "MEDIUM", "LOW"]
    # Within HIGH, a.py:2 sorts before z.py:9.
    assert ordered[0].path == "a.py"
    assert ordered[1].path == "z.py"


def test_build_report_counts_and_disables() -> None:
    findings = [
        Finding("bandit", "B608", "HIGH", "db.py", 1, "sqli"),
        Finding("ruff", "C901", "MEDIUM", "a.py", 5, "too complex"),
        Finding("ruff", "F401", "LOW", "a.py", 1, "unused"),
    ]
    disables = [
        {"path": "a.py", "line": 5, "text": "# pylint: disable=too-many-branches"}
    ]
    meta = {
        "owner": "o",
        "repo": "r",
        "number": "42",
        "base": "origin/main",
        "head": "HEAD",
        "python_files": 2,
        "typescript_files": 0,
        "tools": {"ruff": "ok", "eslint": "not run (no typescript files)"},
    }
    payload, markdown = build_report(findings, disables, meta)
    assert payload["summary"] == {"high": 1, "medium": 1, "low": 1}
    assert payload["slug"] == "o/r#42"
    assert payload["disables"] == disables
    assert "🔴 High (1)" in markdown
    assert "too-many-branches" in markdown
    assert "not run (no typescript files)" in markdown


def test_load_tools_parses_tsv(tmp_path: Path) -> None:
    (tmp_path / "tools.tsv").write_text(
        "ruff\tok\npylint\tnot run (tool unavailable)\n", encoding="utf-8"
    )
    tools = load_tools(tmp_path / "tools.tsv")
    assert tools == {"ruff": "ok", "pylint": "not run (tool unavailable)"}


def test_load_all_reads_directory(tmp_path: Path) -> None:
    (tmp_path / "ruff.json").write_text(
        '[{"code": "F401", "message": "x", '
        '"filename": "m.py", "location": {"row": 1}}]',
        encoding="utf-8",
    )
    (tmp_path / "disables.json").write_text(
        '[{"path": "m.py", "line": 2, "text": "# noqa"}]', encoding="utf-8"
    )
    (tmp_path / "scan-meta.json").write_text(
        '{"owner": "o", "repo": "r", "number": "1"}', encoding="utf-8"
    )
    (tmp_path / "tools.tsv").write_text("ruff\tok\n", encoding="utf-8")
    findings, disables, meta = load_all(tmp_path)
    assert len(findings) == 1
    assert len(disables) == 1
    assert meta["owner"] == "o"
    assert meta["tools"] == {"ruff": "ok"}
