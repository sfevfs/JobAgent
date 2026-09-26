"""Source checks must never change a job's technical match or priority."""

import sys
import unittest
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from candidate_pool import build_queue, render_queue_report  # noqa: E402
from source_quality import assess_source_quality  # noqa: E402


class SourceQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.job = {
            "source_checked_at": "2026-09-24",
            "source_status": "public_detail_page_observed",
            "jd_text": "负责医学图像分割算法开发、模型训练与评估，要求熟悉 Python 与 PyTorch，理解三维影像数据处理、实验设计、性能验证和团队协作。",
            "url": "https://example.test/job/1",
        }

    def test_recent_complete_source_passes(self) -> None:
        self.job["jd_text"] *= 2
        quality = assess_source_quality(self.job, date(2026, 9, 25))
        self.assertFalse(quality["needs_source_recheck"])
        self.assertEqual(quality["reasons"], [])

    def test_stale_short_source_is_flagged(self) -> None:
        self.job["source_checked_at"] = "2026-09-14"
        self.job["jd_text"] = "图像算法"
        quality = assess_source_quality(self.job, date(2026, 9, 25))
        self.assertEqual(quality["source_age_days"], 11)
        self.assertIn("source_date_out_of_window", quality["reasons"])
        self.assertIn("short_jd_summary", quality["reasons"])

    def test_product_route_needs_company_product_source(self) -> None:
        self.job["jd_text"] *= 2
        self.job["discovery_methods"] = ["role_led", "product_led"]
        quality = assess_source_quality(self.job, date(2026, 9, 25))
        self.assertIn("missing_company_product_evidence_url", quality["reasons"])
        self.job["company_product_evidence_urls"] = ["https://example.test/product"]
        self.assertFalse(assess_source_quality(self.job, date(2026, 9, 25))["needs_source_recheck"])

    def test_queue_preserves_match_decision(self) -> None:
        result = {
            **self.job,
            "canonical_job_id": "canonical-1",
            "company": "示例公司",
            "job_title": "医学图像算法工程师",
            "technical_match": {"score": 86, "grade": "S", "primary_track": "medical_cv"},
            "eligibility": {"status": "eligible"},
            "opportunity_priority": "P0",
            "decision": "selected",
            "preference_fit": {"score": 80},
        }
        queue = build_queue([result])
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["technical_score"], 86)
        self.assertEqual(queue[0]["opportunity_priority"], "P0")
        self.assertEqual(queue[0]["decision"], "selected")
        self.assertIn("source_quality", queue[0])
        self.assertIn("来源核验", render_queue_report(queue))


if __name__ == "__main__":
    unittest.main()
