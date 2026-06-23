from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DuplicateVerdict = Literal["hard", "likely", "similar"]


class DuplicateCheckRequest(BaseModel):
    job_id: UUID
    force_recompute: bool = False
    max_candidates: int = Field(
        default=50, ge=1, le=200,
        description="HNSW pre-filter top-N (cosine distance) before fuzzy/skills check.",
    )


class DuplicateMatch(BaseModel):
    duplicate_job_id: UUID
    title: str
    company: str | None = None
    title_similarity: float = Field(ge=0, le=1)
    embedding_similarity: float = Field(ge=0, le=1)
    shared_required_skills: list[str] = Field(default_factory=list)
    same_company: bool
    verdict: DuplicateVerdict


class DuplicateCheckResponse(BaseModel):
    job_id: UUID
    job_title: str
    total_compared: int
    duplicates: list[DuplicateMatch]
    cached: bool = False
    computed_at: datetime
