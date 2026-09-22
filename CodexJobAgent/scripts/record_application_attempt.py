"""Record an authorized application attempt.

This script only writes local attempt/audit records and never controls a phone
or sends an application/message.  A status of ``submitted`` is valid only when
the caller has visually confirmed a platform success page.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "data" / "runtime"
DB = RUNTIME_DIR / "job_agent.db"
QUEUE = RUNTIME_DIR / "application_queue.json"
ATTEMPTS = RUNTIME_DIR / "audit" / "application_attempts.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_queue(queue_id: str) -> dict:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    rows = [r for r in data.get("final_queue", []) if r.get("queue_id") == queue_id]
    if len(rows) != 1:
        raise SystemExit(f"queue_id not found or not unique: {queue_id}")
    return rows[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-id", required=True)
    ap.add_argument("--status", required=True, choices=["submitted", "failed", "manual_required"])
    ap.add_argument("--reason", required=True)
    ap.add_argument("--snapshot-note", required=True)
    ap.add_argument("--action", default="application_attempt_failed")
    ap.add_argument("--platform-status", default="")
    args = ap.parse_args()

    row = load_queue(args.queue_id)
    ts = now_iso()
    con = sqlite3.connect(DB)
    try:
        dbrow = con.execute(
            "SELECT job_id, platform, company, job_title, url FROM jobs WHERE url = ?",
            (row["url"],),
        ).fetchone()
        if not dbrow:
            raise SystemExit(f"job URL not found in jobs table: {row['url']}")
        db_job_id, db_platform, db_company, db_title, db_url = dbrow
        if db_company != row["company"] or db_title != row["job_title"]:
            raise SystemExit("queue/DB company or title mismatch; no record written")

        con.execute(
            "INSERT INTO applications(job_id, platform, apply_time, resume_version, status, delivery_verified, last_update) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                db_job_id,
                db_platform,
                ts,
                row["resume_template"],
                args.status,
                1 if args.status == "submitted" else 0,
                ts,
            ),
        )
        result = {
            "queue_id": args.queue_id,
            "job_id": row["job_id"],
            "db_job_id": db_job_id,
            "company": row["company"],
            "job_title": row["job_title"],
            "url": row["url"],
            "platform": db_platform,
            "resume_version": row["resume_template"],
            "status": args.status,
            "platform_status": args.platform_status,
            "reason": args.reason,
            "snapshot_note": args.snapshot_note,
            "timestamp": ts,
        }
        audit_result = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        con.execute(
            "INSERT INTO audit_events(timestamp, agent, action, target, result, requires_confirmation, user_confirmed) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                ts,
                "codex-job-agent",
                args.action,
                f"{row['company']} | {row['job_title']} | {row['url']}",
                audit_result,
                1,
                1,
            ),
        )
        con.commit()
    finally:
        con.close()

    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    with ATTEMPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
