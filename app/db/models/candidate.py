from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.db.models.base import CandidateBase


class Candidate(CandidateBase):
    """`hiremind_candidate.candidate` — the live row maintained by candidate-service.

    The AI service writes a subset of columns:
      * `raw_resume_text`, `headline`, `github_username`, `parse_job_id` after a parse
      * scalar prefs (`notice_period`, `expected_salary`, `preferred_location`, etc.)
        come from candidate-service; the AI reads them, doesn't write them
    """

    __tablename__ = "candidate"

    # ── identity ────────────────────────────────────────────────────────────
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # ── core profile ────────────────────────────────────────────────────────
    full_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(180))
    country_code: Mapped[str | None] = mapped_column(String(8))
    phone_number: Mapped[str | None] = mapped_column(String(30))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    current_location: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))

    # ── current role ────────────────────────────────────────────────────────
    current_job_role: Mapped[str | None] = mapped_column(String(160))
    current_company: Mapped[str | None] = mapped_column(String(180))
    total_experience_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    # ── preferences (scalar) ────────────────────────────────────────────────
    notice_period: Mapped[str | None] = mapped_column(String(80))
    expected_salary: Mapped[str | None] = mapped_column(String(80))
    salary_type: Mapped[str | None] = mapped_column(String(40))
    preferred_location: Mapped[str | None] = mapped_column(String(180))
    open_to_relocate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    additional_preferences: Mapped[str | None] = mapped_column(String(500))
    available_for_job_search: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # ── profile state ──────────────────────────────────────────────────────
    profile_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'DRAFT'")
    )
    profile_strength: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── assets ──────────────────────────────────────────────────────────────
    resume_file_key: Mapped[str | None] = mapped_column(String(500))
    profile_picture_key: Mapped[str | None] = mapped_column(String(500))
    professional_summary: Mapped[str | None] = mapped_column(Text)

    # ── AI columns (added in V10/V11) ──────────────────────────────────────
    raw_resume_text: Mapped[str | None] = mapped_column(Text)
    github_username: Mapped[str | None] = mapped_column(String(80))
    parse_job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    headline: Mapped[str | None] = mapped_column(String(255))

    # ── timestamps ──────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    # ── back-compat aliases ────────────────────────────────────────────────
    # The old schema used `phone`, `location`, `raw_text`, `raw_resume_url`.
    # SQLAlchemy `synonym()` exposes both instance access (`candidate.phone`)
    # AND class-level access for queries (`select(Candidate.phone)`) — so
    # legacy callers and queries both continue to work.
    phone = synonym("phone_number")
    location = synonym("current_location")
    raw_text = synonym("raw_resume_text")
    raw_resume_url = synonym("resume_file_key")
