from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import FakeProfileScore


class FakeProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, candidate_id: UUID) -> FakeProfileScore | None:
        return self.session.execute(
            select(FakeProfileScore).where(FakeProfileScore.candidate_id == candidate_id)
        ).scalar_one_or_none()

    def get_many(self, candidate_ids: list[UUID]) -> dict[UUID, FakeProfileScore]:
        if not candidate_ids:
            return {}
        rows = self.session.execute(
            select(FakeProfileScore).where(FakeProfileScore.candidate_id.in_(candidate_ids))
        ).scalars().all()
        return {row.candidate_id: row for row in rows}

    def upsert(
        self,
        candidate_id: UUID,
        trust_score: float,
        risk_level: str,
        anomalies_blob: dict,
    ) -> FakeProfileScore:
        stmt = (
            pg_insert(FakeProfileScore)
            .values(
                candidate_id=candidate_id,
                trust_score=Decimal(str(round(trust_score, 2))),
                risk_level=risk_level,
                anomalies=anomalies_blob,
            )
            .on_conflict_do_update(
                index_elements=[FakeProfileScore.candidate_id],
                set_={
                    "trust_score": Decimal(str(round(trust_score, 2))),
                    "risk_level": risk_level,
                    "anomalies": anomalies_blob,
                },
            )
            .returning(FakeProfileScore)
        )
        result = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return result
