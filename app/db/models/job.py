from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.db.models.base import CompanyBase


class Job(CompanyBase):
    """`hiremind_company.jobs` — owned by company-service. AI reads it heavily,
    writes only `last_activity_at` / `repost_count` when nudged by recruiters.
    """

    __tablename__ = "jobs"

    # ── identity / ownership ────────────────────────────────────────────────
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    client_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    # ── core posting ────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    role_category: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))
    employment_type: Mapped[str | None] = mapped_column(String(40))
    openings: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    workplace_location: Mapped[str | None] = mapped_column(String(300))
    work_mode: Mapped[str | None] = mapped_column(String(30))
    starting_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[str | None] = mapped_column(Text)

    # ── requirements ────────────────────────────────────────────────────────
    experience_min_years: Mapped[int | None] = mapped_column(SmallInteger)
    experience_max_years: Mapped[int | None] = mapped_column(SmallInteger)
    notice_period: Mapped[str | None] = mapped_column(String(50))
    education_qualification: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    job_shift: Mapped[str | None] = mapped_column(String(80))
    requirement_exp_years: Mapped[int | None] = mapped_column(SmallInteger)
    requirement_exp_unit: Mapped[str | None] = mapped_column(String(10))
    seniority_level: Mapped[str | None] = mapped_column(String(40))

    # ── compensation ────────────────────────────────────────────────────────
    salary_type: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str | None] = mapped_column(String(80))
    annual_ctc: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_min_ctc: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_max_ctc: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    basic_pay: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    hra: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    special_allowance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    other_allowances: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    variable_pay: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    joining_bonus: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    other_benefits: Mapped[str | None] = mapped_column(String(200))

    # ── preferences ────────────────────────────────────────────────────────
    work_arrangement: Mapped[str | None] = mapped_column(String(30))
    pref_work_location: Mapped[str | None] = mapped_column(String(300))
    working_hours: Mapped[str | None] = mapped_column(String(80))
    time_zone: Mapped[str | None] = mapped_column(String(100))
    gender_preference: Mapped[str | None] = mapped_column(String(40))
    diversity_hiring: Mapped[str | None] = mapped_column(String(80))
    equal_opportunity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    additional_preferences: Mapped[str | None] = mapped_column(String(300))

    # ── lifecycle ──────────────────────────────────────────────────────────
    application_deadline: Mapped[date | None] = mapped_column(Date)
    job_expiry: Mapped[date | None] = mapped_column(Date)
    confidential: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'DRAFT'")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── AI / ghost-detection signals (V11/V12) ──────────────────────────────
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    repost_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )

    # ── timestamps ──────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # ── back-compat synonyms ───────────────────────────────────────────────
    # Old service code reads .location, .recruiter_id, .posted_at, .expires_at.
    # Synonyms keep both instance access AND class-level queries working.
    location = synonym("workplace_location")
    recruiter_id = synonym("user_id")
    posted_at = synonym("created_at")
    expires_at = synonym("job_expiry")

    # The old schema stored the recruiter's company name as a string column.
    # In the new schema, company is a FK in another table. For now, the AI
    # service doesn't have the company name handy — return None and let
    # downstream code degrade gracefully (it always treats this as optional).
    @property
    def company(self) -> str | None:
        return None


class JobSkill(CompanyBase):
    """`job_skills` — one row per required/preferred skill on a job."""

    __tablename__ = "job_skills"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    min_experience: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    unit: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'YEARS'")
    )
    mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )


class JobBenefit(CompanyBase):
    __tablename__ = "job_benefits"

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    benefit: Mapped[str] = mapped_column(String(80), primary_key=True)


class JobEmploymentTypePref(CompanyBase):
    __tablename__ = "job_employment_type_prefs"

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    employment_type: Mapped[str] = mapped_column(String(40), primary_key=True)


class JobNoticePeriodPref(CompanyBase):
    __tablename__ = "job_notice_period_prefs"

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    notice_period: Mapped[str] = mapped_column(String(20), primary_key=True)


class JobApplication(CompanyBase):
    """`job_applications` — Module 8 training labels come from `outcome`."""

    __tablename__ = "job_applications"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    candidate_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'APPLIED'")
    )
    match_score: Mapped[int | None] = mapped_column(Integer)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(20))
    outcome_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
