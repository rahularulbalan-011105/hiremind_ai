from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

GhostRiskLevel = Literal["active", "stale", "likely_ghost"]


class GhostScoreRequest(BaseModel):
    job_id: UUID
    force_recompute: bool = False


class GhostSignals(BaseModel):
    posting_age_days: int
    days_since_last_activity: int
    repost_count: int
    match_scores_count: int
    days_since_last_interaction: int | None = Field(
        default=None,
        description="Days since the last match_scores row for this job, or null if none exist.",
    )
    job_status: str


class GhostSignalBreakdown(BaseModel):
    signal: str
    fired: bool
    penalty: int = Field(ge=0)
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class GhostScoreResponse(BaseModel):
    job_id: UUID
    job_title: str
    ghost_score: int = Field(ge=0, le=100)
    risk_classification: GhostRiskLevel
    signals: GhostSignals
    breakdown: list[GhostSignalBreakdown]
    cached: bool = False
    computed_at: datetime
