from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _LooseDate(BaseModel):
    """Helper — Grok/users sometimes return partial dates; we tolerate that."""

    model_config = ConfigDict(extra="ignore")


# ---------- LLM-produced parse schema (what the prompt promises) ----------


class ParsedExperience(BaseModel):
    company: str
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v in ("", None):
            return None
        return v


class ParsedEducation(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v in ("", None):
            return None
        return v


class ParsedCertification(BaseModel):
    name: str
    issuer: str | None = None
    issued_date: date | None = None
    expires_date: date | None = None

    @field_validator("issued_date", "expires_date", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v in ("", None):
            return None
        return v


class ParsedLanguage(BaseModel):
    language: str
    proficiency: str | None = None


class ParsedResume(BaseModel):
    """Strict schema the LLM output must satisfy."""

    model_config = ConfigDict(extra="ignore")

    full_name: str
    email: str | None = None
    phone: str | None = None
    headline: str | None = None
    location: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ParsedExperience] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
    certifications: list[ParsedCertification] = Field(default_factory=list)
    languages: list[ParsedLanguage] = Field(default_factory=list)


# ---------- API DTOs ----------


ParseJobStatus = Literal["queued", "running", "succeeded", "failed"]


class ParseJobAccepted(BaseModel):
    parse_job_id: UUID
    status: ParseJobStatus = "queued"


class ParseJobStatusResponse(BaseModel):
    parse_job_id: UUID
    status: ParseJobStatus
    candidate_id: UUID | None = None
    source_url: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class CandidateProfile(BaseModel):
    id: UUID
    full_name: str
    email: str | None = None
    phone: str | None = None
    headline: str | None = None
    location: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ParsedExperience] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
    certifications: list[ParsedCertification] = Field(default_factory=list)
    languages: list[ParsedLanguage] = Field(default_factory=list)
    raw_resume_url: str | None = None
    created_at: datetime
