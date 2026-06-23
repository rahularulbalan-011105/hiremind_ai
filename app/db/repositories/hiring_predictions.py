from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import HiringPrediction


class HiringPredictionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(
        self, candidate_id: UUID, job_id: UUID, model_version: str
    ) -> HiringPrediction | None:
        return self.session.execute(
            select(HiringPrediction).where(
                HiringPrediction.candidate_id == candidate_id,
                HiringPrediction.job_id == job_id,
                HiringPrediction.model_version == model_version,
            )
        ).scalar_one_or_none()

    def upsert(
        self,
        *,
        candidate_id: UUID,
        job_id: UUID,
        probability: float,
        confidence: float,
        shap_blob: dict,
        model_version: str,
    ) -> HiringPrediction:
        stmt = (
            pg_insert(HiringPrediction)
            .values(
                candidate_id=candidate_id,
                job_id=job_id,
                probability=Decimal(str(round(probability, 4))),
                confidence=Decimal(str(round(confidence, 4))),
                shap=shap_blob,
                model_version=model_version,
            )
            .on_conflict_do_update(
                index_elements=[
                    HiringPrediction.candidate_id,
                    HiringPrediction.job_id,
                    HiringPrediction.model_version,
                ],
                set_={
                    "probability": Decimal(str(round(probability, 4))),
                    "confidence": Decimal(str(round(confidence, 4))),
                    "shap": shap_blob,
                },
            )
            .returning(HiringPrediction)
        )
        result = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return result
