"""Deterministic salary normalization for the job-agent read-only stages.

The legacy discovery artifacts keep the source salary string and, for some
records, a pair of numeric fields.  This module adds an explicit unit-aware
representation without changing the legacy fields.  It never converts a
daily/hourly salary into monthly or annual cash for filtering.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("，", ",")
        .replace("～", "-")
        .replace("－", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace("至", "-")
        .replace("／", "/")
        .replace("·", "*")
        .replace("•", "*")
        .replace("每月", "/月")
        .replace("人民币", "元")
        .strip()
    )


def _unit_factor(unit: str | None, *, annual: bool = False) -> float | None:
    if not unit:
        return None
    u = unit.lower()
    if u in {"k", "千"}:
        return 1.0
    if u in {"万", "w"}:
        return 10.0 if not annual else 100.0
    if u in {"元", "rmb", "cny"}:
        return 0.001 if not annual else 0.001
    return None


def _tokens(text: str) -> list[tuple[float, str | None]]:
    """Return number/unit tokens in source order."""
    pattern = re.compile(
        r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>K|k|千|万|W|w|元|人民币)?"
    )
    out: list[tuple[float, str | None]] = []
    for match in pattern.finditer(text):
        value = _number(match.group("num"))
        if value is not None:
            out.append((value, match.group("unit")))
    return out


def _range_tokens(text: str, *, annual: bool = False) -> tuple[float, float, str | None, str | None] | None:
    """Parse the first one or two salary values and preserve endpoint units."""
    # Ignore the frequency and date-like numbers after the salary range.
    prefix = re.split(r"(?:\*|薪|/月|/天|/日|/小时|/时|/年|每周|天)", text, maxsplit=1)[0]
    values = _tokens(prefix)
    if not values:
        return None
    if len(values) == 1:
        low, high = values[0], values[0]
    else:
        low, high = values[0], values[1]
    low_unit = low[1] or high[1]
    high_unit = high[1] or low[1]
    if low_unit is None and high_unit is None:
        # A unit-less number is not safe to classify on its own.
        return None
    return low[0], high[0], low_unit, high_unit


def _convert_monthly(value: float, unit: str | None) -> float | None:
    if unit is None:
        return None
    u = unit.lower()
    if u in {"k", "千"}:
        return value
    if u in {"万", "w"}:
        return value * 10.0
    return None


def _convert_annual_k(value: float, unit: str | None) -> float | None:
    if unit is None:
        return None
    u = unit.lower()
    if u in {"万", "w"}:
        return value * 10.0  # 10,000 CNY -> 10 thousand CNY
    if u in {"k", "千"}:
        return value
    if u in {"元", "人民币", "rmb", "cny"}:
        return value / 1000.0
    return None


def _convert_cny(value: float, unit: str | None) -> float | None:
    # Daily/hourly values are normally written in yuan.  A bare number is
    # accepted only when the surrounding marker says day/hour.
    if unit is None:
        return value
    u = unit.lower()
    if u in {"元", "人民币", "rmb", "cny"}:
        return value
    if u in {"k", "千"}:
        return value * 1000.0
    if u in {"万", "w"}:
        return value * 10000.0
    return None


def parse_salary(raw: Any) -> dict[str, Any]:
    """Normalize one source salary string into the Stage 6A contract."""
    salary_raw = "" if raw is None else str(raw).strip()
    text = _clean(salary_raw)
    result: dict[str, Any] = {
        "salary_raw": salary_raw,
        "salary_type": "unknown",
        "salary_min_raw": None,
        "salary_max_raw": None,
        "salary_months": None,
        "monthly_base_min_k": None,
        "monthly_base_max_k": None,
        "annual_cash_min_k": None,
        "annual_cash_max_k": None,
        "daily_cny_min": None,
        "daily_cny_max": None,
        "hourly_cny_min": None,
        "hourly_cny_max": None,
        "salary_months_explicit": False,
        "annual_cash_is_estimate": False,
        "normalization_note": None,
    }
    if not text:
        result["normalization_note"] = "empty_salary"
        return result

    month_match = re.search(r"(\d+(?:\.\d+)?)\s*薪", text, re.I)
    if month_match:
        result["salary_months"] = float(month_match.group(1))
        result["salary_months_explicit"] = True

    # Daily and hourly markers take precedence over K/万 tokens.
    if re.search(r"(?:元|人民币)?\s*/\s*(?:天|日)|(?:元|人民币)\s*(?:每天|/天|/日)", text, re.I):
        parsed = _range_tokens(text)
        if parsed:
            low, high, low_unit, high_unit = parsed
            result.update(
                salary_type="daily_cny",
                salary_min_raw=low,
                salary_max_raw=high,
                daily_cny_min=_convert_cny(low, low_unit),
                daily_cny_max=_convert_cny(high, high_unit),
                normalization_note="daily salary kept in CNY/day; excluded from monthly statistics",
            )
        else:
            result["normalization_note"] = "daily_marker_without_numeric_range"
        result["salary_months"] = None
        result["salary_months_explicit"] = False
        return result

    if re.search(r"(?:元|人民币)?\s*/\s*(?:小时|时)|(?:元|人民币)\s*(?:每小时|/小时|/时)", text, re.I):
        parsed = _range_tokens(text)
        if parsed:
            low, high, low_unit, high_unit = parsed
            result.update(
                salary_type="hourly_cny",
                salary_min_raw=low,
                salary_max_raw=high,
                hourly_cny_min=_convert_cny(low, low_unit),
                hourly_cny_max=_convert_cny(high, high_unit),
                normalization_note="hourly salary kept in CNY/hour; excluded from monthly statistics",
            )
        else:
            result["normalization_note"] = "hourly_marker_without_numeric_range"
        result["salary_months"] = None
        result["salary_months_explicit"] = False
        return result

    # Annual markers include 万/年, 元/年, 年薪 and explicit annual cash.
    if re.search(r"(?:/|每)\s*年|年薪|年收入|年度薪资|年终", text, re.I):
        parsed = _range_tokens(text, annual=True)
        if parsed:
            low, high, low_unit, high_unit = parsed
            low_k = _convert_annual_k(low, low_unit)
            high_k = _convert_annual_k(high, high_unit)
            if low_k is not None and high_k is not None:
                result.update(
                    salary_type="annual_cny",
                    salary_min_raw=low,
                    salary_max_raw=high,
                    annual_cash_min_k=low_k,
                    annual_cash_max_k=high_k,
                    normalization_note="annual cash kept in thousand CNY/year",
                )
            else:
                result["normalization_note"] = "annual_marker_with_unrecognized_unit"
        else:
            result["normalization_note"] = "annual_marker_without_numeric_range"
        result["salary_months"] = None
        result["salary_months_explicit"] = False
        return result

    # Remaining K/千/万 listings are treated as monthly board salary.  Job
    # boards commonly omit /月; a 12-month cash estimate is labelled inferred
    # and is never used for hard eligibility filtering.
    if re.search(r"(?:K|千|万)\b|(?:K|千|万)\s*(?:/月|每月)|月薪", text, re.I):
        parsed = _range_tokens(text)
        if parsed:
            low, high, low_unit, high_unit = parsed
            low_k = _convert_monthly(low, low_unit)
            high_k = _convert_monthly(high, high_unit)
            if low_k is not None and high_k is not None:
                months = result["salary_months"]
                if months is None:
                    months = 12.0
                    result["salary_months"] = months
                    result["annual_cash_is_estimate"] = True
                    note = "monthly salary; 12-month annual cash estimate inferred"
                else:
                    note = "monthly salary; annual cash computed from explicit salary months"
                result.update(
                    salary_type="monthly_k",
                    salary_min_raw=low,
                    salary_max_raw=high,
                    monthly_base_min_k=low_k,
                    monthly_base_max_k=high_k,
                    annual_cash_min_k=low_k * months,
                    annual_cash_max_k=high_k * months,
                    normalization_note=note,
                )
            else:
                result["normalization_note"] = "monthly_marker_with_unrecognized_unit"
        else:
            result["normalization_note"] = "monthly_marker_without_numeric_range"
        return result

    result["normalization_note"] = "unit_or_period_not_detected"
    return result


def normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    out = dict(job)
    normalized = parse_salary(job.get("salary", job.get("salary_raw", "")))
    out["salary_normalization"] = normalized
    # Keep the contract available at the top level for simple downstream JSON
    # consumers while retaining a nested copy for auditability.
    for key, value in normalized.items():
        if key == "salary_raw":
            continue
        out[key] = value
    out["salary_raw"] = normalized["salary_raw"]
    return out


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _range_stats(rows: list[dict[str, Any]], low_key: str, high_key: str, *, unit: str) -> dict[str, Any]:
    lows = [float(row[low_key]) for row in rows if row.get(low_key) is not None]
    highs = [float(row[high_key]) for row in rows if row.get(high_key) is not None]
    mids = [(lo + hi) / 2.0 for lo, hi in zip(lows, highs)]

    def stats(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0, "mean": None, "median": None, "p25": None, "p75": None}
        return {
            "count": len(values),
            "mean": round(statistics.fmean(values), 4),
            "median": round(statistics.median(values), 4),
            "p25": round(_quantile(values, 0.25) or 0.0, 4),
            "p75": round(_quantile(values, 0.75) or 0.0, 4),
        }

    return {
        "unit": unit,
        "summary_basis": "range midpoint; low/high stats retained separately",
        "count": len(mids),
        "mean": stats(mids)["mean"],
        "median": stats(mids)["median"],
        "p25": stats(mids)["p25"],
        "p75": stats(mids)["p75"],
        "range_min": stats(lows),
        "range_max": stats(highs),
    }


def build_audit(jobs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(jobs)
    normalized = [row.get("salary_normalization", parse_salary(row.get("salary", ""))) for row in rows]
    monthly = [row for row in normalized if row.get("salary_type") == "monthly_k"]
    daily = [row for row in normalized if row.get("salary_type") == "daily_cny"]
    annual = [row for row in normalized if row.get("salary_type") == "annual_cny"]
    hourly = [row for row in normalized if row.get("salary_type") == "hourly_cny"]
    unknown = [row for row in normalized if row.get("salary_type") == "unknown"]

    mixed_markers: list[dict[str, Any]] = []
    for row in normalized:
        raw = row.get("salary_raw", "")
        markers = []
        if re.search(r"/\s*(?:天|日)", _clean(raw), re.I):
            markers.append("daily")
        if re.search(r"/\s*(?:小时|时)", _clean(raw), re.I):
            markers.append("hourly")
        if re.search(r"/\s*年|年薪", _clean(raw), re.I):
            markers.append("annual")
        if re.search(r"(?:K|千|万)\s*(?:\*|薪|/月|每月)", _clean(raw), re.I):
            markers.append("monthly")
        if len(set(markers)) > 1:
            mixed_markers.append({"salary_raw": raw, "detected_markers": markers})

    def examples(group: list[dict[str, Any]]) -> list[str]:
        return [str(row.get("salary_raw", "")) for row in group[:8]]

    return {
        "parser_version": "stage6a-unit-aware-v1",
        "total_jobs": len(rows),
        "salary_type_distribution": {
            "monthly_k": len(monthly),
            "daily_cny": len(daily),
            "annual_cny": len(annual),
            "hourly_cny": len(hourly),
            "unknown": len(unknown),
        },
        "monthly_salary_stats": _range_stats(monthly, "monthly_base_min_k", "monthly_base_max_k", unit="thousand_cny_per_month"),
        "daily_intern_salary_stats": _range_stats(daily, "daily_cny_min", "daily_cny_max", unit="cny_per_day"),
        "annual_cash_stats": _range_stats(
            monthly + annual,
            "annual_cash_min_k",
            "annual_cash_max_k",
            unit="thousand_cny_per_year",
        ),
        "hourly_salary_stats": _range_stats(hourly, "hourly_cny_min", "hourly_cny_max", unit="cny_per_hour"),
        "mixed_unit_records": mixed_markers,
        "unknown_salary_examples": examples(unknown),
        "unit_separation_check": {
            "monthly_excludes_daily": True,
            "monthly_excludes_hourly": True,
            "annual_is_monthly_estimate_or_explicit_annual_only": True,
            "daily_monthly_equivalent_used_for_filtering": False,
            "hourly_monthly_equivalent_used_for_filtering": False,
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("input must be a JSON array")
    rows = [normalize_job(row) for row in payload]
    write_json(args.output, rows)
    write_json(args.audit, build_audit(rows))
    print(json.dumps({"normalized_jobs": len(rows), "output": str(args.output), "audit": str(args.audit)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
