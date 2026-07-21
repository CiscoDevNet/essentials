#!/usr/bin/env python3
"""Validate 1–5 markdown summary bullets for the summarize-change-log skill."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MESSAGE_LENGTH_LIMIT = 50
MAX_BULLETS = 5

BULLET_PATTERN = re.compile(r"^\s*-\s+\*\*([^*]+)\*\*\s*(—|-)\s*")
LIST_LINE_PATTERN = re.compile(r"^\s*-\s+")
CO_AUTHOR_PATTERN = re.compile(r"^Co-authored-by:")

VAGUE_SUBJECT_PATTERNS = (
    re.compile(r"[Aa][Dd][Dd][Rr][Ee][Ss][Ss]\s+[Pp][Rr]"),
    re.compile(r"[Rr][Ee][Vv][Ii][Ee][Ww]\s+[Cc][Oo][Mm][Mm][Ee][Nn][Tt]"),
    re.compile(r"(^|[^a-zA-Z0-9])[Pp][Oo][Rr][Tt]\s+.*[Ff][Rr][Oo][Mm]\s+#"),
    re.compile(r"[Ff][Oo][Ll][Ll][Oo][Ww]\s+[Uu][Pp]"),
    re.compile(r"[Cc][Hh][Ee][Rr][Rr][Yy][- ][Pp][Ii][Cc][Kk]"),
)


class ValidationError(Exception):
    """Summary markdown failed skill validation."""


@dataclass(frozen=True)
class SummaryDocument:
    """Parsed bullet subjects and optional Co-authored-by footers."""

    subjects: list[str]
    footers: list[str]


def find_repo_root(start: Path) -> Path:
    """Walk parents until a pyproject.toml with Commitizen config is found."""
    path = start.resolve()
    while True:
        pyproject = path / "pyproject.toml"
        if pyproject.is_file() and "[tool.commitizen]" in pyproject.read_text(
            encoding="utf-8"
        ):
            return path
        if path.parent == path:
            raise ValidationError(
                "could not find repo root with [tool.commitizen] in pyproject.toml"
            )
        path = path.parent


def is_vague_subject(subject: str) -> bool:
    """Return True when the subject matches a banned process/meta phrase."""
    return any(pattern.search(subject) for pattern in VAGUE_SUBJECT_PATTERNS)


def parse_document(text: str) -> SummaryDocument:
    """Parse bullets and Co-authored-by footers, enforcing layout rules."""
    subjects: list[str] = []
    footers: list[str] = []
    saw_bullet = False
    saw_footer = False
    prev_was_blank = False

    for line in text.splitlines():
        if not line.strip():
            if saw_bullet and not saw_footer:
                prev_was_blank = True
            continue

        bullet_match = BULLET_PATTERN.match(line)
        if bullet_match:
            if saw_footer:
                raise ValidationError("Co-authored-by footer must follow all bullets")
            subjects.append(bullet_match.group(1))
            saw_bullet = True
            prev_was_blank = False
            continue

        if LIST_LINE_PATTERN.match(line):
            raise ValidationError(
                "malformed bullet(s); expected - **type(scope): subject** — ..."
            )

        if CO_AUTHOR_PATTERN.match(line):
            if not saw_bullet:
                raise ValidationError("Co-authored-by footer must follow bullets")
            if not saw_footer and not prev_was_blank:
                raise ValidationError(
                    "blank line required before Co-authored-by footer"
                )
            footers.append(line)
            saw_footer = True
            prev_was_blank = False
            continue

        raise ValidationError(f"unexpected non-bullet line: {line}")

    return SummaryDocument(subjects=subjects, footers=footers)


def run_commitizen_check(subject: str, repo_root: Path) -> None:
    """Run ``uv run cz check`` for a single Conventional Commit subject."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "cz",
            "check",
            "-m",
            subject,
            "-l",
            str(MESSAGE_LENGTH_LIMIT),
        ],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        raise ValidationError(f"failed Conventional Commits check for: {subject}")


def validate_summary_text(text: str, *, repo_root: Path) -> int:
    """Validate summary markdown. Returns bullet count on success."""
    document = parse_document(text)
    bullet_count = len(document.subjects)

    if bullet_count == 0:
        raise ValidationError(
            "no bullets found (expected: - **type(scope): subject** — ...)"
        )
    if bullet_count > MAX_BULLETS:
        raise ValidationError(
            f"too many bullets ({bullet_count}); maximum is {MAX_BULLETS}"
        )

    for subject in document.subjects:
        if is_vague_subject(subject):
            raise ValidationError(
                f"vague subject (describe what changed, not process): {subject}"
            )
        run_commitizen_check(subject, repo_root)

    return bullet_count


def _read_input(path: Path | None) -> str:
    if path is None:
        return sys.stdin.read()
    if not path.is_file():
        raise ValidationError(f"file not found: {path}")
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate summarize-change-log markdown bullets.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Summary markdown file (stdin when omitted)",
    )
    args = parser.parse_args(argv)

    try:
        input_path = Path(args.path).resolve() if args.path else None
        text = _read_input(input_path)
        script_dir = Path(__file__).resolve().parent
        repo_root = find_repo_root(script_dir)
        bullet_count = validate_summary_text(text, repo_root=repo_root)
    except ValidationError as exc:
        print(f"validate-summary: {exc}", file=sys.stderr)
        return 1

    print(f"validate-summary: OK ({bullet_count} bullet(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
