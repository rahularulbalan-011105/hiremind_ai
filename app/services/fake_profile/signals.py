"""
Pure-function detectors for the Fake Profile Detector module.

Each detector takes structured candidate data and returns a `Finding` describing
whether the signal fired, the penalty to subtract from the trust score, a
human-readable message, and structured details for the UI.

Penalty caps per signal live in `PENALTIES` — one noisy dimension can't crater
the score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# ---------- Tunable thresholds ----------

GAP_MIN_MONTHS = 6
OVERLAP_MIN_DAYS = 30
COMPLETENESS_SKILL_THRESHOLD = 10
COMPLETENESS_REQUIRED_FIELDS = ("headline", "location", "phone")  # all must be filled
COMPLETENESS_BONUS_FIELDS = ("certifications", "languages")  # both must be non-empty

PENALTIES = {
    "employment_gap": {"each": 10, "cap": 30},
    "overlap": {"each": 15, "cap": 30},
    "duplicate_contact": {"each": 25, "cap": 40},
    "completeness": {"each": 5, "cap": 5},
    "timeline_inconsistency": {"each": 20, "cap": 20},
}

# ---------- Data shapes ----------


@dataclass(frozen=True)
class ExperienceRow:
    company: str
    title: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool


@dataclass(frozen=True)
class EducationRow:
    institution: str
    start_date: date | None
    end_date: date | None


@dataclass
class Finding:
    signal: str
    fired: bool
    penalty: int  # positive int; sign is applied at composition time
    severity: str | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)


# ---------- Detectors ----------


def detect_employment_gaps(experiences: list[ExperienceRow], *, today: date) -> Finding:
    intervals: list[tuple[date, date, str]] = []
    for e in experiences:
        if e.start_date is None:
            continue
        end = e.end_date or today
        if end < e.start_date:
            continue
        intervals.append((e.start_date, end, e.company))

    intervals.sort()
    gaps: list[dict] = []
    for prev, cur in zip(intervals, intervals[1:]):
        prev_end = prev[1]
        cur_start = cur[0]
        if cur_start <= prev_end:
            continue
        months = _months_between(prev_end, cur_start)
        if months >= GAP_MIN_MONTHS:
            gaps.append({
                "from_company": prev[2],
                "to_company": cur[2],
                "from_date": prev_end.isoformat(),
                "to_date": cur_start.isoformat(),
                "gap_months": months,
            })

    if not gaps:
        return Finding(
            signal="employment_gap",
            fired=False,
            penalty=0,
            severity=None,
            message="No employment gaps ≥ 6 months detected.",
        )

    rule = PENALTIES["employment_gap"]
    penalty = min(rule["each"] * len(gaps), rule["cap"])
    severity = "high" if penalty >= rule["cap"] else "medium"
    msg = f"{len(gaps)} employment gap(s) ≥ 6 months detected."
    return Finding(
        signal="employment_gap",
        fired=True,
        penalty=penalty,
        severity=severity,
        message=msg,
        details={"gaps": gaps},
    )


def detect_overlaps(experiences: list[ExperienceRow], *, today: date) -> Finding:
    full_time = [
        (e.start_date, e.end_date or today, e.company, e.title)
        for e in experiences
        if e.start_date is not None
    ]
    overlaps: list[dict] = []
    for i in range(len(full_time)):
        for j in range(i + 1, len(full_time)):
            a_start, a_end, a_co, _ = full_time[i]
            b_start, b_end, b_co, _ = full_time[j]
            overlap_days = (min(a_end, b_end) - max(a_start, b_start)).days
            if overlap_days > OVERLAP_MIN_DAYS:
                overlaps.append({
                    "company_a": a_co,
                    "company_b": b_co,
                    "overlap_days": overlap_days,
                })

    if not overlaps:
        return Finding(
            signal="overlap",
            fired=False,
            penalty=0,
            severity=None,
            message="No overlapping full-time roles detected.",
        )

    rule = PENALTIES["overlap"]
    penalty = min(rule["each"] * len(overlaps), rule["cap"])
    severity = "high" if penalty >= rule["cap"] else "medium"
    return Finding(
        signal="overlap",
        fired=True,
        penalty=penalty,
        severity=severity,
        message=f"{len(overlaps)} pair(s) of overlapping employment detected.",
        details={"overlaps": overlaps},
    )


def detect_duplicate_contact(
    *,
    email_matches: list[str],
    phone_matches: list[str],
) -> Finding:
    if not email_matches and not phone_matches:
        return Finding(
            signal="duplicate_contact",
            fired=False,
            penalty=0,
            severity=None,
            message="Email and phone are unique in the database.",
        )

    n = len(email_matches) + len(phone_matches)
    rule = PENALTIES["duplicate_contact"]
    penalty = min(rule["each"] * n, rule["cap"])
    parts: list[str] = []
    if email_matches:
        parts.append(f"email shared with {len(email_matches)} other candidate(s)")
    if phone_matches:
        parts.append(f"phone shared with {len(phone_matches)} other candidate(s)")
    return Finding(
        signal="duplicate_contact",
        fired=True,
        penalty=penalty,
        severity="high",
        message=" + ".join(parts).capitalize() + ".",
        details={
            "matched_by_email": email_matches,
            "matched_by_phone": phone_matches,
        },
    )


def detect_perfect_completeness(
    *,
    has_headline: bool,
    has_location: bool,
    has_phone: bool,
    has_certifications: bool,
    has_languages: bool,
    skill_count: int,
) -> Finding:
    all_required = has_headline and has_location and has_phone
    bonus = has_certifications and has_languages
    too_many_skills = skill_count >= COMPLETENESS_SKILL_THRESHOLD

    if not (all_required and bonus and too_many_skills):
        return Finding(
            signal="completeness",
            fired=False,
            penalty=0,
            severity=None,
            message="Profile completeness is normal.",
        )

    rule = PENALTIES["completeness"]
    return Finding(
        signal="completeness",
        fired=True,
        penalty=rule["each"],
        severity="low",
        message=(
            f"Every optional field filled and {skill_count} skills listed — "
            "matches the pattern of templated / AI-generated resumes."
        ),
        details={
            "headline": has_headline,
            "location": has_location,
            "phone": has_phone,
            "certifications": has_certifications,
            "languages": has_languages,
            "skill_count": skill_count,
        },
    )


def detect_timeline_inconsistency(
    *,
    earliest_education_end: date | None,
    earliest_job_start: date | None,
) -> Finding:
    if earliest_education_end is None or earliest_job_start is None:
        return Finding(
            signal="timeline_inconsistency",
            fired=False,
            penalty=0,
            severity=None,
            message="Education timeline could not be compared (missing dates).",
        )
    if earliest_education_end <= earliest_job_start:
        return Finding(
            signal="timeline_inconsistency",
            fired=False,
            penalty=0,
            severity=None,
            message="Education timeline is consistent with employment history.",
        )

    rule = PENALTIES["timeline_inconsistency"]
    return Finding(
        signal="timeline_inconsistency",
        fired=True,
        penalty=rule["each"],
        severity="medium",
        message=(
            f"First job started on {earliest_job_start.isoformat()} but earliest education "
            f"end date is {earliest_education_end.isoformat()} — likely date inconsistency."
        ),
        details={
            "earliest_education_end": earliest_education_end.isoformat(),
            "earliest_job_start": earliest_job_start.isoformat(),
        },
    )


# ---------- Composition ----------


def trust_score_from_findings(findings: list[Finding]) -> int:
    score = 100 - sum(f.penalty for f in findings)
    return max(0, min(100, score))


def risk_level_from_score(score: int) -> str:
    if score >= 70:
        return "low"
    if score >= 40:
        return "medium"
    return "high"


# ---------- helpers ----------


def _months_between(d1: date, d2: date) -> int:
    months = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        months -= 1
    return max(0, months)
