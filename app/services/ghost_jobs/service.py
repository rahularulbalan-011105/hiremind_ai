from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import MatchScore
from app.db.repositories.ghost_jobs import GhostJobRepository
from app.db.repositories.jobs import JobRepository
from app.schemas.ghost_job import (
    GhostScoreResponse,
    GhostSignalBreakdown,
    GhostSignals,
)
from app.services.ghost_jobs.detector import (
    Finding,
    detect_last_activity,
    detect_posting_age,
    detect_repost,
    detect_stale_interaction,
    detect_zero_interaction,
    ghost_score_from_findings,
    risk_classification_from_score,
)

log = get_logger(__name__)


class GhostJobService:
    def score(
        self,
        session: Session,
        *,
        job_id: UUID,
        force_recompute: bool,
    ) -> GhostScoreResponse:
        job_repo = JobRepository(session)
        job = job_repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found.")

        repo = GhostJobRepository(session)
        if not force_recompute:
            cached = repo.get(job_id)
            if cached is not None:
                return self._cached_to_response(job, cached)

        now = datetime.now(timezone.utc)
        posted_at = _aware(job.posted_at)
        last_activity_at = _aware(job.last_activity_at)

        posting_age_days = max(0, (now - posted_at).days)
        days_since_last_activity = max(0, (now - last_activity_at).days)
        repost_count = int(job.repost_count or 0)

        # Candidate-interaction stats from match_scores
        match_count_row = session.execute(
            select(func.count(MatchScore.id), func.max(MatchScore.computed_at)).where(
                MatchScore.job_id == job_id
            )
        ).one()
        match_scores_count = int(match_count_row[0] or 0)
        last_match_at = match_count_row[1]
        days_since_last_interaction: int | None = None
        if last_match_at is not None:
            days_since_last_interaction = max(0, (now - _aware(last_match_at)).days)

        findings: list[Finding] = [
            detect_posting_age(posting_age_days),
            detect_last_activity(days_since_last_activity),
            detect_repost(repost_count),
            detect_zero_interaction(posting_age_days, match_scores_count),
            detect_stale_interaction(days_since_last_interaction, match_scores_count),
        ]

        ghost_score = ghost_score_from_findings(findings)
        risk = risk_classification_from_score(ghost_score)

        signals = GhostSignals(
            posting_age_days=posting_age_days,
            days_since_last_activity=days_since_last_activity,
            repost_count=repost_count,
            match_scores_count=match_scores_count,
            days_since_last_interaction=days_since_last_interaction,
            job_status=job.status,
        )
        breakdown = [
            GhostSignalBreakdown(
                signal=f.signal,
                fired=f.fired,
                penalty=f.penalty,
                message=f.message,
                details=f.details,
            )
            for f in findings
        ]

        signals_blob = {
            "signals": signals.model_dump(),
            "breakdown": [b.model_dump() for b in breakdown],
        }
        row = repo.upsert(
            job_id=job_id,
            ghost_score=float(ghost_score),
            risk_classification=risk,
            signals_blob=signals_blob,
        )

        log.info(
            "ghost_score_done",
            job_id=str(job_id),
            score=ghost_score,
            classification=risk,
        )

        return GhostScoreResponse(
            job_id=job_id,
            job_title=job.title,
            ghost_score=ghost_score,
            risk_classification=risk,  # type: ignore[arg-type]
            signals=signals,
            breakdown=breakdown,
            cached=False,
            computed_at=_aware(row.computed_at),
        )

    @staticmethod
    def _cached_to_response(job, row) -> GhostScoreResponse:
        blob = row.signals if isinstance(row.signals, dict) else {}
        sig_raw = blob.get("signals") or {}
        signals = GhostSignals.model_validate(sig_raw) if sig_raw else GhostSignals(
            posting_age_days=0,
            days_since_last_activity=0,
            repost_count=0,
            match_scores_count=0,
            days_since_last_interaction=None,
            job_status=job.status,
        )
        bd_raw = blob.get("breakdown") or []
        breakdown = [GhostSignalBreakdown.model_validate(b) for b in bd_raw]
        return GhostScoreResponse(
            job_id=row.job_id,
            job_title=job.title,
            ghost_score=int(round(float(row.ghost_score))),
            risk_classification=row.risk_classification,  # type: ignore[arg-type]
            signals=signals,
            breakdown=breakdown,
            cached=True,
            computed_at=_aware(row.computed_at),
        )


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
