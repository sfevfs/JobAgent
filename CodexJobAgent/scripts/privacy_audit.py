#!/usr/bin/env python3
"""Conservative pre-share scan for private data and machine-bound artifacts."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".local",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
EXCLUDED_PREFIXES = {
    Path("data/runtime"),
    Path("reports/runtime"),
    Path("logs"),
}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".jsonl",
    ".toml",
    ".py",
    ".ps1",
    ".cfg",
    ".ini",
}
PATTERNS = {
    "absolute_windows_user_path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+", re.I),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "mainland_phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "mainland_id": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "secret_assignment": re.compile(
        r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd)"
        r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{8,}"
    ),
}


def is_excluded(relative: Path) -> bool:
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return True
    return any(relative == prefix or prefix in relative.parents for prefix in EXCLUDED_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forbidden-term",
        action="append",
        default=[],
        help="extra literal name, organization or identifier that must not appear",
    )
    args = parser.parse_args()

    findings: list[tuple[str, Path, int]] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if is_excluded(relative) or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append((label, relative, line))
        lowered = text.casefold()
        for term in args.forbidden_term:
            if term and term.casefold() in lowered:
                findings.append(("forbidden_term", relative, 0))

    forbidden_dirs = [
        PROJECT_ROOT / ".local",
        PROJECT_ROOT / ".venv",
        PROJECT_ROOT / "data" / "runtime",
        PROJECT_ROOT / "reports" / "runtime",
    ]
    for directory in forbidden_dirs:
        if directory.exists() and any(directory.rglob("*")):
            findings.append(("private_directory_not_empty", directory.relative_to(PROJECT_ROOT), 0))

    if findings:
        print("PRIVACY_AUDIT_FAILED")
        for label, path, line in sorted(set(findings)):
            suffix = f":{line}" if line else ""
            print(f"- {label}: {path}{suffix}")
        return 2

    print("PRIVACY_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

