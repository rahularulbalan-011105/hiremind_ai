from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import session_dep
from app.core.exceptions import NotFoundError
from app.db.repositories.candidates import CandidateRepository
from app.schemas.candidate_preferences import (
    CandidatePreferences,
    CandidatePreferencesResponse,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get(
    "/{candidate_id}/preferences",
    response_model=CandidatePreferencesResponse,
    summary="Read a candidate's preferences (notice, salary, locations, skill_years).",
)
def get_preferences(
    candidate_id: UUID,
    session: Session = Depends(session_dep),
) -> CandidatePreferencesResponse:
    repo = CandidateRepository(session)
    if not repo.exists(candidate_id):
        raise NotFoundError(f"Candidate {candidate_id} not found.")
    raw = repo.get_preferences(candidate_id)
    prefs = CandidatePreferences.model_validate(raw)
    return CandidatePreferencesResponse(candidate_id=candidate_id, preferences=prefs)


@router.put(
    "/{candidate_id}/preferences",
    response_model=CandidatePreferencesResponse,
    summary="Replace a candidate's preferences (full overwrite).",
)
def put_preferences(
    candidate_id: UUID,
    body: CandidatePreferences,
    session: Session = Depends(session_dep),
) -> CandidatePreferencesResponse:
    """
    **Example body**:
    ```json
    {
      "available_notice_days": 30,
      "expected_salary": {"min": 1500000, "max": 2500000, "currency": "INR"},
      "preferred_locations": ["bengaluru", "remote"],
      "skill_years": {"python": 5, "fastapi": 3, "aws": 2},
      "open_to_remote": true
    }
    ```
    """
    repo = CandidateRepository(session)
    if not repo.exists(candidate_id):
        raise NotFoundError(f"Candidate {candidate_id} not found.")
    # Normalize: lowercased skill keys + lowercased location entries
    payload = body.model_dump(mode="json")
    payload["preferred_locations"] = [str(s).strip().lower() for s in payload.get("preferred_locations") or [] if s]
    payload["skill_years"] = {str(k).strip().lower(): float(v) for k, v in (payload.get("skill_years") or {}).items()}
    repo.update_preferences(candidate_id, payload)
    return CandidatePreferencesResponse(
        candidate_id=candidate_id,
        preferences=CandidatePreferences.model_validate(payload),
    )
