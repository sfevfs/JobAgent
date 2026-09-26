#!/usr/bin/env python3
"""Run read-only discovery and matching for one explicit candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from candidate_pool import (
    build_queue,
    normalize_result,
    render_pool_report,
    render_queue_report,
    salary_statistics,
    upsert_database,
    write_json,
)
from job_deduplicator import deduplicate
from job_discovery import load_records, normalize_jobs


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/portable_candidate_registry.yaml"


def candidate_paths(candidate: str) -> dict[str, Path]:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    row = registry.get("candidates", {}).get(candidate)
    if not isinstance(row, dict):
        raise ValueError(f"Unknown candidate: {candidate}")
    paths: dict[str, Path] = {}
    for field in ("facts", "profile", "eligibility_policy", "onboarding_status"):
        path = (ROOT / row[field]).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise ValueError(f"Candidate {candidate} path escapes project: {field}")
        if not path.is_file():
            raise FileNotFoundError(f"Missing {candidate} {field}: {path}")
        paths[field] = path
    status = yaml.safe_load(paths["onboarding_status"].read_text(encoding="utf-8"))
    facts = yaml.safe_load(paths["facts"].read_text(encoding="utf-8"))
    if status.get("confirmed_by_user") is not True:
        raise ValueError(f"Candidate {candidate} facts are not user-confirmed")
    candidate_meta = facts.get("candidate", {}) if isinstance(facts.get("candidate", {}), dict) else {}
    source_id = candidate_meta.get("id") or candidate_meta.get("candidate_id")
    if source_id not in (None, "", candidate):
        raise ValueError(f"Candidate profile id {source_id!r} does not match selected id {candidate!r}")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, choices=["candidate_a", "candidate_b"])
    parser.add_argument("--raw", type=Path, help="Candidate-tagged JSON file or directory of raw public JDs")
    args = parser.parse_args()
    paths = candidate_paths(args.candidate)
    data_dir = ROOT / "data/runtime" / args.candidate / "discovered_jobs"
    reports_dir = ROOT / "reports/runtime" / args.candidate
    raw_path = args.raw or data_dir / "raw_source_jobs.json"
    raw = load_records(raw_path)
    if any(item.get("candidate") != args.candidate for item in raw):
        raise ValueError("Every raw JD must have the selected candidate ID; mixed or untagged inputs are refused")
    normalized = normalize_jobs(raw)
    canonical, summary = deduplicate(normalized)
    if args.candidate == "candidate_a":
        from job_matcher_candidate_a import JobMatcher
        scoring_path = ROOT / "config/scoring_candidate_a.yaml"
    else:
        from job_matcher import JobMatcher
        scoring_path = ROOT / "config/scoring.yaml"
    matcher = JobMatcher(
        resume_path=paths["facts"],
        profile_path=paths["profile"],
        scoring_path=scoring_path,
        eligibility_path=paths["eligibility_policy"],
    )
    results = [normalize_result(job, matcher.match(job)) for job in canonical]
    queue = build_queue(results)
    database = ROOT / "data/runtime" / args.candidate / "job_agent.db"
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    db_summary = upsert_database(canonical, results, database)
    salary = salary_statistics(results)
    for name, value in (
        ("normalized_jobs.json", normalized),
        ("canonical_jobs.json", canonical),
        ("matched_jobs.json", results),
        ("application_review_queue.json", queue),
        ("salary_stats.json", salary),
        ("dedup_summary.json", summary),
    ):
        write_json(data_dir / name, value)
    (reports_dir / "candidate_pool.md").write_text(
        render_pool_report(canonical, results, queue, db_summary, salary), encoding="utf-8"
    )
    (reports_dir / "application_review_queue.md").write_text(
        render_queue_report(queue), encoding="utf-8"
    )
    print(json.dumps({
        "candidate": args.candidate,
        "raw_jobs": len(raw),
        "canonical_jobs": len(canonical),
        "review_queue": len(queue),
        "data_dir": str(data_dir),
        "database": str(database),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
