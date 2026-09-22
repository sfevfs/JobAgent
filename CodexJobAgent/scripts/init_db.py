"""Initialize the local SQLite database for Codex Job Agent V1."""

from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "runtime"
DATABASE_PATH = DATA_DIR / "job_agent.db"

EXPECTED_TABLES = {
    "jobs",
    "applications",
    "conversations",
    "companies",
    "audit_events",
}

EXTENDED_JOB_COLUMNS = {
    "canonical_job_id": "TEXT",
    "same_job_group_id": "TEXT",
    "primary_track": "TEXT",
    "technical_score": "REAL CHECK (technical_score IS NULL OR technical_score BETWEEN 0 AND 100)",
    "technical_grade": "TEXT CHECK (technical_grade IS NULL OR technical_grade IN ('S', 'A', 'B', 'C', 'D'))",
    "eligibility_status": "TEXT CHECK (eligibility_status IS NULL OR eligibility_status IN ('eligible', 'uncertain', 'ineligible'))",
    "opportunity_priority": "TEXT CHECK (opportunity_priority IS NULL OR opportunity_priority IN ('P0', 'P1', 'P2', 'reject'))",
    "preference_score": "REAL CHECK (preference_score IS NULL OR preference_score BETWEEN 0 AND 100)",
    "discovered_platforms": "TEXT",
    "salary_min": "REAL",
    "salary_max": "REAL",
    "salary_months": "REAL",
    "is_campus": "INTEGER CHECK (is_campus IS NULL OR is_campus IN (0, 1))",
    "is_internship": "INTEGER CHECK (is_internship IS NULL OR is_internship IN (0, 1))",
    "graduation_year": "TEXT",
    "user_review_status": "TEXT NOT NULL DEFAULT 'pending' CHECK (user_review_status IN ('pending', 'approved', 'rejected_by_user', 'deferred'))",
    "source_status": "TEXT",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    platform_company_id TEXT,
    company TEXT NOT NULL,
    industry TEXT,
    city TEXT,
    company_size TEXT,
    financing_stage TEXT,
    priority INTEGER,
    notes TEXT,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (platform, platform_company_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    platform_job_id TEXT,
    company TEXT NOT NULL,
    job_title TEXT NOT NULL,
    city TEXT,
    salary TEXT,
    jd_text TEXT,
    url TEXT,
    score REAL CHECK (score IS NULL OR score BETWEEN 0 AND 100),
    grade TEXT CHECK (grade IS NULL OR grade IN ('S', 'A', 'B', 'C', 'D')),
    decision TEXT,
    reason TEXT,
    job_fingerprint TEXT NOT NULL UNIQUE,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (platform, platform_job_id)
);

CREATE TABLE IF NOT EXISTS applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    apply_time TEXT,
    resume_version TEXT,
    status TEXT,
    delivery_verified INTEGER NOT NULL DEFAULT 0
        CHECK (delivery_verified IN (0, 1)),
    last_update TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    platform TEXT NOT NULL,
    recruiter TEXT,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    direction TEXT CHECK (
        direction IS NULL OR direction IN ('inbound', 'outbound', 'system')
    ),
    message TEXT NOT NULL,
    message_type TEXT,
    risk_level TEXT CHECK (
        risk_level IS NULL OR risk_level IN ('L0', 'L1', 'L2', 'L3', 'L4')
    ),
    auto_sent INTEGER NOT NULL DEFAULT 0 CHECK (auto_sent IN (0, 1)),
    FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    agent TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    result TEXT,
    requires_confirmation INTEGER NOT NULL DEFAULT 0
        CHECK (requires_confirmation IN (0, 1)),
    user_confirmed INTEGER NOT NULL DEFAULT 0
        CHECK (user_confirmed IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_jobs_last_seen
    ON jobs (last_seen);
CREATE INDEX IF NOT EXISTS idx_applications_job_id
    ON applications (job_id);
CREATE INDEX IF NOT EXISTS idx_conversations_job_id_timestamp
    ON conversations (job_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp
    ON audit_events (timestamp);
"""


def initialize_database(database_path: Path = DATABASE_PATH) -> None:
    """Create the database and all V1 tables if they do not already exist."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        migrate_job_schema(connection)


def migrate_job_schema(connection: sqlite3.Connection) -> None:
    """Add the V1 discovery fields without deleting or rewriting old rows."""

    existing = {
        row[1]
        for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
    }
    for name, declaration in EXTENDED_JOB_COLUMNS.items():
        if name not in existing:
            connection.execute(
                f"ALTER TABLE jobs ADD COLUMN {name} {declaration}"
            )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_canonical_job_id ON jobs (canonical_job_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_same_job_group_id ON jobs (same_job_group_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_opportunity_priority ON jobs (opportunity_priority)"
    )


def list_user_tables(database_path: Path = DATABASE_PATH) -> set[str]:
    """Return application table names, excluding SQLite internal tables."""
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    return {row[0] for row in rows}


def main() -> None:
    initialize_database()
    tables = list_user_tables()
    missing_tables = EXPECTED_TABLES - tables
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise RuntimeError(f"Database initialization incomplete; missing: {missing}")

    print(f"Database initialized: {DATABASE_PATH}")
    print(f"Tables: {', '.join(sorted(tables))}")


if __name__ == "__main__":
    main()
