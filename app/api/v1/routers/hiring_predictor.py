from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import session_dep
from app.core.config import Settings, get_settings
from app.llm import LLMClient, get_llm_client
from app.schemas.hiring_predictor import (
    HiringProbabilityRequest,
    HiringProbabilityResponse,
)
from app.services.hiring_predictor import HiringPredictorService

router = APIRouter(prefix="/hiring-probability", tags=["hiring-probability"])


def _service_dep(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> HiringPredictorService:
    svc: HiringPredictorService | None = getattr(
        request.app.state, "hiring_predictor_service", None
    )
    if svc is None:
        llm: LLMClient | None = getattr(request.app.state, "llm_client", None)
        if llm is None:
            llm = get_llm_client(settings)
            request.app.state.llm_client = llm
        svc = HiringPredictorService(settings, llm)
        request.app.state.hiring_predictor_service = svc
    return svc


@router.post(
    "/predict",
    response_model=HiringProbabilityResponse,
    summary="Predict probability that this candidate gets hired for this job.",
)
def predict_hiring_probability(
    body: HiringProbabilityRequest,
    session: Session = Depends(session_dep),
    service: HiringPredictorService = Depends(_service_dep),
) -> HiringProbabilityResponse:
    """
    **Example request**:
    ```json
    {
      "candidate_id": "11111111-1111-1111-1111-111111111111",
      "job_id": "22222222-2222-2222-2222-222222222222",
      "force_recompute": false,
      "include_shap": true
    }
    ```

    Picks XGBoost if a trained model exists for `MODEL_VERSION`, else the
    deterministic rules-based predictor (with rule-derived contributions). The
    response shape is identical either way; check `model_type` to know which.
    """
    return service.predict(
        session,
        candidate_id=body.candidate_id,
        job_id=body.job_id,
        force_recompute=body.force_recompute,
        include_shap=body.include_shap,
    )
