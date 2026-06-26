from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import CompanyBase


class HiringPrediction(CompanyBase):
    """`hiremind_company.hiring_predictions` — Module 8 cache.

    `candidate_id` is a bare UUID (cross-DB) — no FK constraint. Unique key in
    the live schema is `(candidate_id, job_id, model_version)`, which lets
    multiple model versions coexist for the same pair.
    """

    __tablename__ = "hiring_predictions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # Stores: {"features_used": {...}, "shap_explanations": [...]}
    shap: Mapped[dict | list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    # NEW in V10 — split out of the old shap blob, lets us filter by predictor type.
    model_type: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
