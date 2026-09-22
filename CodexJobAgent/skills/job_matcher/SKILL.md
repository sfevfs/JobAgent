---
name: job-matcher
description: Offline, evidence-grounded matching of public job descriptions against the user's confirmed private resume facts. Never apply, contact recruiters, edit platform profiles, or operate a phone.
---

# Job Matcher

Use `scripts/job_matcher.py` only after `scripts/validate_profile.py` returns `PROFILE_OK`.

## Required inputs

- `.local/resume_facts.yaml`: sole source of candidate facts.
- `.local/profile.yaml`: target roles and preferences.
- `.local/eligibility_policy.yaml`: hard eligibility and unknown boundaries.
- `config/scoring.yaml`: scoring dimensions and decisions.

Missing fields remain unknown. Never infer candidate experience, skills, publications, employment, internships, project results, language credentials, work authorization or location intent.

## Workflow

1. Parse a JD into required/preferred skills, education, experience, domain, language, location and safety constraints.
2. Keep technical match, eligibility and preference separate.
3. Use only skills and projects present in the private fact file. Project evidence is based on explicit confirmed keywords; a similar field without overlapping evidence is transferable at most.
4. Return explainable JSON with matched and missing requirements, evidence, risks and a local-only recommendation.
5. A `selected` result means only that the record may enter a local review queue.

## Safety boundary

This skill has no permission to open application controls, upload a resume, message a recruiter, change a platform profile, bypass verification or perform any real-world application. Every real application requires the user to approve a concrete job or listed batch after reviewing the generated material.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts\job_matcher.py --input examples\jds\sample_general_ai.json
```

The built-in three-track classifier covers communication AI, medical/CV and general AI. For a different profession, recalibrate the classifier and create new synthetic validation fixtures before using scores for decisions.

