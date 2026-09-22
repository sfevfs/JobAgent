#!/usr/bin/env python3
"""Idempotently extend the local jobs table for discovery and review metadata."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from init_db import DATABASE_PATH, initialize_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    args = parser.parse_args()
    initialize_database(args.database)
    with sqlite3.connect(args.database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(jobs)")]
        print({"database": str(args.database), "job_columns": columns})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
