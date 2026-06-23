from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RankerWeights(BaseModel):
    match: float = Field(default=0.45, ge=0, le=1)
    hiring_probability: float = Field(default=0.30, ge=0, le=1)
    trust: float = Field(default=0.15, ge=0, le=1)
    experience: float = Field(default=0.10, ge=0, le=1)


class RankerRequest(BaseModel):
    job_id: UUID
    top_k: int = Field(default=20, ge=1, le=500)
    weights: RankerWeights | None = None
    force_recompute: bool = False


class CompareRequest(BaseModel):
    job_id: UUID
    candidate_ids: list[UUID] = Field(min_length=1, max_length=20)
    weights: RankerWeights | None = None


class RankerComponents(BaseModel):
    match_score: int = Field(ge=0, le=100)
    hiring_probability: int = Field(ge=0, le=100, description="probability * 100, rounded.")
    trust_score: int = Field(ge=0, le=100)
    experience_score: int = Field(ge=0, le=100, description="min(years/15, 1) * 100.")


class RankedHit(BaseModel):
    rank: int
    candidate_id: UUID
    full_name: str
    headline: str | None = None
    location: str | None = None
    final_score: int = Field(ge=0, le=100)
    components: RankerComponents
    candidate_years: float
    fake_profile_risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    hiring_probability_raw: float = Field(ge=0, le=1)
    hiring_model_type: Literal["xgboost", "rules"] | None = None
    match_summary: str = Field(description="One-line summary of matched/missing skills + experience gap.")


class RankerResponse(BaseModel):
    job_id: UUID
    job_title: str
    total_candidates_ranked: int
    top_k: int
    weights_used: RankerWeights
    hits: list[RankedHit]
    computed_at: datetime


class CompareResponse(BaseModel):
    job_id: UUID
    job_title: str
    weights_used: RankerWeights
    hits: list[RankedHit]
    computed_at: datetime
