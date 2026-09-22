#!/usr/bin/env python3
"""Create user-private configuration skeletons without overwriting data."""

from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "templates"
LOCAL_DIR = PROJECT_ROOT / ".local"

FILES = {
    "resume_facts.template.yaml": "resume_facts.yaml",
    "profile.template.yaml": "profile.yaml",
    "eligibility_policy.template.yaml": "eligibility_policy.yaml",
    "application_profile.template.yaml": "application_profile.yaml",
    "onboarding_status.template.yaml": "onboarding_status.yaml",
}


def main() -> int:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    preserved: list[str] = []
    for template_name, local_name in FILES.items():
        source = TEMPLATE_DIR / template_name
        destination = LOCAL_DIR / local_name
        if destination.exists():
            preserved.append(local_name)
            continue
        shutil.copy2(source, destination)
        created.append(local_name)
    print(f"LOCAL_SKELETON_OK created={created} preserved={preserved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

