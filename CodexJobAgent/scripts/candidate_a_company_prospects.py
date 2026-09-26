#!/usr/bin/env python3
"""Review product-led company leads for candidate_a without contacting a platform."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from build_candidate_a_discovery_plan import DEFAULT_OUTPUT, STRATEGY, read_yaml


def review_prospects(records: list[dict[str, Any]], strategy: dict, as_of: date) -> list[dict[str, Any]]:
    scenarios = {
        item["id"]: item
        for track in strategy["scenarios"].values()
        for item in track
    }
    accepted_sources = set(strategy["company_review"]["accepted_product_sources"])
    preferred_sizes = strategy["company_review"]["preferred_company_sizes"]
    output: list[dict[str, Any]] = []
    for index, record in enumerate(records, 1):
        if record.get("candidate") != "candidate_a":
            raise ValueError(f"Company lead {index} must explicitly identify candidate candidate_a")
        scenario_id = record.get("product_scenario_id")
        if scenario_id not in scenarios:
            raise ValueError(f"Unknown product scenario in lead {index}: {scenario_id}")
        if not str(record.get("company") or "").strip():
            raise ValueError(f"Company lead {index} has no company name")
        checks: list[str] = []
        source_url = str(record.get("product_evidence_url") or "").strip()
        source_type = record.get("product_evidence_source_type")
        evidence = str(record.get("product_evidence_summary") or "").strip()
        observed = str(record.get("observed_at") or "")[:10]
        if not source_url.startswith(("https://", "http://")):
            checks.append("missing_product_source_url")
        if source_type not in accepted_sources:
            checks.append("product_source_requires_review")
        if not evidence:
            checks.append("missing_product_evidence_summary")
        try:
            observed_date = date.fromisoformat(observed)
            if observed_date > as_of or (as_of - observed_date).days > 30:
                checks.append("product_evidence_date_out_of_window")
        except ValueError:
            checks.append("missing_or_invalid_observation_date")
        size = str(record.get("company_size") or "未知").strip()
        if not checks and size == "0-20人":
            checks.append("micro_company_verify_full_jd_on_boss")
        status = "ready_for_boss_lookup" if not checks or checks == ["micro_company_verify_full_jd_on_boss"] else "needs_product_review"
        output.append({
            **record,
            "company_size": size,
            "product_area": scenarios[scenario_id]["product_area"],
            "evidence_level": scenarios[scenario_id]["evidence_level"],
            "company_size_preferred": size in preferred_sizes,
            "review_status": status,
            "review_checks": checks,
            "next_step": "在 BOSS 按公司名核对当前具体岗位与完整 JD" if status == "ready_for_boss_lookup" else "补齐可核对的公司产品证据",
            "apply_authorized": False,
        })
    output.sort(key=lambda item: (
        item["review_status"] != "ready_for_boss_lookup",
        preferred_sizes.index(item["company_size"]) if item["company_size"] in preferred_sizes else len(preferred_sizes),
        item["company"],
    ))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, choices=["candidate_a"])
    parser.add_argument("--input", type=Path, required=True, help="JSON array of observed company leads")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "company_prospects_review.json")
    args = parser.parse_args()
    records = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError("Company lead input must be a JSON array of objects")
    output = review_prospects(records, read_yaml(STRATEGY), args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"leads": len(output), "ready_for_boss_lookup": sum(item["review_status"] == "ready_for_boss_lookup" for item in output), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
