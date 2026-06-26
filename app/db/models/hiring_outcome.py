from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import CompanyBase


class HiringOutcome(CompanyBase):
    """`hiremind_company.hiring_outcomes` — Module 8 training labels.

    Real outcomes get synced from `job_applications.outcome` once the recruiter
    marks an application terminal. Synthetic seed rows for cold-start training
    still go here too (see `scripts/seed_hiring_outcomes.py`).
    """

    __tablename__ = "hiring_outcomes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(Text, nullable=False)  # hired / rejected / withdrawn / no_show
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
