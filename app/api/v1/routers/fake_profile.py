from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import session_dep
from app.core.config import Settings, get_settings
from app.schemas.fake_profile import FakeProfileRequest, FakeProfileResponse
from app.services.fake_profile import FakeProfileService
from app.services.fake_profile.github import GitHubChecker

router = APIRouter(prefix="/fake-profile", tags=["fake-profile"])


def _fake_profile_service_dep(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> FakeProfileService:
    svc: FakeProfileService | None = getattr(request.app.state, "fake_profile_service", None)
    if svc is None:
        gh = GitHubChecker(
            token=settings.github_token, timeout=settings.github_timeout_seconds
        )
        svc = FakeProfileService(gh)
        request.app.state.fake_profile_service = svc
    return svc


@router.post(
    "/score",
    response_model=FakeProfileResponse,
    summary="Trust score, anomaly breakdown, and GitHub cross-check for one candidate.",
)
def score_fake_profile(
    body: FakeProfileRequest,
    session: Session = Depends(session_dep),
    service: FakeProfileService = Depends(_fake_profile_service_dep),
) -> FakeProfileResponse:
    """
    **Example request**:
    ```json
    {
      "candidate_id": "11111111-1111-1111-1111-111111111111",
      "force_recompute": false,
      "github_username": "alice-lee",
      "skip_github": false
    }
    ```

    Returns a 0–100 trust score with a full breakdown of all 5 signals (fired or
    not), human-readable reasoning bullets, and the GitHub cross-check details.
    """
    return service.score(
        session,
        candidate_id=body.candidate_id,
        force_recompute=body.force_recompute,
        github_username=body.github_username,
        skip_github=body.skip_github,
    )
