#!/usr/bin/env python3
"""Conservative cross-platform job deduplication for the local candidate pool."""

from __future__ import annotations

import argparse
import hashlib
import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from job_discovery import company_group, normalize_text, normalized_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "data" / "runtime" / "discovered_jobs"
DEFAULT_INPUT = RUNTIME_DIR / "normalized_jobs.json"
DEFAULT_OUTPUT = RUNTIME_DIR / "canonical_jobs.json"

PLATFORM_RANK = {
    "official_company_site": 0,
    "公司官网": 0,
    "boss": 1,
    "boss直聘": 1,
    "智联招聘": 2,
    "zhaopin": 2,
    "51job": 3,
    "前程无忧": 3,
    "nowcoder": 4,
    "牛客": 4,
    "高校就业网": 5,
}


def platform_rank(platform: Any) -> int:
    value = normalize_text(platform).lower()
    for token, rank in PLATFORM_RANK.items():
        if token in value:
            return rank
    return 9


def city_tokens(city: Any) -> set[str]:
    value = normalize_text(city)
    return {token for token in __import__("re").split(r"[/、,，;；|\s]+", value) if token}


def title_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    return SequenceMatcher(
        None,
        normalized_key(left.get("job_title")),
        normalized_key(right.get("job_title")),
    ).ratio()


def jd_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    return SequenceMatcher(
        None,
        normalized_key(left.get("jd_text")),
        normalized_key(right.get("jd_text")),
    ).ratio()


def same_city(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_tokens = city_tokens(left.get("city"))
    right_tokens = city_tokens(right.get("city"))
    return bool(left_tokens and right_tokens and left_tokens.intersection(right_tokens))


def is_duplicate(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("job_fingerprint") and left.get("job_fingerprint") == right.get("job_fingerprint"):
        return True
    if company_group(left.get("company"), left.get("legal_entity")).lower() != company_group(
        right.get("company"), right.get("legal_entity")
    ).lower():
        return False
    title_score = title_similarity(left, right)
    jd_score = jd_similarity(left, right)
    if same_city(left, right):
        return title_score >= 0.82 and jd_score >= 0.45
    # A multi-city posting may be represented by one city on one platform.
    return title_score >= 0.94 and jd_score >= 0.80


def group_records(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for record in records:
        for group in groups:
            if any(is_duplicate(record, existing) for existing in group):
                group.append(record)
                break
        else:
            groups.append([record])
    return groups


def stable_id(prefix: str, records: list[dict[str, Any]]) -> str:
    seed = "|".join(
        sorted(
            f"{record.get('platform')}:{record.get('platform_job_id')}:{record.get('job_fingerprint')}"
            for record in records
        )
    )
    return f"{prefix}-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups = group_records(sorted(records, key=lambda item: item.get("job_id", "")))
    canonical_jobs: list[dict[str, Any]] = []
    duplicate_records = 0
    for group in groups:
        ordered = sorted(
            group,
            key=lambda item: (
                platform_rank(item.get("platform")),
                item.get("first_seen", ""),
                item.get("job_id", ""),
            ),
        )
        canonical = dict(ordered[0])
        canonical_id = stable_id("canonical", group)
        group_id = stable_id("same", group)
        duplicate_platform_records = [
            {
                "job_id": item.get("job_id"),
                "platform": item.get("platform"),
                "platform_job_id": item.get("platform_job_id"),
                "url": item.get("url"),
            }
            for item in ordered[1:]
        ]
        duplicate_records += len(duplicate_platform_records)
        discovered_platforms = sorted(
            {
                platform
                for item in group
                for platform in (item.get("discovered_platforms") or [item.get("platform")])
                if platform
            }
        )
        canonical.update(
            {
                "canonical_job_id": canonical_id,
                "same_job_group_id": group_id,
                "discovered_platforms": discovered_platforms,
                "duplicate_platform_records": duplicate_platform_records,
                "duplicate_count": len(duplicate_platform_records),
                "canonical_source_platform": canonical.get("platform"),
                "canonical_source_url": canonical.get("url"),
            }
        )
        canonical_jobs.append(canonical)
    canonical_jobs.sort(key=lambda item: (item.get("canonical_job_id", ""), item.get("job_id", "")))
    summary = {
        "raw_count": len(records),
        "canonical_count": len(canonical_jobs),
        "duplicate_record_count": duplicate_records,
        "duplicate_group_count": sum(1 for group in groups if len(group) > 1),
        "canonical_jobs_with_duplicates": sum(
            1 for job in canonical_jobs if job.get("duplicate_count", 0) > 0
        ),
    }
    return canonical_jobs, summary


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    with args.input.open("r", encoding="utf-8") as handle:
        records = json.load(handle)
    if not isinstance(records, list):
        raise ValueError("Normalized input must be a JSON array")
    canonical, summary = deduplicate(records)
    write_json(args.output, canonical)
    print(json.dumps({**summary, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
