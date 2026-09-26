#!/usr/bin/env python3
"""Plan balanced role-led and product-led searches for the primary demo candidate.

This reads local facts and preferences. It never opens BOSS, matches a live JD,
changes an application record, or sends a message.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / ".local/candidates/candidate_a/resume_facts.yaml"
PROFILE = ROOT / ".local/candidates/candidate_a/profile.yaml"
STRATEGY = ROOT / "config/product_search_candidate_a.yaml"
DEFAULT_OUTPUT = ROOT / "data/runtime/candidate_a/discovery_strategy"
PRIMARY_TRACKS = ("communication_ai", "medical_cv")


def read_yaml(path: Path) -> dict[str, Any]:
    result = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return result


def unique_strings(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def validate_inputs(facts: dict, profile: dict, strategy: dict) -> None:
    candidate_meta = facts.get("candidate", {}) if isinstance(facts.get("candidate", {}), dict) else {}
    facts_id = candidate_meta.get("id") or candidate_meta.get("candidate_id")
    if facts_id not in (None, "", "candidate_a") or strategy.get("candidate") != "candidate_a":
        raise ValueError("Candidate facts must be unbound or identify candidate_a, and the strategy must identify candidate_a")
    balance = strategy.get("search_balance", {})
    if tuple(balance.get("primary_tracks", [])) != PRIMARY_TRACKS:
        raise ValueError("Both existing primary tracks must remain present")
    weights = profile.get("tracks", {})
    if [weights.get(track, {}).get("weight") for track in PRIMARY_TRACKS] != [0.50, 0.50]:
        raise ValueError("Candidate A communication and medical/CV weights must remain 0.50/0.50")
    projects = set(facts.get("projects", {}))
    role_count = int(balance.get("role_queries_per_track", 0))
    product_count = int(balance.get("product_queries_per_track", 0))
    if role_count < 1 or role_count != product_count:
        raise ValueError("Primary role and product search counts must be equal and positive")
    if int(balance.get("feedback_window_main_searches", 0)) != 8:
        raise ValueError("Candidate A feedback window must contain eight main searches")
    if int(balance.get("minimum_verified_jobs_to_shift", 0)) < 1:
        raise ValueError("Feedback needs a positive verified-job threshold")
    if int(balance.get("next_round_main_searches_per_track", 0)) != 10:
        raise ValueError("Next round must provide ten searches per primary track")
    company_review = strategy.get("company_review", {})
    if not company_review.get("accepted_product_sources") or not company_review.get("preferred_company_sizes"):
        raise ValueError("Company product evidence and size preferences must be configured")
    for track in PRIMARY_TRACKS:
        roles = unique_strings(profile.get("target_roles", {}).get(f"{track}_P0", []))
        scenarios = strategy.get("scenarios", {}).get(track, [])
        if len(roles) < role_count or len(scenarios) < product_count:
            raise ValueError(f"Insufficient search coverage for {track}")
        ids: set[str] = set()
        for scenario in scenarios:
            scenario_id = scenario.get("id")
            if not scenario_id or scenario_id in ids:
                raise ValueError(f"Missing or duplicate product scenario ID in {track}")
            ids.add(scenario_id)
            if scenario.get("evidence_level") not in {"direct_research_overlap", "transfer_only"}:
                raise ValueError(f"Invalid evidence level: {scenario_id}")
            if not scenario.get("product_area") or not scenario.get("company_query") or not scenario.get("job_query"):
                raise ValueError(f"Incomplete product scenario: {scenario_id}")
            evidence = scenario.get("evidence_projects") or []
            if not evidence or not set(evidence) <= projects:
                raise ValueError(f"Unverified project reference: {scenario_id}")


def build_plan(facts: dict, profile: dict, strategy: dict, as_of: date) -> dict[str, Any]:
    validate_inputs(facts, profile, strategy)
    balance = strategy["search_balance"]
    count = int(balance["role_queries_per_track"])
    all_role_queries = {
        track: unique_strings(profile["target_roles"][f"{track}_P0"])
        for track in PRIMARY_TRACKS
    }
    role_queries = {track: all_role_queries[track][:count] for track in PRIMARY_TRACKS}
    scenarios = {track: strategy["scenarios"][track][:count] for track in PRIMARY_TRACKS}
    sizes = balance["preferred_company_sizes"]
    searches: list[dict[str, Any]] = []

    def add(track: str, method: str, job_query: str, scenario: dict | None = None) -> None:
        searches.append({
            "sequence": len(searches) + 1,
            "candidate": "candidate_a",
            "track": track,
            "discovery_method": method,
            "job_query": job_query,
            "company_query": scenario.get("company_query") if scenario else None,
            "product_scenario_id": scenario.get("id") if scenario else None,
            "product_area": scenario.get("product_area") if scenario else None,
            "evidence_projects": scenario.get("evidence_projects", []) if scenario else [],
            "evidence_level": scenario.get("evidence_level") if scenario else None,
            "preferred_company_sizes": sizes,
            "company_size_is_hard_filter": False,
            "apply_authorized": False,
        })

    for index in range(count):
        for track in PRIMARY_TRACKS:
            add(track, "role_led", role_queries[track][index])
        for track in PRIMARY_TRACKS:
            scenario = scenarios[track][index]
            add(track, "product_led", scenario["job_query"], scenario)

    secondary_count = int(balance.get("secondary_general_ai_queries", 0))
    secondary = unique_strings(profile.get("target_roles", {}).get("general_ai_P1", []))
    if len(secondary) < secondary_count:
        raise ValueError("Insufficient secondary general AI role queries")
    for query in secondary[:secondary_count]:
        add("general_ai", "secondary_role_led", query)

    return {
        "candidate": "candidate_a",
        "as_of": as_of.isoformat(),
        "purpose": strategy["purpose"],
        "primary_search_balance": {
            "communication_ai_role_led": count,
            "communication_ai_product_led": count,
            "medical_cv_role_led": count,
            "medical_cv_product_led": count,
        },
        "selection_rule": balance["selection_rule"],
        "adaptive_rule": balance["adaptive_rule"],
        "feedback_window_main_searches": balance["feedback_window_main_searches"],
        "minimum_verified_jobs_to_shift": balance["minimum_verified_jobs_to_shift"],
        "company_review": strategy["company_review"],
        "remaining_original_role_queries": {
            track: all_role_queries[track][count:] for track in PRIMARY_TRACKS
        },
        "workflow": [
            "按轮次交替执行原岗位名称搜索与产品场景搜索，优先查看中小企业，但不排除其他规模。",
            "产品路线先记录公司真实产品的页面、观察日期和对应场景，再在 BOSS 按公司名找具体在招岗位；职位名称路线按原方式搜索。",
            "0-20 人公司核对产品页面和完整岗位职责；公司规模只影响查看顺序，不代替岗位匹配。",
            "每个 JD 记录发现路线、场景 ID、来源链接、观察时间和完整岗位要求；同岗合并来源。",
            "两条路线统一交给现有 Matcher、Eligibility 和来源核验；搜索配额不等于投递配额。",
            "每完成 8 次主线搜索，记录每次搜索关联的 canonical 岗位编号，运行 candidate_a_discovery_feedback.py 复盘并生成下一轮搜索槽位。",
            "真实投递前核对岗位状态、既有投递记录和用户授权；本计划本身不授权投递。",
        ],
        "searches": searches,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Candidate A：岗位名称与产品场景并行搜索计划",
        "",
        f"生成日期：{plan['as_of']}。本计划仅用于找岗；不含当前开放岗位，也不授权投递。",
        "",
        "## 平衡方式",
        "",
        "- 通信/CSI 与医学影像/CV 两条主线各占一半搜索次数。",
        "- 每条主线中，原岗位名称搜索与产品场景反推各占一半。",
        "- 通用 AI 作为少量补充。搜索比例不改变原 Matcher 分数，也不强制实际投递比例。",
        f"- {plan['adaptive_rule']}",
        "- 优先查看 20–99 人、100–499 人公司；0–20 人需核对真实产品和岗位职责。其他规模不被排除。",
        "- 产品路线先记公司产品证据，再按公司名去 BOSS 找具体岗位；公司规模不能代替产品和 JD 核验。",
        "",
        "## 搜索顺序",
        "",
        "| 次序 | 方向 | 路线 | 公司搜索词 | 岗位搜索词 | 产品场景 | 证据边界 |",
        "|---:|---|---|---|---|---|---|",
    ]
    labels = {"role_led": "原岗位名称", "product_led": "产品场景", "secondary_role_led": "次级补充"}
    for row in plan["searches"]:
        lines.append(
            f"| {row['sequence']} | {row['track']} | {labels[row['discovery_method']]} | "
            f"{row['company_query'] or '—'} | {row['job_query']} | {row['product_area'] or '—'} | "
            f"{row['evidence_level'] or '按完整 JD 判断'} |"
        )
    lines.extend(["", "## 原岗位搜索词续批", "", "本批之外的原有岗位词继续保留，后续轮次可接着搜索。", ""])
    for track in PRIMARY_TRACKS:
        lines.append(f"- {track}：" + "、".join(plan["remaining_original_role_queries"][track]))
    lines.extend(["", "## 入池规则", ""])
    lines.extend(f"- {step}" for step in plan["workflow"])
    lines.extend([
        "",
        "## 每轮记录与复盘",
        "",
        "- 用 `scripts/candidate_a_company_prospects.py` 核对产品路线的公司线索；未核对产品的公司不能标为已匹配岗位。",
        "- 在 `data/runtime/candidate_a/discovery_strategy/completed_searches.json` 记录每次已完成搜索的 sequence、candidate、status、observed_at 和 canonical_job_ids。",
        "- 用 `scripts/candidate_a_discovery_feedback.py --candidate candidate_a` 读取本轮匹配结果，按去重后且来源可核验的 eligible P0/P1 岗位计算每次搜索产出；同岗被两种方法发现时各计半个。BOSS 手机端近期完整且开放的详情可用于复盘，无链接岗位单列等待再次核验。",
        "- 达到 8 次主线搜索且至少有 2 个有效岗位时，产出差异足够明显才把下一轮调成 60/40；否则维持 50/50。两条技术主线始终等量。",
    ])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, choices=["candidate_a"])
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = build_plan(read_yaml(FACTS), read_yaml(PROFILE), read_yaml(STRATEGY), args.as_of)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "search_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (args.output_dir / "search_plan.md").write_text(render_markdown(plan), encoding="utf-8", newline="\n")
    print(json.dumps({"searches": len(plan["searches"]), "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
