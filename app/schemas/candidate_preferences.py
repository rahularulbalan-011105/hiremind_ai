from __future__ import annotations

from typing import Any, Literal
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
    Tolerant projection of what the candidate-service stores.

    The live schema splits preferences across:
      * scalar columns on `candidate` (notice_period, expected_salary, …)
        — all free-text strings (e.g. "30 Days", "10 – 15 LPA")
      * typed rows in `candidate_preferences` (ROLE / EMPLOYMENT_TYPE / BENEFIT)

    The candidate repo folds them into a single dict; this schema accepts
    every key with a permissive type so the AI service doesn't gatekeep
    whatever the candidate-service decides to store.
    """

    model_config = ConfigDict(extra="allow")

    # ── scalar columns from `candidate` ────────────────────────────────────
    notice_period: str | None = None              # e.g. "30 Days"
    expected_salary: str | SalaryRange | None = None   # e.g. "10 – 15 LPA" OR a structured range
    salary_type: str | None = None                # e.g. "Fixed"
    preferred_location: str | None = None         # e.g. "Bangalore, Chennai"
    open_to_relocate: bool | None = None
    additional_preferences: str | None = None

    # ── typed rows (`candidate_preferences`) folded into buckets ──────────
    roles: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)

    # ── derived from candidate_skills.experience_years ────────────────────
    skill_years: dict[str, float] = Field(default_factory=dict)

    # ── legacy fields still consumed by Match Engine ──────────────────────
    available_notice_days: int | None = Field(
        default=None, ge=0, le=365,
        description="Numeric form of `notice_period` if it parses cleanly.",
    )
    preferred_locations: list[str] = Field(
        default_factory=list,
        description="Lowercase list. Derived from `preferred_location` (comma-split).",
    )
    open_to_remote: bool = True

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        """
        Fill the derived fields from the live columns so downstream code that
        still reads `available_notice_days` / `preferred_locations` keeps working.
        """
        if not isinstance(data, dict):
            return data
        out = dict(data)

        # notice_period (e.g. "30 Days") → available_notice_days (int)
        if out.get("available_notice_days") is None and out.get("notice_period"):
            np_str = str(out["notice_period"]).strip().lower()
            if "immediate" in np_str:
                out["available_notice_days"] = 0
            else:
                token = np_str.split()[0] if np_str.split() else ""
                try:
                    out["available_notice_days"] = int(token)
                except ValueError:
                    pass

        # preferred_location (CSV string) → preferred_locations (list lowercase)
        if not out.get("preferred_locations") and out.get("preferred_location"):
            locs = [
                p.strip().lower()
                for p in str(out["preferred_location"]).split(",")
                if p.strip()
            ]
            if locs:
                out["preferred_locations"] = locs

        # open_to_relocate → open_to_remote default (only if user didn't supply one)
        if "open_to_remote" not in out and out.get("open_to_relocate") is not None:
            out["open_to_remote"] = bool(out["open_to_relocate"])

        return out


class CandidatePreferencesResponse(BaseModel):
    candidate_id: UUID
    preferences: CandidatePreferences
