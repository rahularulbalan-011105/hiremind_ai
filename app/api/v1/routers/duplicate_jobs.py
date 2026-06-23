from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import session_dep
from app.schemas.duplicate_job import DuplicateCheckRequest, DuplicateCheckResponse
from app.services.duplicate_jobs import DuplicateJobService

router = APIRouter(prefix="/jobs", tags=["duplicate-jobs"])


@router.post(
    "/duplicate-check",
    response_model=DuplicateCheckResponse,
    summary="Find jobs that look like duplicates of the given job.",
)
def duplicate_check(
    body: DuplicateCheckRequest,
    session: Session = Depends(session_dep),
) -> DuplicateCheckResponse:
    """
    **Example request**:
    ```json
    {
      "job_id": "22222222-2222-2222-2222-222222222222",
      "force_recompute": false,
      "max_candidates": 50
    }
    ```

    Three signals are combined: RapidFuzz title similarity (`token_set_ratio`),
    JD embedding cosine similarity, and same-company. Verdicts:

      - **hard** — same company + (title ≥ 0.90 OR embedding ≥ 0.97)
      - **likely** — title ≥ 0.85 AND embedding ≥ 0.92
      - **similar** — embedding ≥ 0.90 OR title ≥ 0.85

    Persists clusters to `duplicate_job_clusters` (method='combined').
    """
    return DuplicateJobService().check(
        session,
        job_id=body.job_id,
        force_recompute=body.force_recompute,
        max_candidates=body.max_candidates,
    )
