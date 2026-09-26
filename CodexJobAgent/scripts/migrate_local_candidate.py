#!/usr/bin/env python3
"""Copy an already-confirmed local profile into an isolated candidate slot."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ("candidate_a", "candidate_b")
REQUIRED = ("resume_facts.yaml", "profile.yaml", "eligibility_policy.yaml", "onboarding_status.yaml")
OPTIONAL = ("application_profile.yaml",)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, choices=CANDIDATES)
    parser.add_argument("--source-dir", required=True, type=Path)
    args = parser.parse_args()
    source = args.source_dir.resolve()
    destination = ROOT / ".local/candidates" / args.candidate
    missing = [name for name in REQUIRED if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Source profile is missing: {', '.join(missing)}")
    facts = yaml.safe_load((source / "resume_facts.yaml").read_text(encoding="utf-8"))
    status = yaml.safe_load((source / "onboarding_status.yaml").read_text(encoding="utf-8"))
    if status.get("confirmed_by_user") is not True:
        raise ValueError("Source profile has not been confirmed by the user")
    candidate_meta = facts.get("candidate", {}) if isinstance(facts.get("candidate", {}), dict) else {}
    source_id = candidate_meta.get("id") or candidate_meta.get("candidate_id")
    if source_id not in (None, "", args.candidate):
        raise ValueError(f"Source candidate id {source_id!r} does not match {args.candidate!r}")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Destination already has a candidate profile; review it manually: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED + OPTIONAL:
        if (source / name).is_file():
            shutil.copy2(source / name, destination / name)
    print(f"MIGRATE_PROFILE_OK: {args.candidate} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
