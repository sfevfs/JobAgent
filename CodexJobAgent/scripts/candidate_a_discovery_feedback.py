#!/usr/bin/env python3
"""Compare verified discovery yield and suggest the next balanced candidate_a search round."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from build_candidate_a_discovery_plan import DEFAULT_OUTPUT, PRIMARY_TRACKS, STRATEGY, read_yaml
from source_quality import assess_source_quality


METHODS = ("role_led", "product_led")


def usable_source_evidence(match: dict, observed_at: str, as_of: date) -> tuple[bool, bool]:
    """Return (usable for yield, mobile detail without a durable job URL)."""
    if not assess_source_quality(match, as_of)["needs_source_recheck"]:
        return True, False
    if match.get("source") != "mobile_boss_live":
        return False, False
    if match.get("source_status") not in {"live_detail_observed_full_jd", "live_detail_observed_full_enough"}:
        return False, False
    if match.get("posting_state") != "active_detail_observed":
        return False, False
    if not match.get("company") or not match.get("job_title") or len(str(match.get("jd_text") or "")) < 80:
        return False, False
    try:
        observed_date = date.fromisoformat(observed_at[:10])
    except ValueError:
        return False, False
    if not 0 <= (as_of - observed_date).days <= 7:
        return False, False
    if "product_led" in (match.get("discovery_methods") or [match.get("discovery_method")]) and not (match.get("company_product_evidence_urls") or match.get("product_evidence_url")):
        return False, False
    return True, not bool(match.get("url"))


def next_round_slots(plan: dict, preferred_method: str | None, searches_per_track: int) -> list[dict[str, Any]]:
    if searches_per_track != 10:
        raise ValueError("Next-round allocation requires 10 main searches per track")
    dominant = preferred_method or "role_led"
    minority = "product_led" if dominant == "role_led" else "role_led"
    method_order = [method for _ in range(4) for method in (dominant, minority)]
    method_order += [dominant, dominant] if preferred_method else ["role_led", "product_led"]
    role_queries = {
        track: plan["remaining_original_role_queries"][track] + [
            row["job_query"] for row in plan["searches"]
            if row["track"] == track and row["discovery_method"] == "role_led"
        ] for track in PRIMARY_TRACKS
    }
    product_rows = {
        track: [row for row in plan["searches"] if row["track"] == track and row["discovery_method"] == "product_led"]
        for track in PRIMARY_TRACKS
    }
    indexes = defaultdict(int)
    slots: list[dict[str, Any]] = []
    for method in method_order:
        for track in PRIMARY_TRACKS:
            index = indexes[(track, method)]
            indexes[(track, method)] += 1
            if method == "role_led":
                query = role_queries[track][index % len(role_queries[track])]
                slots.append({"sequence": len(slots) + 1, "track": track, "discovery_method": method, "job_query": query, "company_query": None, "product_scenario_id": None})
            else:
                row = product_rows[track][index % len(product_rows[track])]
                slots.append({"sequence": len(slots) + 1, "track": track, "discovery_method": method, "job_query": row["job_query"], "company_query": row["company_query"], "product_scenario_id": row["product_scenario_id"], "instruction": "用该产品场景寻找新的公司，记录产品证据后在 BOSS 按公司名找岗位"})
    return slots


def evaluate(plan: dict, completed: list[dict], matches: list[dict], strategy: dict, as_of: date) -> dict[str, Any]:
    plan_rows = {row["sequence"]: row for row in plan["searches"]}
    seen_sequences: set[int] = set()
    main_turns: list[dict[str, Any]] = []
    for turn in completed:
        if turn.get("candidate") != "candidate_a":
            raise ValueError("Every completed search must explicitly identify candidate candidate_a")
        sequence = turn.get("sequence")
        if sequence not in plan_rows or sequence in seen_sequences:
            raise ValueError(f"Unknown or repeated search sequence: {sequence}")
        seen_sequences.add(sequence)
        if turn.get("status") != "completed":
            continue
        try:
            observed_date = date.fromisoformat(str(turn.get("observed_at") or "")[:10])
            if observed_date > as_of:
                raise ValueError
        except ValueError:
            raise ValueError(f"Search {sequence} needs a valid observed_at on or before {as_of}") from None
        row = plan_rows[sequence]
        if row["discovery_method"] in METHODS:
            ids = turn.get("canonical_job_ids")
            if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
                raise ValueError(f"Search {sequence} needs canonical_job_ids as a string list")
            main_turns.append({**turn, "discovery_method": row["discovery_method"], "track": row["track"]})
    window_size = int(strategy["search_balance"]["feedback_window_main_searches"])
    complete_windows = len(main_turns) // window_size
    window = main_turns[(complete_windows - 1) * window_size:complete_windows * window_size] if complete_windows else []
    if len(window) < window_size:
        return {"status": "awaiting_searches", "completed_main_searches": len(main_turns), "required_main_searches": window_size, "recommendation": "维持岗位名称与产品场景各 50%；先完成本轮搜索并记录 canonical 岗位编号", "next_round_slots": []}
    counts = {method: sum(turn["discovery_method"] == method for turn in window) for method in METHODS}
    if min(counts.values()) < 2 or len({turn["track"] for turn in window}) < 2:
        return {"status": "unbalanced_window", "completed_main_searches": len(main_turns), "window_sequences": [turn["sequence"] for turn in window], "recommendation": "本窗口两条路线或技术主线覆盖不足，继续按原计划搜索", "next_round_slots": []}
    by_id = {str(match.get("canonical_job_id")): match for match in matches if match.get("canonical_job_id")}
    discovered_by: dict[str, set[str]] = defaultdict(set)
    observed_by: dict[str, str] = {}
    for turn in window:
        for canonical_id in turn["canonical_job_ids"]:
            discovered_by[canonical_id].add(turn["discovery_method"])
            observed_by[canonical_id] = max(observed_by.get(canonical_id, ""), str(turn["observed_at"]))
    credited = {method: 0.0 for method in METHODS}
    verified_ids: list[str] = []
    needs_recheck: list[str] = []
    unmatched_ids: list[str] = []
    mobile_no_url_ids: list[str] = []
    for canonical_id, methods in discovered_by.items():
        match = by_id.get(canonical_id)
        if not match:
            unmatched_ids.append(canonical_id)
            continue
        if match.get("eligibility", {}).get("status") != "eligible" or match.get("opportunity_priority") not in {"P0", "P1"}:
            continue
        usable, mobile_no_url = usable_source_evidence(match, observed_by[canonical_id], as_of)
        if not usable:
            needs_recheck.append(canonical_id)
            continue
        verified_ids.append(canonical_id)
        if mobile_no_url:
            mobile_no_url_ids.append(canonical_id)
        for method in methods:
            credited[method] += 1 / len(methods)
    yields = {method: round(credited[method] / counts[method], 3) for method in METHODS}
    minimum = int(strategy["search_balance"]["minimum_verified_jobs_to_shift"])
    preferred: str | None = None
    if len(verified_ids) >= minimum and abs(yields["role_led"] - yields["product_led"]) >= 0.25:
        preferred = max(METHODS, key=lambda method: yields[method])
    share = {"role_led": 0.5, "product_led": 0.5}
    if preferred:
        share[preferred] = 0.6
        share[next(method for method in METHODS if method != preferred)] = 0.4
    slots = next_round_slots(plan, preferred, int(strategy["search_balance"]["next_round_main_searches_per_track"]))
    return {
        "status": "ready",
        "window_sequences": [turn["sequence"] for turn in window],
        "main_searches_since_window": len(main_turns) % window_size,
        "completed_searches_by_method": counts,
        "eligible_p0_p1_source_verified_unique_jobs": len(verified_ids),
        "source_recheck_job_ids": sorted(needs_recheck),
        "mobile_live_observed_without_url_job_ids": sorted(mobile_no_url_ids),
        "unmatched_job_ids": sorted(unmatched_ids),
        "shared_verified_jobs": sum(len(discovered_by[canonical_id]) > 1 for canonical_id in verified_ids),
        "credited_verified_jobs_by_method": credited,
        "verified_jobs_per_search": yields,
        "next_round_method_share": share,
        "recommendation": "按有效岗位产出调整下一轮" if preferred else "证据不足或差异不明显，下一轮维持 50/50",
        "next_round_slots": slots,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, choices=["candidate_a"])
    parser.add_argument("--plan", type=Path, default=DEFAULT_OUTPUT / "search_plan.json")
    parser.add_argument("--completed", type=Path, default=DEFAULT_OUTPUT / "completed_searches.json")
    parser.add_argument("--matches", type=Path, default=Path(__file__).resolve().parents[1] / "data/runtime/candidate_a/discovered_jobs/matched_jobs.json")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "feedback_report.json")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    completed = json.loads(args.completed.read_text(encoding="utf-8"))
    matches = json.loads(args.matches.read_text(encoding="utf-8"))
    if plan.get("candidate") != "candidate_a" or not isinstance(completed, list) or not isinstance(matches, list):
        raise ValueError("Expected a candidate_a plan and JSON arrays for searches and matched jobs")
    report = evaluate(plan, completed, matches, read_yaml(STRATEGY), args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "recommendation": report["recommendation"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
