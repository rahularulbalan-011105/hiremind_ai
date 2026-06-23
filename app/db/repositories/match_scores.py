from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import MatchScore


class MatchScoreRepository:
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
        stmt = (
            pg_insert(MatchScore)
            .values(
                candidate_id=candidate_id,
                job_id=job_id,
                score=Decimal(str(round(score, 2))),
                reasoning=reasoning_blob,
            )
            .on_conflict_do_update(
                index_elements=[MatchScore.candidate_id, MatchScore.job_id],
                set_={"score": Decimal(str(round(score, 2))), "reasoning": reasoning_blob},
            )
            .returning(MatchScore)
        )
        result = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return result
