from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import MatchScore


class MatchScoreRepository:
    """Lives in `hiremind_company`. `candidate_id` is a bare UUID (cross-DB)."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, candidate_id: UUID, job_id: UUID) -> MatchScore | None:
        return self.session.execute(
            select(MatchScore).where(
                MatchScore.candidate_id == candidate_id,
                MatchScore.job_id == job_id,
            )
        ).scalar_one_or_none()

    def upsert(
        self,
        candidate_id: UUID,
        job_id: UUID,
        score: float,
        reasoning_blob: dict,
    ) -> MatchScore:
        """
        Accepts the legacy `reasoning_blob` shape:
            {"bullets": [...], "subscores": {...}, "weights": {...}}
        and splits it into the three top-level JSONB columns on the new schema.
        """
        bullets = reasoning_blob.get("bullets", []) if isinstance(reasoning_blob, dict) else []
        subscores = reasoning_blob.get("subscores", {}) if isinstance(reasoning_blob, dict) else {}
        weights = reasoning_blob.get("weights", {}) if isinstance(reasoning_blob, dict) else {}

        score_dec = Decimal(str(round(score, 2)))
        stmt = (
            pg_insert(MatchScore)
            .values(
                candidate_id=candidate_id,
                job_id=job_id,
                score=score_dec,
                reasoning=bullets,
                subscores=subscores,
                weights=weights,
            )
            .on_conflict_do_update(
                index_elements=[MatchScore.candidate_id, MatchScore.job_id],
                set_={
                    "score": score_dec,
                    "reasoning": bullets,
                    "subscores": subscores,
                    "weights": weights,
                },
            )
            .returning(MatchScore)
        )
        result = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return result
