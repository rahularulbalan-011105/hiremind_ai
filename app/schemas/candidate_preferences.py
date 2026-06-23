from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SalaryRange(BaseModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)
    currency: Literal["INR", "USD", "EUR", "GBP", "SGD", "AED"] = "INR"

    @model_validator(mode="after")
    def _check_range(self) -> "SalaryRange":
        if self.max < self.min:
            raise ValueError("salary.max must be >= salary.min")
        return self


class CandidatePreferences(BaseModel):
    """
    What the candidate has told us / the recruiter has captured manually.
    Stored as a JSONB blob under `candidates.preferences`.
    """

    model_config = ConfigDict(extra="ignore")

    available_notice_days: int | None = Field(
        default=None, ge=0, le=365,
        description="Number of days before they can join.",
    )
    expected_salary: SalaryRange | None = None
    preferred_locations: list[str] = Field(
        default_factory=list,
        description="Acceptable work locations. Lowercase. Empty = no preference.",
    )
    skill_years: dict[str, float] = Field(
        default_factory=dict,
        description="Per-skill years of experience override (skill name lowercase).",
    )
    open_to_remote: bool = True


class CandidatePreferencesResponse(BaseModel):
    candidate_id: UUID
    preferences: CandidatePreferences
