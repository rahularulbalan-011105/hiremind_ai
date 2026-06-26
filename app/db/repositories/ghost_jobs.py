from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import GhostJobScore


class GhostJobRepository:
    """Lives in `hiremind_company`. Column is `classification` in the live schema —
    we keep the `risk_classification` kwarg name for backwards-compatibility."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, job_id: UUID) -> GhostJobScore | None:
        return self.session.execute(
            select(GhostJobScore).where(GhostJobScore.job_id == job_id)
        ).scalar_one_or_none()

    def upsert(
        self,
        *,
        job_id: UUID,
        ghost_score: float,
        risk_classification: str,
        signals_blob: dict,
    ) -> GhostJobScore:
        score_dec = Decimal(str(round(ghost_score, 2)))
        stmt = (
            pg_insert(GhostJobScore)
            .values(
                job_id=job_id,
                ghost_score=score_dec,
                classification=risk_classification,
                signals=signals_blob,
            )
            .on_conflict_do_update(
                index_elements=[GhostJobScore.job_id],
                set_={
                    "ghost_score": score_dec,
                    "classification": risk_classification,
                    "signals": signals_blob,
                },
            )
            .returning(GhostJobScore)
        )
        result = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return result
