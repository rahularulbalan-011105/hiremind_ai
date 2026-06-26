from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import CandidateBase


class CandidateExperience(CandidateBase):
    """`candidate_work_experiences` — one row per past/current job."""

    __tablename__ = "candidate_work_experiences"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(180), nullable=False)
    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    location: Mapped[str | None] = mapped_column(String(160))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    currently_working: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    notice_period: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class CandidateEducation(CandidateBase):
    __tablename__ = "candidate_educations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    degree: Mapped[str] = mapped_column(String(160), nullable=False)
    institution: Mapped[str] = mapped_column(String(180), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(255))
    year_of_passing: Mapped[str | None] = mapped_column(String(10))
    grade: Mapped[str | None] = mapped_column(String(40))
    education_type: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(1000))
    attachment_file_keys: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class Skill(CandidateBase):
    """Master skills table — `skills`. Candidate skills FK into this."""

    __tablename__ = "skills"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class CandidateSkill(CandidateBase):
    """`candidate_skills` — junction between candidate and the master `skills` table."""

    __tablename__ = "candidate_skills"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    proficiency_level: Mapped[str] = mapped_column(String(40), nullable=False)
    experience_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    last_used: Mapped[date | None] = mapped_column(Date)
    top_skill: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    additional_details: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class CandidateCertification(CandidateBase):
    __tablename__ = "candidate_certifications"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    certification_name: Mapped[str] = mapped_column(String(160), nullable=False)
    issuing_institution: Mapped[str] = mapped_column(String(160), nullable=False)
    credential_id: Mapped[str | None] = mapped_column(String(160))
    certificate_url: Mapped[str | None] = mapped_column(String(500))
    passed_year: Mapped[int | None] = mapped_column(Integer)
    valid_till: Mapped[date | None] = mapped_column(Date)
    does_not_expire: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    display_on_profile: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    description: Mapped[str | None] = mapped_column(String(500))
    certificate_file_key: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class CandidatePreference(CandidateBase):
    """`candidate_preferences` — typed key/value preferences (ROLE / EMPLOYMENT_TYPE / BENEFIT)."""

    __tablename__ = "candidate_preferences"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    preference_type: Mapped[str] = mapped_column(String(60), nullable=False)
    preference_value: Mapped[str] = mapped_column(String(180), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


# `candidate_languages` was removed in the new schema — kept as a deprecated alias
# only so existing imports don't immediately break. Service code no longer reads it.
class CandidateLanguage:  # pragma: no cover — legacy
    """Removed. Languages are no longer tracked. Kept to avoid breaking imports."""

    __tablename__ = None
