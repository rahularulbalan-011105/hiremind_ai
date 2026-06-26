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
        model_type: str | None = None,
    ) -> HiringPrediction:
        # If model_type wasn't passed but is embedded in the shap_blob (legacy
        # callers stored it there), lift it out into the dedicated column.
        if model_type is None and isinstance(shap_blob, dict):
            model_type = shap_blob.get("model_type")

        prob = Decimal(str(round(probability, 4)))
        conf = Decimal(str(round(confidence, 4)))
        stmt = (
            pg_insert(HiringPrediction)
            .values(
                candidate_id=candidate_id,
                job_id=job_id,
                probability=prob,
                confidence=conf,
                shap=shap_blob,
                model_version=model_version,
                model_type=model_type,
            )
            .on_conflict_do_update(
                index_elements=[
                    HiringPrediction.candidate_id,
                    HiringPrediction.job_id,
                    HiringPrediction.model_version,
                ],
                set_={
                    "probability": prob,
                    "confidence": conf,
                    "shap": shap_blob,
                    "model_type": model_type,
                },
            )
            .returning(HiringPrediction)
        )
        result = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return result
