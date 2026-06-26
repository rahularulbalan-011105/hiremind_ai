from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import (
    Candidate,
    FakeProfileScore,
    HiringPrediction,
    MatchScore,
    ResumeEmbedding,
)
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.jobs import JobRepository
from app.schemas.match import MatchWeights
from app.schemas.ranker import (
    CompareResponse,
    RankedHit,
    RankerComponents,
    RankerResponse,
    RankerWeights,
)
from app.services.hiring_predictor import HiringPredictorService
from app.services.match_engine import MatchEngineService

log = get_logger(__name__)

_EXPERIENCE_CAP_YEARS = 15.0  # 15+ years → 100; 0 years → 0


class RankerService:
    """
    Composes outputs from Match Engine, Fake Profile Detector, and Hiring
    Predictor into one final ranked list per job. Uses cached scores whenever
    available — falls through to live computation only when missing.
    """

    def __init__(
        self,
        match_service: MatchEngineService,
        hiring_predictor_service: HiringPredictorService,
    ):
        self.match_service = match_service
        self.hiring_predictor_service = hiring_predictor_service

    def rank(
        self,
        candidate_session: Session,
        company_session: Session,
        *,
        job_id: UUID,
        weights: RankerWeights,
        top_k: int,
        force_recompute: bool,
    ) -> RankerResponse:
        job = JobRepository(company_session).get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found.")

        # Candidates + resume embeddings live in candidate DB.
        candidate_rows = candidate_session.execute(
            select(
                Candidate.id,
                Candidate.full_name,
                Candidate.headline,
                Candidate.location,
            ).join(ResumeEmbedding, ResumeEmbedding.candidate_id == Candidate.id)
        ).all()
        if not candidate_rows:
            return RankerResponse(
                job_id=job_id,
                job_title=job.title,
                total_candidates_ranked=0,
                top_k=top_k,
                weights_used=weights,
                hits=[],
                computed_at=datetime.now(timezone.utc),
            )

        candidate_ids = [r.id for r in candidate_rows]
        match_map = self._load_match_scores(company_session, job_id, candidate_ids)
        trust_map = self._load_trust_scores(candidate_session, candidate_ids)
        hiring_map = self._load_hiring_predictions(
            company_session, job_id, candidate_ids, self.hiring_predictor_service.model_version
        )

        candidate_repo = CandidateRepository(candidate_session)
        hits: list[RankedHit] = []
        for row in candidate_rows:
            hit = self._build_hit(
                candidate_session=candidate_session,
                company_session=company_session,
                cand_id=row.id,
                full_name=row.full_name,
                headline=row.headline,
                location=row.location,
                weights=weights,
                match_map=match_map,
                trust_map=trust_map,
                hiring_map=hiring_map,
                candidate_repo=candidate_repo,
                job_id=job_id,
                force_recompute=force_recompute,
            )
            hits.append(hit)

        hits.sort(key=lambda h: h.final_score, reverse=True)
        for i, h in enumerate(hits[:top_k], start=1):
            h.rank = i

        log.info(
            "ranker_done",
            job_id=str(job_id),
            ranked=len(hits),
            top_k=top_k,
        )

        return RankerResponse(
            job_id=job_id,
            job_title=job.title,
            total_candidates_ranked=len(hits),
            top_k=top_k,
            weights_used=weights,
            hits=hits[:top_k],
            computed_at=datetime.now(timezone.utc),
        )

    def compare(
        self,
        candidate_session: Session,
        company_session: Session,
        *,
        job_id: UUID,
        candidate_ids: list[UUID],
        weights: RankerWeights,
    ) -> CompareResponse:
        job = JobRepository(company_session).get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found.")

        candidate_repo = CandidateRepository(candidate_session)
        match_map = self._load_match_scores(company_session, job_id, candidate_ids)
        trust_map = self._load_trust_scores(candidate_session, candidate_ids)
        hiring_map = self._load_hiring_predictions(
            company_session, job_id, candidate_ids, self.hiring_predictor_service.model_version
        )

        hits: list[RankedHit] = []
        for i, cid in enumerate(candidate_ids, start=1):
            candidate = candidate_repo.get(cid)
            if candidate is None:
                continue
            hit = self._build_hit(
                candidate_session=candidate_session,
                company_session=company_session,
                cand_id=cid,
                full_name=candidate.full_name or "",
                headline=candidate.headline,
                location=candidate.location,
                weights=weights,
                match_map=match_map,
                trust_map=trust_map,
                hiring_map=hiring_map,
                candidate_repo=candidate_repo,
                job_id=job_id,
                force_recompute=False,
            )
            hit.rank = i  # preserve input order
            hits.append(hit)

        return CompareResponse(
            job_id=job_id,
            job_title=job.title,
            weights_used=weights,
            hits=hits,
            computed_at=datetime.now(timezone.utc),
        )

    # ---------- bulk loaders ----------

    @staticmethod
    def _load_match_scores(session: Session, job_id: UUID, candidate_ids: list[UUID]) -> dict[UUID, MatchScore]:
        if not candidate_ids:
            return {}
        rows = session.execute(
            select(MatchScore).where(
                MatchScore.job_id == job_id,
                MatchScore.candidate_id.in_(candidate_ids),
            )
        ).scalars().all()
        return {r.candidate_id: r for r in rows}

    @staticmethod
    def _load_trust_scores(session: Session, candidate_ids: list[UUID]) -> dict[UUID, FakeProfileScore]:
        if not candidate_ids:
            return {}
        rows = session.execute(
            select(FakeProfileScore).where(FakeProfileScore.candidate_id.in_(candidate_ids))
        ).scalars().all()
        return {r.candidate_id: r for r in rows}

    @staticmethod
    def _load_hiring_predictions(
        session: Session,
        job_id: UUID,
        candidate_ids: list[UUID],
        model_version: str,
    ) -> dict[UUID, HiringPrediction]:
        if not candidate_ids:
            return {}
        rows = session.execute(
            select(HiringPrediction).where(
                HiringPrediction.job_id == job_id,
                HiringPrediction.candidate_id.in_(candidate_ids),
                HiringPrediction.model_version == model_version,
            )
        ).scalars().all()
        return {r.candidate_id: r for r in rows}

    # ---------- per-candidate composer ----------

    def _build_hit(
        self,
        *,
        candidate_session: Session,
        company_session: Session,
        cand_id: UUID,
        full_name: str,
        headline: str | None,
        location: str | None,
        weights: RankerWeights,
        match_map: dict[UUID, MatchScore],
        trust_map: dict[UUID, FakeProfileScore],
        hiring_map: dict[UUID, HiringPrediction],
        candidate_repo: CandidateRepository,
        job_id: UUID,
        force_recompute: bool,
    ) -> RankedHit:
        # --- Match ---
        match_row = match_map.get(cand_id)
        if match_row is None or force_recompute:
            mr = self.match_service.score(
                candidate_session,
                company_session,
                candidate_id=cand_id,
                job_id=job_id,
                weights=MatchWeights(),
                force_recompute=force_recompute,
            )
            match_score = mr.match_score
            match_summary = self._match_summary_from_response(mr)
        else:
            match_score = int(round(float(match_row.score)))
            match_summary = self._match_summary_from_row(match_row)

        # --- Hiring probability ---
        hp_row = hiring_map.get(cand_id)
        if hp_row is None or force_recompute:
            hr = self.hiring_predictor_service.predict(
                candidate_session,
                company_session,
                candidate_id=cand_id,
                job_id=job_id,
                force_recompute=force_recompute,
                include_shap=False,
            )
            probability = hr.probability
            model_type = hr.model_type
        else:
            probability = float(hp_row.probability)
            model_type = None
            if isinstance(hp_row.shap, dict):
                mt = hp_row.shap.get("model_type")
                if mt in ("xgboost", "rules"):
                    model_type = mt
        hiring_int = int(round(probability * 100))

        # --- Trust ---
        fp_row = trust_map.get(cand_id)
        if fp_row is None:
            trust_score = 100
            risk_level = "unknown"
        else:
            trust_score = int(round(float(fp_row.trust_score)))
            risk_level = fp_row.risk_level

        # --- Experience seniority ---
        candidate_years = candidate_repo.years_of_experience(cand_id)
        experience_score = int(
            round(min(candidate_years / _EXPERIENCE_CAP_YEARS, 1.0) * 100.0)
        )

        # --- Composite ---
        total_w = weights.match + weights.hiring_probability + weights.trust + weights.experience
        if total_w <= 0:
            final = 0
        else:
            final = int(round(
                (match_score * weights.match
                 + hiring_int * weights.hiring_probability
                 + trust_score * weights.trust
                 + experience_score * weights.experience) / total_w
            ))

        return RankedHit(
            rank=0,  # set after sorting
            candidate_id=cand_id,
            full_name=full_name,
            headline=headline,
            location=location,
            final_score=max(0, min(100, final)),
            components=RankerComponents(
                match_score=match_score,
                hiring_probability=hiring_int,
                trust_score=trust_score,
                experience_score=experience_score,
            ),
            candidate_years=candidate_years,
            fake_profile_risk=risk_level,  # type: ignore[arg-type]
            hiring_probability_raw=probability,
            hiring_model_type=model_type,
            match_summary=match_summary,
        )

    # ---------- small helpers ----------

    @staticmethod
    def _match_summary_from_row(row: MatchScore) -> str:
        """
        In the new schema `row.reasoning` holds just the bullets list and
        `row.subscores` holds the numeric breakdown. The richer `matched_skills`
        / `missing_skills` arrays from the legacy blob are no longer persisted,
        so we summarize from subscores only.
        """
        sub = dict(row.subscores or {})
        parts: list[str] = []
        if (s := sub.get("semantic")) is not None:
            parts.append(f"sem {int(round(float(s)))}")
        if (s := sub.get("skill_overlap")) is not None:
            parts.append(f"sk {int(round(float(s)))}")
        if (s := sub.get("experience")) is not None:
            parts.append(f"exp {int(round(float(s)))}")
        if not parts:
            parts.append("semantic only")
        return " · ".join(parts)

    @staticmethod
    def _match_summary_from_response(mr) -> str:
        parts: list[str] = []
        # mr is MatchResponse — has subscores but not matched/missing arrays at top level
        sem = int(round(mr.subscores.semantic))
        sk = int(round(mr.subscores.skill_overlap))
        ex = int(round(mr.subscores.experience))
        parts.append(f"sub {sem}/{sk}/{ex}")
        return " · ".join(parts)
