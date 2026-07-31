#!/usr/bin/env python3
"""Merge and rank linter output for the pr-review skill.

Reads the raw linter JSON written by the scan scripts into an input directory and
emits two artifacts next to them:

* ``report.json`` -- normalized, severity-ranked findings plus suppression list.
* ``report.md``   -- the human/LLM-readable review scan the skill actually reads.

Stdlib only; no third-party dependencies, so it runs under bare ``python3`` when
the skill is lifted out of this repo.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
SEVERITY_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

# ruff codes for complexity / structure smells (never silently "just style").
_RUFF_COMPLEXITY = {
    "C901",
    "PLR0904",
    "PLR0911",
    "PLR0912",
    "PLR0913",
    "PLR0914",
    "PLR0915",
    "PLR0916",
    "PLR1702",
}
_RUFF_UNUSED = {"F401", "F811", "F841", "F842"}
# "E9" (E902 IO, E999 syntax/parse) are "can't run" errors -- rank HIGH so they
# are not buried by the generic "E" -> LOW rule below. Checked before LOW.
_RUFF_HIGH_PREFIXES = ("PLE", "S", "E9")
_RUFF_LOW_PREFIXES = ("E", "W", "I", "N", "D", "Q", "COM")
_ESLINT_ERROR_LEVEL = 2
_SHA_LEN = 40
_SHORT_SHA_LEN = 8


@dataclass(frozen=True)
class Finding:
    """A single normalized linter finding."""

    tool: str
    rule: str
    severity: str
    path: str
    line: int
    message: str


def ruff_severity(code: str) -> str:
    """Map a ruff rule code to HIGH/MEDIUM/LOW."""
    if code in _RUFF_COMPLEXITY:
        return "MEDIUM"
    if code == "PLR2004":
        return "LOW"
    if code.startswith("F"):
        return "LOW" if code in _RUFF_UNUSED else "HIGH"
    if code.startswith(_RUFF_HIGH_PREFIXES):
        return "HIGH"
    if code.startswith(_RUFF_LOW_PREFIXES):
        return "LOW"
    # B (bugbear), PERF, PLC/PLW/PLR and anything else -> a reviewable middle.
    return "MEDIUM"


def pylint_severity(message_id: str, symbol: str) -> str:
    """Map a pylint message to HIGH/MEDIUM/LOW."""
    if message_id.startswith("E") or message_id.startswith("F"):
        return "HIGH"
    if symbol == "duplicate-code" or message_id.startswith("W8"):
        return "MEDIUM"
    return "MEDIUM"


def eslint_severity(rule_id: str, eslint_level: int) -> str:
    """Map an eslint message to HIGH/MEDIUM/LOW."""
    smell_markers = (
        "no-identical-functions",
        "no-duplicate-string",
        "cognitive-complexity",
    )
    if rule_id and any(marker in rule_id for marker in smell_markers):
        return "MEDIUM"
    return "MEDIUM" if eslint_level == _ESLINT_ERROR_LEVEL else "LOW"


def normalize_path(raw: str) -> str:
    """Present a repo-relative path: drop a leading ``./`` and relativize
    absolute paths under the current working directory (eslint emits absolute)."""
    path = raw.strip()
    if path.startswith("./"):
        path = path[2:]
    if path.startswith("/"):
        try:
            path = str(Path(path).resolve().relative_to(Path.cwd()))
        except ValueError:
            pass
    return path


def _load_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def load_ruff(path: Path) -> list[Finding]:
    """Parse ruff --output-format=json into findings."""
    data = _load_json(path)
    findings: list[Finding] = []
    if not isinstance(data, list):
        return findings
    for item in data:
        code = str(item.get("code") or "?")
        location = item.get("location") or {}
        findings.append(
            Finding(
                tool="ruff",
                rule=code,
                severity=ruff_severity(code),
                path=normalize_path(str(item.get("filename") or "?")),
                line=int(location.get("row") or 0),
                message=str(item.get("message") or "").strip(),
            )
        )
    return findings


def load_bandit(path: Path) -> list[Finding]:
    """Parse bandit -f json into findings (bandit's own severity is used)."""
    data = _load_json(path)
    findings: list[Finding] = []
    if not isinstance(data, dict):
        return findings
    for item in data.get("results", []) or []:
        severity = str(item.get("issue_severity") or "MEDIUM").upper()
        if severity not in SEVERITY_ORDER:
            severity = "MEDIUM"
        findings.append(
            Finding(
                tool="bandit",
                rule=str(item.get("test_id") or "?"),
                severity=severity,
                path=normalize_path(str(item.get("filename") or "?")),
                line=int(item.get("line_number") or 0),
                message=str(item.get("issue_text") or "").strip(),
            )
        )
    return findings


def load_pylint(path: Path) -> list[Finding]:
    """Parse pylint --output-format=json into findings."""
    data = _load_json(path)
    findings: list[Finding] = []
    if not isinstance(data, list):
        return findings
    for item in data:
        message_id = str(item.get("message-id") or item.get("messageId") or "?")
        symbol = str(item.get("symbol") or "")
        findings.append(
            Finding(
                tool="pylint",
                rule=symbol or message_id,
                severity=pylint_severity(message_id, symbol),
                path=normalize_path(str(item.get("path") or "?")),
                line=int(item.get("line") or 0),
                message=str(item.get("message") or "").strip(),
            )
        )
    return findings


def load_eslint(input_dir: Path) -> list[Finding]:
    """Parse every ``eslint*.json`` part in ``input_dir`` into findings.

    ESLint is often installed per-app in a monorepo, so ``lint_ts.sh`` may run it
    once per app and emit one part file per group; they are merged here.
    """
    findings: list[Finding] = []
    for part in sorted(input_dir.glob("eslint*.json")):
        data = _load_json(part)
        if not isinstance(data, list):
            continue
        for file_result in data:
            file_path = normalize_path(str(file_result.get("filePath") or "?"))
            for message in file_result.get("messages", []) or []:
                rule_id = str(message.get("ruleId") or "?")
                level = int(message.get("severity") or 1)
                findings.append(
                    Finding(
                        tool="eslint",
                        rule=rule_id,
                        severity=eslint_severity(rule_id, level),
                        path=file_path,
                        line=int(message.get("line") or 0),
                        message=str(message.get("message") or "").strip(),
                    )
                )
    return findings


def load_disables(path: Path) -> list[dict]:
    """Parse the suppression-comment JSON array."""
    data = _load_json(path)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def load_tools(path: Path) -> dict:
    """Parse the tool<TAB>status run-status file into an ordered dict."""
    tools: dict[str, str] = {}
    if not path.is_file():
        return tools
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" in line:
            name, state = line.split("\t", 1)
            tools[name.strip()] = state.strip()
    return tools


def rank(findings: list[Finding]) -> list[Finding]:
    """Sort findings by severity, then path, then line."""
    return sorted(
        findings,
        key=lambda finding: (
            SEVERITY_ORDER.get(finding.severity, 1),
            finding.path,
            finding.line,
        ),
    )


def build_report(
    findings: list[Finding],
    disables: list[dict],
    meta: dict,
) -> tuple[dict, str]:
    """Build the report.json payload and the report.md text."""
    ordered = rank(findings)
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for finding in ordered:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    tools = meta.get("tools", {}) if isinstance(meta, dict) else {}
    payload = {
        "slug": _slug(meta),
        "base": meta.get("base", ""),
        "head": meta.get("head", ""),
        "python_files": meta.get("python_files", 0),
        "typescript_files": meta.get("typescript_files", 0),
        "summary": {k.lower(): v for k, v in counts.items()},
        "tools": tools,
        "findings": [asdict(finding) for finding in ordered],
        "disables": disables,
    }
    return payload, _render_markdown(ordered, counts, disables, meta, tools)


def _slug(meta: dict) -> str:
    owner = meta.get("owner") or "local"
    repo = meta.get("repo") or "repo"
    number = meta.get("number") or "range"
    return (
        f"{owner}/{repo}#{number}" if number != "range" else f"{owner}/{repo} (range)"
    )


def _short_ref(ref: str) -> str:
    """Abbreviate a full 40-char git SHA to 8 chars; leave named refs untouched."""
    if len(ref) == _SHA_LEN and all(c in "0123456789abcdef" for c in ref):
        return ref[:_SHORT_SHA_LEN]
    return ref


def _render_markdown(
    ordered: list[Finding],
    counts: dict,
    disables: list[dict],
    meta: dict,
    tools: dict,
) -> str:
    lines: list[str] = []
    lines.append(f"# PR review scan — {_slug(meta)}")
    lines.append("")
    lines.append(
        f"Range `{meta.get('base', '?')}...{_short_ref(meta.get('head', '?'))}` · "
        f"{meta.get('python_files', 0)} python / "
        f"{meta.get('typescript_files', 0)} typescript files changed."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("| --- | --- |")
    lines.extend(
        f"| {SEVERITY_EMOJI[sev]} {sev.title()} | {counts.get(sev, 0)} |"
        for sev in ("HIGH", "MEDIUM", "LOW")
    )
    lines.append(f"| Suppressions added | {len(disables)} |")
    lines.append("")
    lines.append(
        "> These are deterministic linter findings. Judge them, don't just "
        "repost them: skip pre-existing noise, keep the high-signal issues, and "
        "spend your effort on correctness, cross-file logic, and the suppression "
        "justifications below (see the skill's references)."
    )
    lines.append("")

    for sev in ("HIGH", "MEDIUM", "LOW"):
        bucket = [finding for finding in ordered if finding.severity == sev]
        if not bucket:
            continue
        lines.append(f"## {SEVERITY_EMOJI[sev]} {sev.title()} ({len(bucket)})")
        lines.append("")
        lines.extend(
            f"- `{finding.path}:{finding.line}` — **{finding.rule}** "
            f"({finding.tool}) {finding.message}"
            for finding in bucket
        )
        lines.append("")

    lines.append("## Suppressions added by this PR")
    lines.append("")
    if disables:
        lines.append(
            "Evaluate each: `too-many-*` / `line-too-long` are never OK; "
            "`import-error` / dynamic `no-member` often are."
        )
        lines.append("")
        for item in disables:
            path = item.get("path", "?")
            line = item.get("line", 0)
            text = str(item.get("text", "")).strip()
            lines.append(f"- `{path}:{line}` — `{text}`")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Tools")
    lines.append("")
    if tools:
        for name, state in tools.items():
            lines.append(f"- {name}: {state}")
    else:
        lines.append("- (no tool status recorded)")
    lines.append("")
    return "\n".join(lines)


def load_all(input_dir: Path) -> tuple[list[Finding], list[dict], dict]:
    """Load every linter artifact from ``input_dir``."""
    findings: list[Finding] = []
    findings += load_ruff(input_dir / "ruff.json")
    findings += load_bandit(input_dir / "bandit.json")
    findings += load_pylint(input_dir / "pylint.json")
    findings += load_eslint(input_dir)
    disables = load_disables(input_dir / "disables.json")
    meta = _load_json(input_dir / "scan-meta.json")
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("tools", {})
    tools = load_tools(input_dir / "tools.tsv")
    if tools:
        meta["tools"] = tools
    return findings, disables, meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge pr-review linter output.")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing the raw linter JSON (scan output).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where to write report.json/report.md (default: input dir).",
    )
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.is_dir():
        print(f"report: input dir not found: {input_dir}", file=sys.stderr)
        return 1
    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    findings, disables, meta = load_all(input_dir)
    payload, markdown = build_report(findings, disables, meta)

    (output_dir / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(markdown + "\n", encoding="utf-8")

    print(
        f"report: {payload['summary']['high']} high / "
        f"{payload['summary']['medium']} medium / "
        f"{payload['summary']['low']} low, "
        f"{len(disables)} suppression(s) -> {output_dir / 'report.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
