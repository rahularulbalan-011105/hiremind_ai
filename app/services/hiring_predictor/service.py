from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.hiring_predictions import HiringPredictionRepository
from app.db.repositories.jobs import JobRepository
from app.llm import LLMClient
from app.schemas.hiring_predictor import (
    FeatureContribution,
    HiringProbabilityResponse,
    ModelType,
)
from app.services.hiring_predictor.features import FeatureExtractor, FeatureVector
from app.services.hiring_predictor.rules_predictor import predict_rules
from app.services.hiring_predictor.xgboost_predictor import (
    XGBoostPredictor,
    try_load_xgboost,
)

log = get_logger(__name__)


class HiringPredictorService:
    """
    Picks the best available predictor at construction time:
      - XGBoost if MODEL_VERSION exists on disk
      - Rules-based otherwise

    The pick is fixed for the lifetime of the service (lazy-loaded on the
    FastAPI app state). Hot-reload of a newly trained model = restart uvicorn.
    """

    def __init__(self, settings: Settings, llm: LLMClient):
        self.settings = settings
        self.extractor = FeatureExtractor(llm=llm)
        self._xgb: XGBoostPredictor | None = try_load_xgboost(
            settings.model_registry_path, settings.model_version
        )
        if self._xgb is not None:
            log.info(
                "hiring_predictor_using_xgboost",
                version=self._xgb.version,
                trained_at=self._xgb.metadata.get("trained_at"),
            )
        else:
            log.info(
                "hiring_predictor_using_rules",
                reason="No XGBoost model on disk — train via scripts/train_model.py",
            )

    @property
    def model_type(self) -> ModelType:
        return "xgboost" if self._xgb is not None else "rules"

    @property
    def model_version(self) -> str:
        if self._xgb is not None:
            return self._xgb.version
        return f"rules-{self.settings.model_version}"

    def predict(
        self,
        candidate_session: Session,
        company_session: Session,
        *,
        candidate_id: UUID,
        job_id: UUID,
        force_recompute: bool,
        include_shap: bool,
    ) -> HiringProbabilityResponse:
        if not CandidateRepository(candidate_session).exists(candidate_id):
            raise NotFoundError(f"Candidate {candidate_id} not found.")
        if not JobRepository(company_session).exists(job_id):
            raise NotFoundError(f"Job {job_id} not found.")

        repo = HiringPredictionRepository(company_session)
        if not force_recompute:
            cached = repo.get(candidate_id, job_id, self.model_version)
            if cached is not None:
                return self._cached_to_response(cached, include_shap)

        fv: FeatureVector = self.extractor.extract(
            candidate_session, company_session,
            candidate_id=candidate_id, job_id=job_id,
        )

        if self._xgb is not None:
            result = self._xgb.predict(fv)
        else:
            result = predict_rules(fv)

        shap_blob = {
            "features_used": fv.values,
            "shap_explanations": [
                {"feature": name, "contribution": round(c, 6)}
                for name, c in result.contributions
            ],
            "model_type": self.model_type,
        }
        row = repo.upsert(
            candidate_id=candidate_id,
            job_id=job_id,
            probability=result.probability,
            confidence=result.confidence,
            shap_blob=shap_blob,
            model_version=self.model_version,
            model_type=self.model_type,
        )

        return HiringProbabilityResponse(
            candidate_id=candidate_id,
            job_id=job_id,
            probability=result.probability,
            confidence=result.confidence,
            model_version=self.model_version,
            model_type=self.model_type,
            features_used={k: round(v, 4) for k, v in fv.values.items()},
            shap_explanations=(
                [
                    FeatureContribution(feature=n, contribution=round(c, 6))
                    for n, c in result.contributions
                ]
                if include_shap
                else []
            ),
            cached=False,
            computed_at=_aware(row.computed_at),
        )

    # ---------- internals ----------

    def _cached_to_response(self, row, include_shap: bool) -> HiringProbabilityResponse:
        # The live schema stores model_type as a dedicated column; the
        # features_used + shap_explanations payload still lives in `shap`.
        blob = row.shap if isinstance(row.shap, dict) else {}
        features = blob.get("features_used") or {}
        shap_list = blob.get("shap_explanations") or []
        model_type_used = row.model_type or blob.get("model_type", self.model_type)
        return HiringProbabilityResponse(
            candidate_id=row.candidate_id,
            job_id=row.job_id,
            probability=float(row.probability),
            confidence=float(row.confidence),
            model_version=row.model_version,
            model_type=model_type_used,  # type: ignore[arg-type]
            features_used={str(k): float(v) for k, v in features.items()},
            shap_explanations=(
                [
                    FeatureContribution(
                        feature=str(item.get("feature", "?")),
                        contribution=float(item.get("contribution", 0.0)),
                    )
                    for item in shap_list
                ]
                if include_shap
                else []
            ),
            cached=True,
            computed_at=_aware(row.computed_at),
        )


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
