from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import company_session_dep
from app.schemas.ghost_job import GhostScoreRequest, GhostScoreResponse
from app.services.ghost_jobs import GhostJobService

router = APIRouter(prefix="/jobs", tags=["ghost-jobs"])


@router.post(
    "/ghost-score",
    response_model=GhostScoreResponse,
    summary="Score a job posting on how likely it is a ghost.",
)
def ghost_score(
    body: GhostScoreRequest,
    session: Session = Depends(company_session_dep),
) -> GhostScoreResponse:
    """
    **Example request**:
    ```json
    {
      "job_id": "22222222-2222-2222-2222-222222222222",
      "force_recompute": false
    }
    ```

    Returns a 0–100 ghost score (higher = more ghost-like) derived from posting
    age, days since last recruiter activity, repost count, and candidate
    interaction volume. Classification:

      - **active** — score < 30
      - **stale** — 30 ≤ score < 60
      - **likely_ghost** — score ≥ 60

    Persists to `ghost_job_scores`. Cached results are returned unless
    `force_recompute: true` — scores age over time, so re-run periodically.
    """
    return GhostJobService().score(
        session,
        job_id=body.job_id,
        force_recompute=body.force_recompute,
    )
