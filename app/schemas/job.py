from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JobSalaryRange(BaseModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)
    currency: Literal["INR", "USD", "EUR", "GBP", "SGD", "AED"] = "INR"

    @model_validator(mode="after")
    def _check_range(self) -> "JobSalaryRange":
        if self.max < self.min:
            raise ValueError("salary.max must be >= salary.min")
        return self


class RequiredSkill(BaseModel):
    skill: str = Field(min_length=1, max_length=80)
    min_years: float = Field(default=0, ge=0, le=50)

    @field_validator("skill", mode="after")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class JobCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10)
    company: str | None = None
    location: str | None = None
    employment_type: str | None = None
    required_skills: list[RequiredSkill] = Field(
        default_factory=list,
        description="Each entry: {skill: 'python', min_years: 5}. min_years defaults to 0 (any).",
    )
    required_years_experience: float | None = Field(
        default=None, ge=0, le=50,
        description="Minimum total years of relevant experience.",
    )
    notice_period_days_max: int | None = Field(
        default=None, ge=0, le=365,
        description="Maximum acceptable notice period of the candidate, in days.",
    )
    salary: JobSalaryRange | None = Field(
        default=None,
        description="Compensation range. Match scoring is more accurate when set.",
    )

    @field_validator("required_skills", mode="after")
    @classmethod
    def _dedup_skills(cls, v: list[RequiredSkill]) -> list[RequiredSkill]:
        seen: set[str] = set()
        out: list[RequiredSkill] = []
        for entry in v:
            key = entry.skill
            if key and key not in seen:
                seen.add(key)
                out.append(entry)
        return out


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    company: str | None = None
    location: str | None = None
    employment_type: str | None = None
    status: Literal["active", "paused", "closed", "archived"]
    required_skills: list[RequiredSkill] = Field(default_factory=list)
    required_years_experience: float | None = None
    notice_period_days_max: int | None = None
    salary: JobSalaryRange | None = None
    embedding_stored: bool = False
    posted_at: datetime
    last_activity_at: datetime
