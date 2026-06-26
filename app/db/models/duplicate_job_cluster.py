from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import CompanyBase


class DuplicateJobCluster(CompanyBase):
    """`hiremind_company.duplicate_job_clusters` — Module 6 cache."""

    __tablename__ = "duplicate_job_clusters"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Legacy pair (kept while the schema still carries both — flagged in the audit).
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    duplicate_of_job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    similarity: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)

    # Richer pair added in V10 (preferred — service writes both for now).
    job_a: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    job_b: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    verdict: Mapped[str | None] = mapped_column(Text)
    title_sim: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    embedding_sim: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    skill_jaccard: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
