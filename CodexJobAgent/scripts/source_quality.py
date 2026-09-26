#!/usr/bin/env python3
"""Assess whether a discovered JD has enough current source evidence for review."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


MAX_SOURCE_AGE_DAYS = 7
MIN_JD_CHARS = 80
OPEN_SOURCE_STATUSES = {"public_detail_page_observed", "observed_open"}


def assess_source_quality(job: dict[str, Any], as_of: date | None = None) -> dict[str, Any]:
    """Keep source confidence separate from technical fit and eligibility."""
    as_of = as_of or date.today()
    reasons: list[str] = []
    checked = str(job.get("source_checked_at") or job.get("last_seen") or "").strip()
    checked_date: date | None = None
    if checked:
        try:
            checked_date = date.fromisoformat(checked[:10])
        except ValueError:
            pass
    if checked_date is None:
        reasons.append("missing_or_invalid_source_date")
    else:
        age = (as_of - checked_date).days
        if age < 0 or age > MAX_SOURCE_AGE_DAYS:
            reasons.append("source_date_out_of_window")

    jd_chars = len(re.sub(r"\s+", "", str(job.get("jd_text") or "")))
    if jd_chars < MIN_JD_CHARS:
        reasons.append("short_jd_summary")
    if str(job.get("source_status") or "").strip() not in OPEN_SOURCE_STATUSES:
        reasons.append("source_status_needs_review")
    if not str(job.get("url") or "").strip():
        reasons.append("missing_source_url")
    methods = job.get("discovery_methods") or ([job.get("discovery_method")] if job.get("discovery_method") else [])
    if "product_led" in methods and not (job.get("company_product_evidence_urls") or job.get("product_evidence_url")):
        reasons.append("missing_company_product_evidence_url")

    return {
        "needs_source_recheck": bool(reasons),
        "source_checked_at": checked or None,
        "source_age_days": (as_of - checked_date).days if checked_date else None,
        "jd_chars": jd_chars,
        "reasons": reasons,
    }
