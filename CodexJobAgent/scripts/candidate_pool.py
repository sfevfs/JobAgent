#!/usr/bin/env python3
"""Run Job Matcher on canonical discovered jobs and build local review artifacts.

This is a read/score/save stage only.  It writes jobs and ``job_discovered`` /
``job_matched`` audit events to the local database, but never writes to
applications or conversations and never performs a platform action.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from init_db import DATABASE_PATH, initialize_database
from job_matcher import JobMatcher
from source_quality import assess_source_quality


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "runtime" / "discovered_jobs"
DEFAULT_INPUT = DEFAULT_OUTPUT_DIR / "canonical_jobs.json"
DEFAULT_POOL_REPORT = PROJECT_ROOT / "reports" / "runtime" / "candidate_pool.md"
DEFAULT_QUEUE_REPORT = PROJECT_ROOT / "reports" / "runtime" / "application_review_queue.md"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def bool_marker(value: Any) -> int:
    text = str(value or "").lower()
    return int(any(token in text for token in ("校招", "校园", "应届", "实习", "intern")))


def is_internship(value: Any) -> int:
    text = str(value or "").lower()
    return int(any(token in text for token in ("实习", "intern", "留用实习")))


def normalize_result(job: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(result)
    enriched.update(
        {
            "job_id": job.get("job_id"),
            "platform": job.get("platform"),
            "platform_job_id": job.get("platform_job_id"),
            "company": job.get("company"),
            "job_title": job.get("job_title"),
            "city": job.get("city"),
            "salary": job.get("salary"),
            "job_type": job.get("job_type"),
            "jd_text": job.get("jd_text"),
            "graduation_year": job.get("graduation_year"),
            "url": job.get("url"),
            "source": job.get("source"),
            "source_label": job.get("source_label"),
            "source_checked_at": job.get("source_checked_at"),
            "source_status": job.get("source_status"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "salary_months": job.get("salary_months"),
            "canonical_job_id": job.get("canonical_job_id"),
            "same_job_group_id": job.get("same_job_group_id"),
            "discovered_platforms": job.get("discovered_platforms") or [job.get("platform")],
            "discovery_methods": job.get("discovery_methods") or ([job["discovery_method"]] if job.get("discovery_method") else []),
            "product_scenario_ids": job.get("product_scenario_ids") or ([job["product_scenario_id"]] if job.get("product_scenario_id") else []),
            "search_queries": job.get("search_queries") or ([job["search_query"]] if job.get("search_query") else []),
            "company_product_evidence_urls": job.get("company_product_evidence_urls") or ([job["product_evidence_url"]] if job.get("product_evidence_url") else []),
            "company_size": job.get("company_size"),
            "duplicate_platform_records": job.get("duplicate_platform_records", []),
            "duplicate_count": job.get("duplicate_count", 0),
            "user_review_status": "pending",
            "discovery_stage": "real_public_job_discovery_read_only",
        }
    )
    return enriched


def upsert_database(
    jobs: list[dict[str, Any]],
    results: list[dict[str, Any]],
    database_path: Path,
) -> dict[str, int]:
    initialize_database(database_path)
    inserted = updated = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for job, result in zip(jobs, results, strict=True):
            technical = result["technical_match"]
            eligibility = result["eligibility"]
            preference = result["preference_fit"]
            values = (
                job.get("platform"),
                job.get("platform_job_id"),
                job.get("company"),
                job.get("job_title"),
                job.get("city"),
                job.get("salary"),
                job.get("jd_text"),
                job.get("url"),
                technical.get("score"),
                technical.get("grade"),
                result.get("decision"),
                result.get("final_reason"),
                job.get("job_fingerprint"),
                job.get("canonical_job_id"),
                job.get("same_job_group_id"),
                technical.get("primary_track"),
                technical.get("score"),
                technical.get("grade"),
                eligibility.get("status"),
                result.get("opportunity_priority"),
                preference.get("score"),
                json.dumps(job.get("discovered_platforms", []), ensure_ascii=False),
                job.get("salary_min"),
                job.get("salary_max"),
                job.get("salary_months"),
                bool_marker(job.get("job_type")),
                is_internship(job.get("job_type")),
                job.get("graduation_year"),
                job.get("source_status"),
            )
            existing = connection.execute(
                "SELECT job_id, user_review_status FROM jobs WHERE job_fingerprint = ?",
                (job.get("job_fingerprint"),),
            ).fetchone()
            if existing:
                update_values = (
                    job.get("platform"),
                    job.get("platform_job_id"),
                    job.get("company"),
                    job.get("job_title"),
                    job.get("city"),
                    job.get("salary"),
                    job.get("jd_text"),
                    job.get("url"),
                    technical.get("score"),
                    technical.get("grade"),
                    result.get("decision"),
                    result.get("final_reason"),
                    now,
                    job.get("canonical_job_id"),
                    job.get("same_job_group_id"),
                    technical.get("primary_track"),
                    technical.get("score"),
                    technical.get("grade"),
                    eligibility.get("status"),
                    result.get("opportunity_priority"),
                    preference.get("score"),
                    json.dumps(job.get("discovered_platforms", []), ensure_ascii=False),
                    job.get("salary_min"),
                    job.get("salary_max"),
                    job.get("salary_months"),
                    bool_marker(job.get("job_type")),
                    is_internship(job.get("job_type")),
                    job.get("graduation_year"),
                    job.get("source_status"),
                    existing[0],
                )
                connection.execute(
                    """
                    UPDATE jobs SET platform=?, platform_job_id=?, company=?, job_title=?, city=?,
                        salary=?, jd_text=?, url=?, score=?, grade=?, decision=?, reason=?,
                        last_seen=?, canonical_job_id=?, same_job_group_id=?, primary_track=?,
                        technical_score=?, technical_grade=?, eligibility_status=?,
                        opportunity_priority=?, preference_score=?, discovered_platforms=?,
                        salary_min=?, salary_max=?, salary_months=?, is_campus=?, is_internship=?,
                        graduation_year=?, source_status=?
                    WHERE job_id=?
                    """,
                    update_values,
                )
                updated += 1
                db_job_id = existing[0]
            else:
                connection.execute(
                    """
                    INSERT INTO jobs (
                        platform, platform_job_id, company, job_title, city, salary, jd_text, url,
                        score, grade, decision, reason, job_fingerprint, first_seen, last_seen,
                        canonical_job_id, same_job_group_id, primary_track, technical_score,
                        technical_grade, eligibility_status, opportunity_priority, preference_score,
                        discovered_platforms, salary_min, salary_max, salary_months, is_campus,
                        is_internship, graduation_year, source_status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    values[:13] + (now, now) + values[13:],
                )
                inserted += 1
                db_job_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute(
                """
                INSERT INTO audit_events (agent, action, target, result, requires_confirmation)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("candidate_pool", "job_discovered", str(job.get("canonical_job_id")), "saved", 0),
            )
            connection.execute(
                """
                INSERT INTO audit_events (agent, action, target, result, requires_confirmation)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("candidate_pool", "job_matched", str(db_job_id), result.get("opportunity_priority"), 0),
            )
        connection.commit()
    return {"inserted": inserted, "updated": updated}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return round(values[low] + (values[high] - values[low]) * (position - low), 2)


def salary_statistics(results: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for result in results:
        low = result.get("salary_min")
        high = result.get("salary_max")
        if low is None and high is None:
            continue
        value = (float(low) + float(high if high is not None else low)) / 2
        groups[(result["technical_match"]["primary_track"], result.get("city") or "unknown")].append(value)
    output: dict[str, Any] = {
        "eligible_after_100_samples": len(results) >= 100,
        "sample_count": len(results),
        "grouping": "job_track + city",
        "statistics": {},
    }
    for (track, city), values in sorted(groups.items()):
        output["statistics"][f"{track} | {city}"] = {
            "count": len(values),
            "p25": percentile(values, 0.25),
            "median": round(median(values), 2),
            "p75": percentile(values, 0.75),
            "unit_note": "公开 JD 数字原样解析；单位按来源 salary 文本保留，未进行币种换算",
        }
    return output


def recommendation(priority: str) -> str:
    return {"P0": "强烈建议", "P1": "建议 / 可以考虑", "P2": "低优先级", "reject": "不建议"}[priority]


def sort_key(result: dict[str, Any]) -> tuple[int, float, float, str]:
    rank = {"P0": 0, "P1": 1, "P2": 2, "reject": 3}[result["opportunity_priority"]]
    return (rank, -float(result["technical_match"]["score"]), -float(result["preference_fit"]["score"]), str(result.get("first_seen") or ""))


def build_queue(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        result
        for result in results
        if result["opportunity_priority"] in {"P0", "P1"}
        and result["eligibility"]["status"] == "eligible"
    ]
    selected.sort(key=sort_key)
    queue: list[dict[str, Any]] = []
    for number, result in enumerate(selected, 1):
        source_quality = assess_source_quality(result)
        queue.append(
            {
                "review_number": number,
                "canonical_job_id": result.get("canonical_job_id"),
                "company": result.get("company"),
                "job_title": result.get("job_title"),
                "city": result.get("city"),
                "platform": result.get("platform"),
                "salary": result.get("salary"),
                "primary_track": result["technical_match"]["primary_track"],
                "technical_score": result["technical_match"]["score"],
                "technical_grade": result["technical_match"]["grade"],
                "eligibility": result["eligibility"]["status"],
                "opportunity_priority": result["opportunity_priority"],
                "decision": result["decision"],
                "matched_requirements": result.get("matched_requirements", [])[:3],
                "missing_requirements": result.get("missing_requirements", [])[:3],
                "soft_gaps": result.get("soft_gaps", []),
                "project_evidence": result.get("project_evidence", []),
                "why_worth_reviewing": result.get("final_reason"),
                "risk_flags": result.get("risk_flags", []),
                "discovery_methods": result.get("discovery_methods", []),
                "product_scenario_ids": result.get("product_scenario_ids", []),
                "company_product_evidence_urls": result.get("company_product_evidence_urls", []),
                "company_size": result.get("company_size"),
                "link": result.get("url"),
                "recommendation": recommendation(result["opportunity_priority"]),
                "source_quality": source_quality,
                "user_review_status": "pending",
            }
        )
    return queue


def render_pool_report(
    jobs: list[dict[str, Any]],
    results: list[dict[str, Any]],
    queue: list[dict[str, Any]],
    db_summary: dict[str, int],
    salary: dict[str, Any],
) -> str:
    priority_counts = Counter(result["opportunity_priority"] for result in results)
    track_counts = Counter(result["technical_match"]["primary_track"] for result in results)
    grade_counts = Counter(result["technical_match"]["grade"] for result in results)
    eligibility_counts = Counter(result["eligibility"]["status"] for result in results)
    platform_counts = Counter(job.get("platform") for job in jobs)
    discovered_platform_counts = Counter(
        platform for job in jobs for platform in job.get("discovered_platforms", [])
    )
    duplicate_groups = sum(1 for job in jobs if job.get("duplicate_count", 0) > 0)
    duplicate_records = sum(int(job.get("duplicate_count", 0)) for job in jobs)
    p0 = sorted(
        (result for result in results if result["opportunity_priority"] == "P0"),
        key=sort_key,
    )[:10]
    p1 = sorted(
        (result for result in results if result["opportunity_priority"] == "P1"),
        key=sort_key,
    )[:20]
    lines = [
        "# Candidate Pool V1",
        "",
        "> 第五阶段只读真实岗位发现报告。所有条目来自公开 JD 读取、标准化、去重和本地 Matcher；没有投递、立即沟通、HR 消息、简历上传或平台资料修改。",
        "",
        "## 总览",
        "",
        f"- 原始发现岗位：**{len(jobs) + duplicate_records}**",
        f"- 去重后 canonical jobs：**{len(jobs)}**",
        f"- 重复记录：{duplicate_records}；含重复的 canonical 组：{duplicate_groups}。",
        f"- 数据库写入：inserted={db_summary['inserted']}，updated={db_summary['updated']}；所有人工状态保持 pending。",
        f"- 待确认清单：{len(queue)} 个（仅 P0/P1 且 eligible）。",
        f"- 其中来源需重新核对：{sum(item['source_quality']['needs_source_recheck'] for item in queue)} 个；技术分和优先级不受此标记影响。",
        "",
        "## 平台分布",
        "",
        "- canonical 来源：" + "，".join(f"{key}={value}" for key, value in sorted(platform_counts.items())),
        "- 发现平台覆盖（含重复记录）：" + "，".join(f"{key}={value}" for key, value in sorted(discovered_platform_counts.items())),
        "",
        "## Track / Eligibility / Priority",
        "",
        "- Track：" + "，".join(f"{key}={track_counts.get(key, 0)}" for key in ("communication_ai", "medical_cv", "general_ai")),
        "- Grade：" + "，".join(f"{key}={grade_counts.get(key, 0)}" for key in ("S", "A", "B", "C", "D")),
        "- Eligibility：" + "，".join(f"{key}={eligibility_counts.get(key, 0)}" for key in ("eligible", "uncertain", "ineligible")),
        "- Priority：" + "，".join(f"{key}={priority_counts.get(key, 0)}" for key in ("P0", "P1", "P2", "reject")),
        "",
        "## 通信与医学/CV比例",
        "",
        f"communication_ai={track_counts.get('communication_ai', 0)}，medical_cv={track_counts.get('medical_cv', 0)}；比例 {track_counts.get('communication_ai', 0)}:{track_counts.get('medical_cv', 0)}。General AI={track_counts.get('general_ai', 0)}。",
        "",
        "## 薪资统计",
        "",
        f"样本数 {salary['sample_count']}，已达到动态统计门槛（100）={salary['eligible_after_100_samples']}；按 job_track + city 统计 P25/Median/P75。",
        "",
        "| Track / City | n | P25 | Median | P75 |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, item in salary["statistics"].items():
        lines.append(f"| {key} | {item['count']} | {item['p25']} | {item['median']} | {item['p75']} |")
    if not salary["statistics"]:
        lines.append("| 无公开数字薪资 | 0 | N/A | N/A | N/A |")
    lines.extend(["", "## P0 Top 10", "", "| Rank | Job | Score | Grade | Track | City | Link |", "|---:|---|---:|---|---|---|---|"])
    for rank, result in enumerate(p0, 1):
        lines.append(f"| {rank} | {result['company']} / {result['job_title']} | {result['technical_match']['score']} | {result['technical_match']['grade']} | {result['technical_match']['primary_track']} | {result.get('city')} | [JD]({result.get('url')}) |")
    if not p0:
        lines.append("| - | 无 | - | - | - | - | - |")
    lines.extend(["", "## P1 Top 20", "", "| Rank | Job | Score | Grade | Track | City | Link |", "|---:|---|---:|---|---|---|---|"])
    for rank, result in enumerate(p1, 1):
        lines.append(f"| {rank} | {result['company']} / {result['job_title']} | {result['technical_match']['score']} | {result['technical_match']['grade']} | {result['technical_match']['primary_track']} | {result.get('city')} | [JD]({result.get('url')}) |")
    if not p1:
        lines.append("| - | 无 | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 审核与安全状态",
            "",
            "所有 P0/P1 项目的 `user_review_status` 为 `pending`。`selected` 只表示进入本地候选池，不代表投递。",
            "",
            "真实投递：0；HR 消息发送：0；简历上传：0；平台资料修改：0；手机动作：0。",
            "",
        ]
    )
    return "\n".join(lines)


def render_queue_report(queue: list[dict[str, Any]]) -> str:
    lines = [
        "# Application Review Queue",
        "",
        "> 第五阶段人工确认清单。仅包含 `P0/P1 + eligible` 岗位；全部为 pending。查看本清单不等于授权投递。",
        "",
        f"待确认岗位数：**{len(queue)}**。建议每批人工审核 15–25 个，从 P0 开始。",
        f"来源需重新核对：**{sum(item['source_quality']['needs_source_recheck'] for item in queue)}** 个。",
        "",
    ]
    for item in queue:
        lines.extend(
            [
                f"## {item['review_number']}. {item['company']} / {item['job_title']}",
                "",
                f"编号：`{item['canonical_job_id']}`",
                f"公司：{item['company']}",
                f"岗位：{item['job_title']}",
                f"城市：{item['city']}",
                f"平台：{item['platform']}",
                f"薪资：{item['salary'] or '未公开'}",
                "",
                f"Primary Track：`{item['primary_track']}`",
                f"Technical Score：**{item['technical_score']}**",
                f"Technical Grade：`{item['technical_grade']}`",
                f"Eligibility：`{item['eligibility']}`",
                f"Opportunity Priority：`{item['opportunity_priority']}`",
                f"建议：**{item['recommendation']}**",
                f"来源核验：{'需重新核对原页面' if item['source_quality']['needs_source_recheck'] else '来源信息满足本地检查'}",
                f"来源检查日期：{item['source_quality']['source_checked_at'] or '未知'}；JD 摘要长度：{item['source_quality']['jd_chars']} 字符",
                f"来源核验原因：{', '.join(item['source_quality']['reasons']) or '无'}",
                f"发现路线：{', '.join(item['discovery_methods']) or '历史记录未标记'}；产品场景：{', '.join(item['product_scenario_ids']) or '无'}",
                f"企业规模：{item['company_size'] or '未知'}；产品证据：{', '.join(item['company_product_evidence_urls']) or '未记录'}",
                "",
                "主要匹配：",
            ]
        )
        lines.extend(f"1. {value}" for value in item["matched_requirements"] or ["无额外摘要"])
        lines.append("主要缺口：")
        lines.extend(f"1. {value}" for value in item["missing_requirements"] or ["无明确缺口"])
        lines.append("Soft Gaps：")
        lines.extend(f"- {value.get('skill')}: {value.get('importance')} / {value.get('effect')}" for value in item["soft_gaps"] or [{"skill": "无", "importance": "none", "effect": "none"}])
        lines.append("项目证据：")
        lines.extend(
            f"- {value.get('project')}：{value.get('evidence')}（{value.get('evidence_type')}）"
            for value in item["project_evidence"] or [{"project": "无", "evidence": "无直接项目证据", "evidence_type": "none"}]
        )
        lines.extend(
            [
                "为什么值得进入待确认清单：",
                str(item["why_worth_reviewing"]),
                "风险：",
            ]
        )
        lines.extend(f"- {value}" for value in item["risk_flags"] or ["无额外风险标记"])
        lines.extend(
            [
                f"链接：{item['link']}",
                "人工状态：`pending`（确认 / 排除 / 稍后由用户决定）",
                "",
            ]
        )
    if not queue:
        lines.append("当前没有同时满足 P0/P1 与 eligible 的岗位。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--pool-report", type=Path, default=DEFAULT_POOL_REPORT)
    parser.add_argument("--queue-report", type=Path, default=DEFAULT_QUEUE_REPORT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    jobs = read_json(args.input)
    if not isinstance(jobs, list):
        raise ValueError("Canonical input must be a JSON array")
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        jobs = jobs[: args.limit]
    matcher = JobMatcher()
    results = [normalize_result(job, matcher.match(job)) for job in jobs]
    queue = build_queue(results)
    db_summary = upsert_database(jobs, results, args.database)
    salary = salary_statistics(results)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    duplicate_record_count = sum(int(job.get("duplicate_count") or 0) for job in jobs)
    raw_count = len(jobs) + duplicate_record_count
    write_json(args.output_dir / "matched_jobs.json", results)
    write_json(
        args.output_dir / "candidate_pool.json",
        {
            "jobs": results,
            "summary": {
                "raw_count": raw_count,
                "canonical_count": len(jobs),
                "duplicate_record_count": duplicate_record_count,
                "queue_count": len(queue),
            },
        },
    )
    write_json(args.output_dir / "application_review_queue.json", queue)
    write_json(args.output_dir / "salary_stats.json", salary)
    write_json(args.output_dir / "db_ingest_summary.json", db_summary)
    args.pool_report.parent.mkdir(parents=True, exist_ok=True)
    args.pool_report.write_text(render_pool_report(jobs, results, queue, db_summary, salary), encoding="utf-8", newline="\n")
    args.queue_report.parent.mkdir(parents=True, exist_ok=True)
    args.queue_report.write_text(render_queue_report(queue), encoding="utf-8", newline="\n")
    print(json.dumps({"raw_jobs": len(jobs), "canonical_jobs": len(jobs), "review_queue": len(queue), "db": db_summary, "pool_report": str(args.pool_report), "queue_report": str(args.queue_report)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
