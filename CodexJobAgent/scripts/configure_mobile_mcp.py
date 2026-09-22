#!/usr/bin/env python3
"""Write a project-scoped Codex MCP configuration for the bundled mobile server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / ".codex" / "config.toml"
PYTHON_PATH = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite an existing config")
    args = parser.parse_args(argv)

    if not PYTHON_PATH.exists():
        raise FileNotFoundError("Run bootstrap.ps1 -IncludeMobile before configuring MCP.")
    if CONFIG_PATH.exists() and not args.force:
        print(f"CONFIG_EXISTS: {CONFIG_PATH}")
        print("Merge the mobile-use table manually or rerun with --force after making a backup.")
        return 3

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "# Generated locally. Review before trusting this project.",
            "[mcp_servers.mobile_use]",
            f"command = {quoted(str(PYTHON_PATH))}",
            'args = ["-m", "mobile_use_mcp"]',
            f"cwd = {quoted(str(PROJECT_ROOT))}",
            "startup_timeout_sec = 30",
            "tool_timeout_sec = 60",
            "enabled = true",
            "",
        ]
    )
    CONFIG_PATH.write_text(content, encoding="utf-8", newline="\n")
    print(f"MCP_CONFIG_WRITTEN: {CONFIG_PATH}")
    print("Restart Codex and verify the server before using phone actions.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"MCP_CONFIG_ERROR: {exc}", file=sys.stderr)
        raise

