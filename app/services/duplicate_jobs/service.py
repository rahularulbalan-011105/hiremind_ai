from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import Job, JobEmbedding
from app.db.repositories.duplicate_jobs import DuplicateJobRepository
from app.db.repositories.jobs import JobRepository
from app.schemas.duplicate_job import DuplicateCheckResponse, DuplicateMatch
from app.services.duplicate_jobs.detector import (
    classify,
    normalize_company,  # noqa: F401 — kept available for downstream code paths
    skill_overlap,
    title_similarity,
)

log = get_logger(__name__)


class DuplicateJobService:
    METHOD = "combined"

    def check(
        self,
        session: Session,
        *,
        job_id: UUID,
        force_recompute: bool,
        max_candidates: int,
    ) -> DuplicateCheckResponse:
        job_repo = JobRepository(session)
        target = job_repo.get(job_id)
        if target is None:
            raise NotFoundError(f"Job {job_id} not found.")

        # ---- Cache: return previously persisted clusters unless force_recompute ----
        if not force_recompute:
            cached = DuplicateJobRepository(session).get_for_job(job_id, self.METHOD)
            if cached:
                return self._cached_to_response(session, target, cached)

        target_vec_raw = session.execute(
            select(JobEmbedding.embedding).where(JobEmbedding.job_id == job_id)
        ).scalar_one_or_none()
        if target_vec_raw is None:
            raise NotFoundError(
                f"Job {job_id} has no JD embedding. Re-create the job to regenerate it."
            )
        target_vec = np.asarray(target_vec_raw, dtype=np.float64)

        target_skills = [s["skill"] for s in JobRepository.required_skills(target)]
        # Same-company check now keys on company_id (UUID) since the live
        # `jobs` table doesn't carry a company name column.
        target_company = str(target.company_id) if target.company_id is not None else None

        # ---- HNSW pre-filter (top-N by cosine distance) ----
        distance = JobEmbedding.embedding.cosine_distance(target_vec_raw)
        rows = session.execute(
            select(
                Job.id,
                Job.title,
                Job.company_id,
                JobEmbedding.embedding,
                (1.0 - distance).label("similarity"),
            )
            .join(Job, Job.id == JobEmbedding.job_id)
            .where(Job.id != job_id)
            .order_by(distance)
            .limit(max_candidates)
        ).all()

        duplicates: list[DuplicateMatch] = []
        for cand_id, cand_title, cand_company, _cand_vec, sim in rows:
            # `cand_company` here is a UUID (company_id), not a name. Same-company
            # comparison degrades to "share the same company_id".
            embedding_sim = float(sim)
            t_sim = title_similarity(target.title, cand_title)
            same_company = (
                target_company is not None
                and cand_company is not None
                and str(cand_company) == target_company
            )

            cand_job = job_repo.get(cand_id)
            cand_skills = (
                [s["skill"] for s in JobRepository.required_skills(cand_job)]
                if cand_job is not None
                else []
            )
            _overlap_ratio, shared = skill_overlap(target_skills, cand_skills)

            verdict = classify(
                title_sim=t_sim,
                embedding_sim=embedding_sim,
                same_company=same_company,
            )
            if verdict is None:
                continue

            duplicates.append(
                DuplicateMatch(
                    duplicate_job_id=cand_id,
                    title=cand_title,
                    company=cand_company,
                    title_similarity=round(t_sim, 3),
                    embedding_similarity=round(embedding_sim, 3),
                    shared_required_skills=shared,
                    same_company=same_company,
                    verdict=verdict,
                )
            )

        # Persist the resolved cluster (overwrite any prior rows for this job/method)
        DuplicateJobRepository(session).replace_for_job(
            job_id=job_id,
            method=self.METHOD,
            pairs=[
                (d.duplicate_job_id, max(d.title_similarity, d.embedding_similarity))
                for d in duplicates
            ],
        )

        log.info(
            "duplicate_check_done",
            job_id=str(job_id),
            compared=len(rows),
            duplicates=len(duplicates),
        )

        return DuplicateCheckResponse(
            job_id=job_id,
            job_title=target.title,
            total_compared=len(rows),
            duplicates=duplicates,
            cached=False,
            computed_at=datetime.now(timezone.utc),
        )

    # ---------- internals ----------

    @staticmethod
    def _cached_to_response(
        session: Session, target: Job, rows
    ) -> DuplicateCheckResponse:
        # Hydrate cached rows with current titles/companies for display
        job_repo = JobRepository(session)
        target_skills = [s["skill"] for s in JobRepository.required_skills(target)]
        # Same-company check now keys on company_id (UUID) since the live
        # `jobs` table doesn't carry a company name column.
        target_company = str(target.company_id) if target.company_id is not None else None

        duplicates: list[DuplicateMatch] = []
        for r in rows:
            other = job_repo.get(r.duplicate_of_job_id)
            if other is None:
                continue
            other_skills = [s["skill"] for s in JobRepository.required_skills(other)]
            _, shared = skill_overlap(target_skills, other_skills)
            t_sim = title_similarity(target.title, other.title)
            same_company = (
                target_company is not None
                and other.company_id is not None
                and str(other.company_id) == target_company
            )
            verdict = classify(
                title_sim=t_sim,
                embedding_sim=float(r.similarity),
                same_company=same_company,
            ) or "similar"
            duplicates.append(
                DuplicateMatch(
                    duplicate_job_id=other.id,
                    title=other.title,
                    company=other.company,
                    title_similarity=round(t_sim, 3),
                    embedding_similarity=round(float(r.similarity), 3),
                    shared_required_skills=shared,
                    same_company=same_company,
                    verdict=verdict,
                )
            )

        latest = max((r.computed_at for r in rows), default=datetime.now(timezone.utc))
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return DuplicateCheckResponse(
            job_id=target.id,
            job_title=target.title,
            total_compared=len(rows),
            duplicates=duplicates,
            cached=True,
            computed_at=latest,
        )
