from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import CompanyBase


class GhostJobScore(CompanyBase):
    """`hiremind_company.ghost_job_scores` — Module 7 cache.

    Column rename note: the live schema uses `classification` (not the older
    `risk_classification`). The Pydantic-facing field name is preserved by a
    property in the service layer, so callers don't have to change.
    """

    __tablename__ = "ghost_job_scores"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    ghost_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    signals: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Back-compat alias for service code that still says `risk_classification`.
    @property
    def risk_classification(self) -> str:
        return self.classification

    @risk_classification.setter
    def risk_classification(self, value: str) -> None:
        self.classification = value
