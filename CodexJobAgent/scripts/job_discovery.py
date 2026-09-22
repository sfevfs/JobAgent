#!/usr/bin/env python3
"""Read-only public-job discovery input and deterministic normalization.

This module never opens an application or communication control.  It accepts
JSON objects/arrays or a directory of JSON files, normalizes the observable
fields, preserves the original source data, and computes a stable fingerprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "data" / "runtime" / "discovered_jobs"
DEFAULT_INPUT = RUNTIME_DIR / "raw_source_jobs.json"
DEFAULT_OUTPUT = RUNTIME_DIR / "normalized_jobs.json"

REQUIRED_FIELDS = (
    "job_id",
    "platform",
    "platform_job_id",
    "company",
    "job_title",
    "city",
    "salary",
    "job_type",
    "graduation_year",
    "jd_text",
    "url",
)


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("–", "-").replace("—", "-").replace("‑", "-")
    return re.sub(r"\s+", " ", text).strip()


def normalized_key(value: Any) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
    return text


def company_group(company: Any, legal_entity: Any = None) -> str:
    """Conservative company grouping; legal entities remain in the record."""

    value = normalize_text(legal_entity or company)
    aliases = (
        ("华为", "华为"),
        ("huawei", "华为"),
        ("小米", "小米"),
        ("xiaomi", "小米"),
        ("oppo", "OPPO"),
        ("中兴", "中兴通讯"),
        ("阿里", "阿里巴巴"),
        ("alibaba", "阿里巴巴"),
        ("字节", "字节跳动"),
        ("bytedance", "字节跳动"),
        ("腾讯", "腾讯"),
        ("tencent", "腾讯"),
        ("百度", "百度"),
        ("baidu", "百度"),
    )
    lowered = value.lower()
    for token, group in aliases:
        if token in lowered:
            return group
    return normalize_text(company)


def parse_salary(value: Any) -> dict[str, float | None]:
    text = normalize_text(value)
    if not text:
        return {"salary_min": None, "salary_max": None, "salary_months": None}
    numbers = [float(x) for x in re.findall(r"(?<!\d)(\d+(?:\.\d+)?)", text)]
    salary_min = salary_max = None
    if numbers:
        if len(numbers) >= 2 and any(token in text for token in ("-", "~", "至", "到")):
            salary_min, salary_max = numbers[0], numbers[1]
        else:
            salary_min = salary_max = numbers[0]
    months = None
    month_match = re.search(r"(?:\*|x|×)\s*(\d+(?:\.\d+)?)\s*薪", text, re.I)
    if month_match:
        months = float(month_match.group(1))
    return {
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_months": months,
    }


def infer_track_hint(job: dict[str, Any]) -> str | None:
    text = normalize_text(f"{job.get('job_title', '')} {job.get('jd_text', '')}").lower()
    if any(token in text for token in ("通信", "csi", "mimo", "phy", "信道", "基带", "雷达")):
        return "communication_ai"
    if any(token in text for token in ("医学", "医疗", "medical", "超声", "ct", "mri")):
        return "medical_cv"
    if any(token in text for token in ("大模型", "llm", "多模态", "推荐", "语音", "深度学习", "ai")):
        return "general_ai"
    if any(token in text for token in ("视觉", "图像", "cv", "检测", "分割")):
        return "medical_cv"
    return None


def load_records(path: Path) -> list[dict[str, Any]]:
    paths = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not paths:
        raise FileNotFoundError(f"No JSON source files found: {path}")
    records: list[dict[str, Any]] = []
    for source_path in paths:
        with source_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = [payload]
        else:
            raise ValueError(f"Source must be a JSON object or array: {source_path}")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Each source item must be an object: {source_path}")
            records.append(item)
    return records


def normalize_job(job: dict[str, Any], observed_at: str | None = None) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in job]
    if missing:
        raise ValueError(f"Job {job.get('job_id')} lacks fields: {missing}")
    checked_at = normalize_text(
        observed_at or job.get("source_checked_at") or job.get("last_seen")
    )
    if not checked_at:
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    legal_entity = normalize_text(job.get("legal_entity") or job.get("company"))
    company = normalize_text(job.get("company"))
    title = normalize_text(job.get("job_title"))
    city = normalize_text(job.get("city"))
    jd_text = normalize_text(job.get("jd_text"))
    fingerprint_payload = "|".join(
        (normalized_key(company_group(company, legal_entity)), normalized_key(title), normalized_key(city), normalized_key(jd_text))
    )
    fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
    salary = parse_salary(job.get("salary"))
    record = dict(job)
    record.update(
        {
            "job_id": normalize_text(job.get("job_id")),
            "platform": normalize_text(job.get("platform")),
            "platform_job_id": normalize_text(job.get("platform_job_id")),
            "company": company,
            "legal_entity": legal_entity,
            "company_group": company_group(company, legal_entity),
            "job_title": title,
            "city": city,
            "salary": normalize_text(job.get("salary")),
            "job_type": normalize_text(job.get("job_type")),
            "graduation_year": normalize_text(
                job.get("graduation_year") or job.get("graduation_cohort")
            ),
            "jd_text": jd_text,
            "url": normalize_text(job.get("url")),
            "first_seen": normalize_text(job.get("first_seen") or checked_at),
            "last_seen": normalize_text(job.get("last_seen") or checked_at),
            "discovered_platforms": sorted(
                set(job.get("discovered_platforms") or [normalize_text(job.get("platform"))])
            ),
            "job_fingerprint": fingerprint,
            "source_status": normalize_text(
                job.get("source_status") or "public_jd_observed"
            ),
            "track_hint": job.get("track_hint") or infer_track_hint(job),
            **salary,
        }
    )
    return record


def normalize_jobs(records: Iterable[dict[str, Any]], observed_at: str | None = None) -> list[dict[str, Any]]:
    normalized = [normalize_job(item, observed_at=observed_at) for item in records]
    normalized.sort(key=lambda item: (item["job_id"], item["job_fingerprint"]))
    return normalized


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--observed-at", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    records = load_records(args.input)
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        records = records[: args.limit]
    normalized = normalize_jobs(records, observed_at=args.observed_at)
    write_json(args.output, normalized)
    print(json.dumps({"input_records": len(records), "normalized_records": len(normalized), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
