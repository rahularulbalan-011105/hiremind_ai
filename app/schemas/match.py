from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MatchWeights(BaseModel):
    semantic: float = Field(default=0.25, ge=0, le=1)
    skill_overlap: float = Field(default=0.25, ge=0, le=1)
    experience: float = Field(default=0.15, ge=0, le=1)
    location: float = Field(default=0.10, ge=0, le=1)
    notice_period: float = Field(default=0.10, ge=0, le=1)
    salary: float = Field(default=0.15, ge=0, le=1)


class MatchRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID
    force_recompute: bool = False
    weights: MatchWeights | None = Field(
        default=None,
        description="Optional override. Weights are renormalized to sum to 1 if provided.",
    )


class MatchSubscores(BaseModel):
    semantic: float = Field(ge=0, le=100, description="Cosine similarity remapped to [0, 100].")
    skill_overlap: float = Field(ge=0, le=100, description="Fraction of required JD skills the candidate has, weighted by per-skill years.")
    experience: float = Field(ge=0, le=100, description="Years vs JD requirement, capped at 120%.")
    location: float = Field(ge=0, le=100, description="JD location vs candidate location/preferences.")
    notice_period: float = Field(ge=0, le=100, description="Candidate's notice period vs JD's max acceptable.")
    salary: float = Field(ge=0, le=100, description="Candidate's expected salary range vs JD's offered range.")


class MatchResponse(BaseModel):
    candidate_id: UUID
    job_id: UUID
    match_score: int = Field(ge=0, le=100)
    subscores: MatchSubscores
    reasoning: list[str]
    weights_used: MatchWeights
    cached: bool = False
    computed_at: datetime


class MatchByJobRequest(BaseModel):
    job_id: UUID
    top_k: int = Field(default=20, ge=1, le=500)
    weights: MatchWeights | None = None


class DuplicateRef(BaseModel):
    candidate_id: UUID
    full_name: str
    similarity: float = Field(ge=0, le=1)
    kind: Literal["hard", "likely", "similar"] = Field(
        description="hard = exact email/phone match; likely = embedding ≥0.95 + name match; similar = embedding ≥0.90"
    )


class CandidateMatchHit(BaseModel):
    candidate_id: UUID
    full_name: str
    headline: str | None = None
    location: str | None = None
    match_score: int = Field(ge=0, le=100)
    subscores: MatchSubscores
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    candidate_years: float
    summary: str = Field(description="One-line rule-based summary (no LLM call).")
    fake_profile_risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    trust_score: int | None = Field(default=None, ge=0, le=100)
    possible_duplicates: list[DuplicateRef] = Field(default_factory=list)


class MatchByJobResponse(BaseModel):
    job_id: UUID
    job_title: str
    total_candidates_scored: int
    top_k: int
    weights_used: MatchWeights
    hits: list[CandidateMatchHit]
