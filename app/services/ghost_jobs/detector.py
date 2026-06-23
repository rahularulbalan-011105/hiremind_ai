"""
Ghost-job signal detectors. Each detector adds points to the ghost_score —
higher = more likely a ghost posting.

Score in [0, 100]:
  < 30  → active
  30–59 → stale
  ≥ 60  → likely_ghost
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---- Tunable thresholds ----

POSTING_AGE_TIERS = [(30, 10), (60, 10), (120, 15)]
"""Each tuple: (days_threshold, additional_penalty). Stacks cumulatively."""

LAST_ACTIVITY_TIERS = [(30, 15), (60, 15), (90, 20)]

REPOST_TIERS = [(3, 10), (5, 10)]

NO_INTERACTION_AFTER_DAYS = 14
NO_INTERACTION_PENALTY = 10

STALE_INTERACTION_DAYS = 30
STALE_INTERACTION_PENALTY = 5

# Active jobs that are still very fresh — never flag.
FRESH_GRACE_DAYS = 7


@dataclass
class Finding:
    signal: str
    fired: bool
    penalty: int  # always non-negative; bigger = stronger ghost evidence
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def detect_posting_age(posting_age_days: int) -> Finding:
    penalty = 0
    for threshold, points in POSTING_AGE_TIERS:
        if posting_age_days > threshold:
            penalty += points

    if posting_age_days <= FRESH_GRACE_DAYS:
        return Finding(
            signal="posting_age",
            fired=False,
            penalty=0,
            message=f"Posted {posting_age_days} day(s) ago — fresh.",
            details={"posting_age_days": posting_age_days},
        )

    if penalty == 0:
        return Finding(
            signal="posting_age",
            fired=False,
            penalty=0,
            message=f"Posted {posting_age_days} day(s) ago — within normal range.",
            details={"posting_age_days": posting_age_days},
        )

    return Finding(
        signal="posting_age",
        fired=True,
        penalty=penalty,
        message=f"Posting is {posting_age_days} day(s) old.",
        details={"posting_age_days": posting_age_days},
    )


def detect_last_activity(days_since_last_activity: int) -> Finding:
    penalty = 0
    for threshold, points in LAST_ACTIVITY_TIERS:
        if days_since_last_activity > threshold:
            penalty += points

    if penalty == 0:
        return Finding(
            signal="last_activity",
            fired=False,
            penalty=0,
            message=f"Recruiter activity within the last {days_since_last_activity} day(s).",
            details={"days_since_last_activity": days_since_last_activity},
        )

    return Finding(
        signal="last_activity",
        fired=True,
        penalty=penalty,
        message=f"No recruiter activity for {days_since_last_activity} day(s).",
        details={"days_since_last_activity": days_since_last_activity},
    )


def detect_repost(repost_count: int) -> Finding:
    penalty = 0
    for threshold, points in REPOST_TIERS:
        if repost_count >= threshold:
            penalty += points

    if penalty == 0:
        return Finding(
            signal="repost_count",
            fired=False,
            penalty=0,
            message=f"Reposted {repost_count} time(s) — within normal range.",
            details={"repost_count": repost_count},
        )

    return Finding(
        signal="repost_count",
        fired=True,
        penalty=penalty,
        message=f"Reposted {repost_count} time(s) — high repost cadence suggests recycling.",
        details={"repost_count": repost_count},
    )


def detect_zero_interaction(
    posting_age_days: int, match_scores_count: int
) -> Finding:
    if posting_age_days <= NO_INTERACTION_AFTER_DAYS:
        return Finding(
            signal="zero_interaction",
            fired=False,
            penalty=0,
            message=f"Posting is only {posting_age_days} day(s) old; too early to judge candidate interaction.",
            details={"posting_age_days": posting_age_days, "match_scores_count": match_scores_count},
        )
    if match_scores_count > 0:
        return Finding(
            signal="zero_interaction",
            fired=False,
            penalty=0,
            message=f"{match_scores_count} candidate(s) have been scored against this job.",
            details={"match_scores_count": match_scores_count},
        )
    return Finding(
        signal="zero_interaction",
        fired=True,
        penalty=NO_INTERACTION_PENALTY,
        message=f"No candidates have been scored against this {posting_age_days}-day-old posting.",
        details={"posting_age_days": posting_age_days, "match_scores_count": 0},
    )


def detect_stale_interaction(
    days_since_last_interaction: int | None, match_scores_count: int
) -> Finding:
    if match_scores_count == 0 or days_since_last_interaction is None:
        return Finding(
            signal="stale_interaction",
            fired=False,
            penalty=0,
            message="N/A — no prior candidate interactions to compare against.",
        )
    if days_since_last_interaction <= STALE_INTERACTION_DAYS:
        return Finding(
            signal="stale_interaction",
            fired=False,
            penalty=0,
            message=f"Most recent candidate scored {days_since_last_interaction} day(s) ago.",
            details={"days_since_last_interaction": days_since_last_interaction},
        )
    return Finding(
        signal="stale_interaction",
        fired=True,
        penalty=STALE_INTERACTION_PENALTY,
        message=f"Last candidate scored {days_since_last_interaction} day(s) ago — interaction has gone cold.",
        details={"days_since_last_interaction": days_since_last_interaction},
    )


def ghost_score_from_findings(findings: list[Finding]) -> int:
    total = sum(f.penalty for f in findings)
    return min(100, max(0, total))


def risk_classification_from_score(score: int) -> str:
    if score >= 60:
        return "likely_ghost"
    if score >= 30:
        return "stale"
    return "active"
