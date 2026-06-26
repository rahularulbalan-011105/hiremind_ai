from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import FakeProfileScore


class FakeProfileRepository:
    """Lives in `hiremind_candidate`."""

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
        """
        Accepts the legacy blob shape:
            {"breakdown": [...], "bullets": [...], "github_check": {...}, "anomalies": [...]}
        Splits it into the live schema's four JSONB columns.
        """
        breakdown = anomalies_blob.get("breakdown", []) if isinstance(anomalies_blob, dict) else []
        bullets = anomalies_blob.get("bullets", []) if isinstance(anomalies_blob, dict) else []
        github_check = (
            anomalies_blob.get("github_check", {}) if isinstance(anomalies_blob, dict) else {}
        )
        anomalies = (
            anomalies_blob.get("anomalies", []) if isinstance(anomalies_blob, dict) else []
        )

        score_dec = Decimal(str(round(trust_score, 2)))
        stmt = (
            pg_insert(FakeProfileScore)
            .values(
                candidate_id=candidate_id,
                trust_score=score_dec,
                risk_level=risk_level,
                anomalies=anomalies,
                breakdown=breakdown,
                bullets=bullets,
                github_check=github_check,
            )
            .on_conflict_do_update(
                index_elements=[FakeProfileScore.candidate_id],
                set_={
                    "trust_score": score_dec,
                    "risk_level": risk_level,
                    "anomalies": anomalies,
                    "breakdown": breakdown,
                    "bullets": bullets,
                    "github_check": github_check,
                },
            )
            .returning(FakeProfileScore)
        )
        result = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return result
