from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]
Severity = Literal["low", "medium", "high"]
SignalName = Literal[
    "employment_gap",
    "overlap",
    "duplicate_contact",
    "completeness",
    "timeline_inconsistency",
]


class FakeProfileRequest(BaseModel):
    candidate_id: UUID
    force_recompute: bool = False
    github_username: str | None = Field(
        default=None,
        description="Override the GitHub username (otherwise parsed from resume text).",
    )
    skip_github: bool = Field(
        default=False, description="Skip the GitHub cross-check entirely."
    )


class CandidateSummary(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    headline: str | None = None
    location: str | None = None
    skill_count: int
    experience_years: float
    education_count: int
    raw_resume_url: str | None = None


class SignalBreakdown(BaseModel):
    signal: SignalName
    fired: bool
    penalty: int = Field(le=0, description="Negative; how many points subtracted from 100.")
    severity: Severity | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class GitHubCheck(BaseModel):
    checked: bool
    username: str | None = None
    profile_url: str | None = None
    account_age_days: int | None = None
    public_repos: int | None = None
    followers: int | None = None
    top_languages: list[str] = Field(default_factory=list)
    claimed_skills_found_in_repos: list[str] = Field(default_factory=list)
    claimed_skills_missing_in_repos: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class FakeProfileResponse(BaseModel):
    candidate_id: UUID
    candidate: CandidateSummary
    trust_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    reasoning_bullets: list[str]
    score_breakdown: list[SignalBreakdown]
    github_check: GitHubCheck
    cached: bool = False
    computed_at: datetime
