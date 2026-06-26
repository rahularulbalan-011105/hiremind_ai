from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import candidate_session_dep, company_session_dep
from app.core.config import Settings, get_settings
from app.llm import LLMClient, get_llm_client
from app.schemas.match import (
    MatchByJobRequest,
    MatchByJobResponse,
    MatchRequest,
    MatchResponse,
    MatchWeights,
)
from app.services.match_engine import MatchEngineService

router = APIRouter(prefix="/match", tags=["match"])


def _llm_dep(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> LLMClient:
    # Lazy-cache an LLM client on app.state so we don't re-instantiate per request.
    client: LLMClient | None = getattr(request.app.state, "llm_client", None)
    if client is None:
        client = get_llm_client(settings)
        request.app.state.llm_client = client
    return client


@router.post(
    "/score",
    response_model=MatchResponse,
    summary="Score a candidate against a job (semantic + skill + experience).",
)
def score_match(
    body: MatchRequest,
    candidate_session: Session = Depends(candidate_session_dep),
    company_session: Session = Depends(company_session_dep),
    llm: LLMClient = Depends(_llm_dep),
) -> MatchResponse:
    """
    **Example request**:
    ```json
    {
      "candidate_id": "11111111-1111-1111-1111-111111111111",
      "job_id": "22222222-2222-2222-2222-222222222222",
      "force_recompute": false,
      "weights": {"semantic": 0.4, "skill_overlap": 0.4, "experience": 0.2}
    }
    ```

    Returns the composite 0–100 score, the three sub-scores, and a list of
    LLM-grounded reasoning bullets (or rule-based bullets as a fallback).
    """
    weights = body.weights or MatchWeights()
    service = MatchEngineService(llm)
    return service.score(
        candidate_session,
        company_session,
        candidate_id=body.candidate_id,
        job_id=body.job_id,
        weights=weights,
        force_recompute=body.force_recompute,
    )


@router.post(
    "/by-job",
    response_model=MatchByJobResponse,
    summary="Rank ALL candidates against one job (recruiter view).",
)
def score_by_job(
    body: MatchByJobRequest,
    candidate_session: Session = Depends(candidate_session_dep),
    company_session: Session = Depends(company_session_dep),
    llm: LLMClient = Depends(_llm_dep),
) -> MatchByJobResponse:
    """
    Recruiter flow: pick a job → see every candidate ranked by composite match score.

    **Example request**:
    ```json
    {
      "job_id": "22222222-2222-2222-2222-222222222222",
      "top_k": 20,
      "weights": {"semantic": 0.4, "skill_overlap": 0.4, "experience": 0.2}
    }
    ```

    Skips the LLM per row for performance — use `POST /api/v1/match/score`
    with a specific `candidate_id` to get full LLM-generated reasoning bullets.
    """
    weights = body.weights or MatchWeights()
    service = MatchEngineService(llm)
    return service.score_by_job(
        candidate_session,
        company_session,
        job_id=body.job_id,
        weights=weights,
        top_k=body.top_k,
    )
