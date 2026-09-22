#!/usr/bin/env python3
"""Validate that user-private onboarding data is complete enough to use."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = PROJECT_ROOT / ".local"
REQUIRED_FILES = (
    "resume_facts.yaml",
    "profile.yaml",
    "eligibility_policy.yaml",
    "application_profile.yaml",
    "onboarding_status.yaml",
)
PLACEHOLDERS = {"todo", "tbd", "replace_me", "example name", "your name"}


def load_yaml(name: str) -> dict[str, Any]:
    path = LOCAL_DIR / name
    if not path.exists():
        raise ValueError(f"missing {path.relative_to(PROJECT_ROOT)}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a YAML mapping")
    return data


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        for key, item in value.items():
            result.extend(strings(key))
            result.extend(strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(strings(item))
        return result
    return [value] if isinstance(value, str) else []


def main() -> int:
    errors: list[str] = []
    try:
        loaded = {name: load_yaml(name) for name in REQUIRED_FILES}
    except ValueError as exc:
        print(f"PROFILE_NOT_READY: {exc}")
        return 2

    resume = loaded["resume_facts.yaml"]
    profile = loaded["profile.yaml"]
    eligibility = loaded["eligibility_policy.yaml"]
    status = loaded["onboarding_status.yaml"]

    if nested(resume, "metadata", "onboarding_complete") is not True:
        errors.append("resume metadata.onboarding_complete must be true")
    if status.get("confirmed_by_user") is not True:
        errors.append("onboarding_status.confirmed_by_user must be true")

    for field in ("name", "degree", "major", "expected_graduation"):
        value = nested(resume, "candidate", field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"candidate.{field} is required")

    graduation = nested(resume, "candidate", "expected_graduation")
    if isinstance(graduation, str) and not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", graduation):
        errors.append("candidate.expected_graduation must use YYYY-MM")

    roles = nested(profile, "target_roles")
    role_count = 0
    if isinstance(roles, dict):
        role_count = sum(len(value) for value in roles.values() if isinstance(value, list))
    if role_count == 0:
        errors.append("at least one target role is required")

    statuses = nested(eligibility, "eligibility", "statuses")
    if statuses != ["eligible", "uncertain", "ineligible"]:
        errors.append("eligibility statuses must be eligible/uncertain/ineligible")

    for value in strings(loaded):
        if value.strip().lower() in PLACEHOLDERS:
            errors.append(f"unresolved placeholder: {value}")

    if errors:
        print("PROFILE_NOT_READY")
        for error in errors:
            print(f"- {error}")
        return 2

    print("PROFILE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

