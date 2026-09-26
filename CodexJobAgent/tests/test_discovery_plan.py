"""Keep role searches intact while adding product searches and provenance."""

import copy
import sys
import unittest
from collections import Counter
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_candidate_a_discovery_plan import STRATEGY, build_plan, read_yaml  # noqa: E402
from candidate_pool import normalize_result  # noqa: E402
from job_deduplicator import deduplicate  # noqa: E402
from candidate_a_company_prospects import review_prospects  # noqa: E402
from candidate_a_discovery_feedback import evaluate, usable_source_evidence  # noqa: E402


class DiscoveryPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.facts = {
            "candidate": {"id": "candidate_a", "name": "Synthetic Candidate"},
            "projects": {
                "wireless_temporal_feedback_project": {},
                "wireless_adaptive_compression_project": {},
                "wireless_resource_allocation_project": {},
                "medical_cv_segmentation_project": {},
            },
        }
        self.profile = {
            "tracks": {
                "communication_ai": {"weight": 0.50},
                "medical_cv": {"weight": 0.50},
            },
            "target_roles": {
                "communication_ai_P0": [
                    "无线算法工程师", "通信算法工程师", "信号处理算法工程师",
                    "MIMO算法工程师", "链路仿真算法工程师", "物理层算法工程师",
                    "无线系统算法工程师",
                ],
                "medical_cv_P0": [
                    "医学图像算法工程师", "图像分割算法工程师", "计算机视觉算法工程师",
                    "3D视觉算法工程师", "医学影像研发工程师", "深度学习算法工程师",
                    "图像处理算法工程师",
                ],
                "general_ai_P1": ["机器学习工程师", "AI算法工程师"],
            },
        }
        self.strategy = read_yaml(STRATEGY)

    def test_both_methods_and_tracks_have_equal_main_search_turns(self) -> None:
        plan = build_plan(self.facts, self.profile, self.strategy, date(2026, 9, 25))
        counts = Counter((row["track"], row["discovery_method"]) for row in plan["searches"])
        self.assertEqual(counts[("communication_ai", "role_led")], 6)
        self.assertEqual(counts[("communication_ai", "product_led")], 6)
        self.assertEqual(counts[("medical_cv", "role_led")], 6)
        self.assertEqual(counts[("medical_cv", "product_led")], 6)
        self.assertEqual(counts[("general_ai", "secondary_role_led")], 2)
        self.assertEqual(plan["searches"][0]["job_query"], self.profile["target_roles"]["communication_ai_P0"][0])
        self.assertIn(self.profile["target_roles"]["communication_ai_P0"][-1], plan["remaining_original_role_queries"]["communication_ai"])
        self.assertIn("40/60", plan["adaptive_rule"])
        self.assertTrue(all(row["apply_authorized"] is False for row in plan["searches"]))

    def test_unverified_project_cannot_enter_product_plan(self) -> None:
        strategy = copy.deepcopy(self.strategy)
        strategy["scenarios"]["communication_ai"][0]["evidence_projects"] = ["invented_project"]
        with self.assertRaisesRegex(ValueError, "Unverified project"):
            build_plan(self.facts, self.profile, strategy, date(2026, 9, 25))

    def test_same_job_keeps_both_discovery_routes_after_dedup(self) -> None:
        base = {
            "job_id": "a",
            "platform": "BOSS直聘",
            "platform_job_id": "1",
            "job_fingerprint": "same-fingerprint",
            "company": "示例通信公司",
            "job_title": "无线算法工程师",
            "city": "北京",
            "jd_text": "负责无线算法仿真",
            "first_seen": "2026-09-25",
            "url": "https://example.test/job/1",
            "discovery_method": "role_led",
            "search_query": "无线通信算法工程师",
        }
        product = {
            **base,
            "job_id": "b",
            "platform_job_id": "2",
            "discovery_method": "product_led",
            "product_scenario_id": "csi_feedback",
            "search_query": "CSI反馈 信道压缩 算法",
            "product_evidence_url": "https://example.test/product/csi",
            "company_size": "20-99人",
        }
        canonical, summary = deduplicate([base, product])
        self.assertEqual(summary["canonical_count"], 1)
        self.assertEqual(canonical[0]["discovery_methods"], ["product_led", "role_led"])
        self.assertEqual(canonical[0]["product_scenario_ids"], ["csi_feedback"])
        self.assertEqual(canonical[0]["company_product_evidence_urls"], ["https://example.test/product/csi"])
        enriched = normalize_result(canonical[0], {})
        self.assertEqual(enriched["discovery_methods"], ["product_led", "role_led"])
        self.assertEqual(enriched["company_size"], "20-99人")

    def test_company_prospect_requires_product_evidence_before_boss_lookup(self) -> None:
        base = {
            "candidate": "candidate_a", "product_scenario_id": "ct_mri_segmentation",
            "company": "示例医疗公司", "company_size": "0-20人",
            "observed_at": "2026-09-25", "product_evidence_source_type": "official_product_page",
            "product_evidence_url": "https://example.test/product", "product_evidence_summary": "公司产品页面描述影像分割模块",
        }
        ready, missing = review_prospects([base, {**base, "company": "未核验公司", "product_evidence_url": ""}], self.strategy, date(2026, 9, 25))
        self.assertEqual(ready["review_status"], "ready_for_boss_lookup")
        self.assertIn("micro_company_verify_full_jd_on_boss", ready["review_checks"])
        self.assertFalse(ready["apply_authorized"])
        self.assertEqual(missing["review_status"], "needs_product_review")

    def test_feedback_shifts_only_after_verified_yield(self) -> None:
        plan = build_plan(self.facts, self.profile, self.strategy, date(2026, 9, 25))
        completed = [
            {"sequence": row["sequence"], "candidate": "candidate_a", "status": "completed", "observed_at": "2026-09-25", "canonical_job_ids": ([f"job-{row['sequence']}"] if row["sequence"] in {1, 5} else [])}
            for row in plan["searches"][:8]
        ]
        def match(job_id: str) -> dict:
            return {
                "canonical_job_id": job_id, "eligibility": {"status": "eligible"},
                "opportunity_priority": "P0", "source_checked_at": "2026-09-25",
                "source_status": "observed_open", "url": "https://example.test/job/1",
                "jd_text": "负责无线算法研发、模型训练和仿真验证，分析算法复杂度并和工程团队合作，将研究结果用于真实通信系统。" * 2,
            }
        report = evaluate(plan, completed, [match("job-1"), match("job-5")], self.strategy, date(2026, 9, 25))
        self.assertEqual(report["next_round_method_share"], {"role_led": 0.6, "product_led": 0.4})
        self.assertEqual(len(report["next_round_slots"]), 20)
        self.assertEqual(Counter(row["discovery_method"] for row in report["next_round_slots"]), {"role_led": 12, "product_led": 8})
        self.assertEqual(Counter(row["track"] for row in report["next_round_slots"]), {"communication_ai": 10, "medical_cv": 10})
        completed[2]["canonical_job_ids"] = ["job-1"]
        shared = evaluate(plan, completed, [match("job-1"), match("job-5")], self.strategy, date(2026, 9, 25))
        self.assertEqual(shared["shared_verified_jobs"], 1)
        self.assertEqual(shared["credited_verified_jobs_by_method"], {"role_led": 1.5, "product_led": 0.5})
        incomplete = evaluate(plan, completed[:7], [match("job-1")], self.strategy, date(2026, 9, 25))
        self.assertEqual(incomplete["status"], "awaiting_searches")
        self.assertEqual(incomplete["next_round_slots"], [])

    def test_recent_complete_boss_detail_counts_with_recheck_flag(self) -> None:
        live = {
            "source": "mobile_boss_live", "source_status": "live_detail_observed_full_jd",
            "posting_state": "active_detail_observed", "company": "示例公司",
            "job_title": "图像算法工程师", "jd_text": "负责图像分割模型的训练、验证、实验分析和算法优化，阅读完整岗位要求并与研发团队协作。" * 2,
        }
        self.assertEqual(usable_source_evidence(live, "2026-09-25", date(2026, 9, 25)), (True, True))
        self.assertEqual(usable_source_evidence(live, "2026-09-14", date(2026, 9, 25)), (False, False))
        live["source_status"] = "live_detail_observed_partial"
        self.assertEqual(usable_source_evidence(live, "2026-09-25", date(2026, 9, 25)), (False, False))


if __name__ == "__main__":
    unittest.main()
