from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import session_dep
from app.core.config import Settings, get_settings
from app.llm import LLMClient, get_llm_client
from app.schemas.ranker import (
    CompareRequest,
    CompareResponse,
    RankerRequest,
    RankerResponse,
    RankerWeights,
)
from app.services.hiring_predictor import HiringPredictorService
from app.services.match_engine import MatchEngineService
from app.services.ranker import RankerService

router = APIRouter(prefix="/rank", tags=["ranker"])


def _service_dep(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> RankerService:
    svc: RankerService | None = getattr(request.app.state, "ranker_service", None)
    if svc is not None:
        return svc

    llm: LLMClient | None = getattr(request.app.state, "llm_client", None)
    if llm is None:
        llm = get_llm_client(settings)
        request.app.state.llm_client = llm

    match_service = MatchEngineService(llm)

    hp: HiringPredictorService | None = getattr(
        request.app.state, "hiring_predictor_service", None
    )
    if hp is None:
        hp = HiringPredictorService(settings, llm)
        request.app.state.hiring_predictor_service = hp

    svc = RankerService(match_service, hp)
    request.app.state.ranker_service = svc
    return svc


@router.post(
    "/candidates",
    response_model=RankerResponse,
    summary="Final ranked candidate list for a job (composes Match + Hiring + Trust + Experience).",
)
def rank_candidates(
    body: RankerRequest,
    session: Session = Depends(session_dep),
    service: RankerService = Depends(_service_dep),
) -> RankerResponse:
    """
    **Example request**:
    ```json
    {
      "job_id": "22222222-2222-2222-2222-222222222222",
      "top_k": 20,
      "weights": {"match": 0.45, "hiring_probability": 0.30, "trust": 0.15, "experience": 0.10},
      "force_recompute": false
    }
    ```

    For each candidate-with-embedding, looks up (or computes) match score,
    hiring probability, trust score, and experience seniority, combines them
    with the supplied weights, and returns the sorted top-K with full
    per-candidate component breakdown.
    """
    weights = body.weights or RankerWeights()
    return service.rank(
        session,
        job_id=body.job_id,
        weights=weights,
        top_k=body.top_k,
        force_recompute=body.force_recompute,
    )


@router.post(
    "/compare",
    response_model=CompareResponse,
    summary="Side-by-side comparison of specific candidates against a job.",
)
def rank_compare(
    body: CompareRequest,
    session: Session = Depends(session_dep),
    service: RankerService = Depends(_service_dep),
) -> CompareResponse:
    """
    **Example request**:
    ```json
    {
      "job_id": "22222222-2222-2222-2222-222222222222",
      "candidate_ids": [
        "11111111-1111-1111-1111-111111111111",
        "33333333-3333-3333-3333-333333333333"
      ],
      "weights": {"match": 0.5, "hiring_probability": 0.25, "trust": 0.15, "experience": 0.10}
    }
    ```

    Returns each candidate's full breakdown in the input order — no sorting.
    Designed for "compare these 3 candidates I shortlisted" recruiter workflows.
    """
    weights = body.weights or RankerWeights()
    return service.compare(
        session,
        job_id=body.job_id,
        candidate_ids=body.candidate_ids,
        weights=weights,
    )
