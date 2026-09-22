"""Record a visually confirmed BOSS bulk application/contact action.

The phone action is performed separately through mobile-use.  This helper only
persists the confirmed result in the local SQLite database, an append-only JSONL
attempt log, and audit_events.  It never controls the phone, sends messages, or
uploads a resume.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "data" / "runtime"
DB = RUNTIME_DIR / "job_agent.db"
ATTEMPTS = RUNTIME_DIR / "audit" / "boss_application_attempts.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def fingerprint(company: str, title: str, city: str) -> str:
    key = "|".join((company.strip().lower(), title.strip().lower(), city.strip().lower()))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def add_audit(con: sqlite3.Connection, ts: str, action: str, target: str, result: dict) -> None:
    con.execute(
        "INSERT INTO audit_events(timestamp, agent, action, target, result, requires_confirmation, user_confirmed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, "codex-job-agent", action, target,
         json.dumps(result, ensure_ascii=False, separators=(",", ":")), 1, 1),
    )


def normalize_auto_greeting(value: str) -> str:
    """Accept a literal greeting or a boolean marker from the CLI.

    Persist only the exact text observed on screen. Boolean markers are not
    accepted because platform greetings can contain candidate-specific facts.
    """
    marker = (value or "").strip()
    if marker.lower() in {"", "false", "0", "no", "none", "null"}:
        return ""
    if marker.lower() in {"true", "1", "yes", "on"}:
        raise ValueError("Pass the exact observed greeting text, not a boolean marker.")
    return marker


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--city", default="")
    ap.add_argument("--salary", default="")
    ap.add_argument("--track", required=True, choices=["communication_ai", "medical_cv", "general_ai"])
    ap.add_argument("--resume-version", required=True)
    ap.add_argument("--status", required=True, choices=["submitted", "failed", "manual_required"])
    ap.add_argument("--reason", required=True)
    ap.add_argument("--snapshot-note", required=True)
    ap.add_argument("--platform", default="BOSS直聘")
    ap.add_argument("--platform-job-id", default="")
    ap.add_argument("--job-url", default="")
    ap.add_argument("--jd-summary", default="")
    ap.add_argument("--recruiter", default="")
    ap.add_argument("--search-query", default="")
    ap.add_argument("--technical-score", type=float, default=None)
    ap.add_argument("--technical-grade", default="")
    ap.add_argument("--eligibility", default="eligible", choices=["eligible", "uncertain", "ineligible"])
    ap.add_argument("--priority", default="P1", choices=["P0", "P1", "P2", "reject"])
    ap.add_argument("--auto-greeting", default="")
    ap.add_argument("--template-message", default="")
    args = ap.parse_args()
    auto_greeting = normalize_auto_greeting(args.auto_greeting)

    ts = now_iso()
    fp = fingerprint(args.company, args.title, args.city)
    target = f"{args.company} | {args.title} | {args.city}"
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM jobs WHERE job_fingerprint = ? OR (company = ? AND job_title = ? AND COALESCE(city,'') = ?) "
            "ORDER BY job_id LIMIT 1",
            (fp, args.company, args.title, args.city),
        ).fetchone()
        if row is None:
            observed_id = args.platform_job_id or f"boss-observed-{fp[:12]}"
            source_text = args.title + " " + args.jd_summary + " " + args.search_query
            graduation_years = re.findall(r"\b20\d{2}\b", source_text)
            campus = int(bool(graduation_years) or any(x in source_text for x in ("校招", "校园", "应届", "实习")))
            internship = int("实习" in source_text)
            con.execute(
                "INSERT INTO jobs(platform, platform_job_id, company, job_title, city, salary, jd_text, url, "
                "score, grade, decision, reason, job_fingerprint, first_seen, last_seen, canonical_job_id, "
                "same_job_group_id, primary_track, technical_score, technical_grade, eligibility_status, "
                "opportunity_priority, preference_score, discovered_platforms, is_campus, is_internship, "
                "graduation_year, user_review_status, source_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (args.platform, observed_id, args.company, args.title, args.city, args.salary, args.jd_summary,
                 args.job_url or f"boss://observed/{fp[:16]}", args.technical_score, args.technical_grade or None,
                 "selected" if args.status == "submitted" else "review", args.reason, fp, ts, ts, observed_id,
                 observed_id, args.track, args.technical_score, args.technical_grade or None, args.eligibility,
                 args.priority, None, json.dumps([args.platform], ensure_ascii=False), campus, internship,
                 graduation_years[0] if graduation_years else None, "pending", "observed_open"),
            )
            job_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        else:
            job_id = int(row["job_id"])
            con.execute(
                "UPDATE jobs SET last_seen = ?, source_status = COALESCE(source_status, 'observed_open'), "
                "primary_track = COALESCE(primary_track, ?), eligibility_status = COALESCE(eligibility_status, ?), "
                "opportunity_priority = COALESCE(opportunity_priority, ?) WHERE job_id = ?",
                (ts, args.track, args.eligibility, args.priority, job_id),
            )

        existing = con.execute(
            "SELECT application_id, status FROM applications WHERE job_id = ? ORDER BY application_id DESC",
            (job_id,),
        ).fetchall()
        already_contacted = con.execute(
            "SELECT 1 FROM conversations WHERE job_id = ? AND direction = 'outbound' "
            "AND message_type IN ('platform_auto_greeting','initial_template') LIMIT 1",
            (job_id,),
        ).fetchone() is not None
        if any(r["status"] == "submitted" for r in existing) or already_contacted:
            result = {
                "company": args.company, "job_title": args.title, "city": args.city,
                "status": "duplicate_skipped", "job_id": job_id, "reason": "已有成功投递或首条沟通审计，未重复点击",
                "timestamp": ts,
            }
            add_audit(con, ts, "application_duplicate_skipped", target, result)
            con.commit()
        else:
            con.execute(
                "INSERT INTO applications(job_id, platform, apply_time, resume_version, status, delivery_verified, last_update) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, args.platform, ts, args.resume_version, args.status,
                 1 if args.status == "submitted" else 0, ts),
            )
            result = {
                "company": args.company, "job_title": args.title, "city": args.city,
                "salary": args.salary, "track": args.track, "resume_version": args.resume_version,
                "status": args.status, "job_id": job_id, "platform": args.platform,
                "platform_job_id": args.platform_job_id or None, "job_url": args.job_url or None,
                "reason": args.reason, "snapshot_note": args.snapshot_note,
                "recruiter": args.recruiter or None, "search_query": args.search_query or None,
                "auto_greeting_sent": bool(auto_greeting), "template_message_sent": bool(args.template_message),
                "timestamp": ts,
            }
            add_audit(con, ts, "application_precheck_verified", target,
                      {**result, "eligibility": args.eligibility, "priority": args.priority})
            add_audit(con, ts, "application_submitted" if args.status == "submitted" else
                      ("application_attempt_failed" if args.status == "failed" else "application_manual_required"),
                      target, result)
            for message, msg_type, auto_sent in (
                (auto_greeting, "platform_auto_greeting", 1),
                (args.template_message, "initial_template", 0),
            ):
                if message:
                    con.execute(
                        "INSERT INTO conversations(job_id, platform, recruiter, timestamp, direction, message, message_type, risk_level, auto_sent) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (job_id, args.platform, args.recruiter or None, ts, "outbound", message, msg_type, "L1", auto_sent),
                    )
                    add_audit(con, ts, "message_sent", target,
                              {"job_id": job_id, "message_type": msg_type, "auto_sent": bool(auto_sent), "message": message})
            con.commit()
    finally:
        con.close()

    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    with ATTEMPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
