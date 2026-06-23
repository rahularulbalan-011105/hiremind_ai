from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ModelType = Literal["xgboost", "rules"]


class HiringProbabilityRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID
    force_recompute: bool = False
    include_shap: bool = True


class FeatureContribution(BaseModel):
    feature: str
    contribution: float = Field(
        description="Signed contribution to the logit (XGBoost) or to the probability shift (rules)."
    )


class HiringProbabilityResponse(BaseModel):
    candidate_id: UUID
    job_id: UUID
    probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1, description="abs(probability - 0.5) * 2 — higher = model is sure either way.")
    model_version: str
    model_type: ModelType
    features_used: dict[str, float]
    shap_explanations: list[FeatureContribution]
    cached: bool = False
    computed_at: datetime
