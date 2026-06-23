from __future__ import annotations

import json
from datetime import timezone
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import Candidate, JobEmbedding, ResumeEmbedding
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.fake_profile import FakeProfileRepository
from app.db.repositories.jobs import JobRepository
from app.db.repositories.match_scores import MatchScoreRepository
from app.llm import LLMClient, LLMError
from app.llm.prompts import MATCH_REASONING_SYSTEM, MATCH_REASONING_USER_TEMPLATE
from app.schemas.match import (
    CandidateMatchHit,
    DuplicateRef,
    MatchByJobResponse,
    MatchResponse,
    MatchSubscores,
    MatchWeights,
)
from app.services.match_engine.scorer import (
    SubScores,
    composite_score,
    compute_subscores,
    rule_based_bullets,
)

log = get_logger(__name__)


class MatchEngineService:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def score(
        self,
        session: Session,
        *,
        candidate_id: UUID,
        job_id: UUID,
        weights: MatchWeights,
        force_recompute: bool,
    ) -> MatchResponse:
        match_repo = MatchScoreRepository(session)

        if not force_recompute:
            cached = match_repo.get(candidate_id, job_id)
            if cached is not None:
                return self._cached_to_response(cached, weights)

        candidate_repo = CandidateRepository(session)
        job_repo = JobRepository(session)

        candidate = candidate_repo.get(candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {candidate_id} not found.")
        job = job_repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found.")

        # 1. Semantic similarity via pgvector
        cosine = self._cosine_similarity(session, candidate_id, job_id)

        # 2-6. Skill overlap, experience, location, notice, salary
        candidate_skills = candidate_repo.get_skills(candidate_id)
        candidate_years = candidate_repo.years_of_experience(candidate_id)
        prefs = candidate_repo.get_preferences(candidate_id)
        required_skills = JobRepository.required_skills(job)
        required_years = JobRepository.required_years(job)

        sub = compute_subscores(
            cosine_similarity=cosine,
            required_skills=required_skills,
            candidate_skills=candidate_skills,
            candidate_skill_years={
                str(k).lower(): float(v) for k, v in (prefs.get("skill_years") or {}).items()
            },
            candidate_years=candidate_years,
            required_years=required_years,
            job_location=job.location,
            candidate_location=candidate.location,
            preferred_locations=list(prefs.get("preferred_locations") or []),
            open_to_remote=bool(prefs.get("open_to_remote", True)),
            candidate_notice_days=prefs.get("available_notice_days"),
            job_notice_max=JobRepository.notice_period_max(job),
            candidate_expected_salary=prefs.get("expected_salary"),
            job_salary=JobRepository.salary(job),
        )

        match = composite_score(
            sub,
            w_sem=weights.semantic,
            w_skill=weights.skill_overlap,
            w_exp=weights.experience,
            w_loc=weights.location,
            w_notice=weights.notice_period,
            w_sal=weights.salary,
        )

        # 4. Reasoning (LLM with rule-based fallback)
        bullets = self._reasoning(job_title=job.title, job_summary=job.description, sub=sub)

        # 5. Persist
        blob = {
            "bullets": bullets,
            "subscores": {
                "semantic": sub.semantic,
                "skill_overlap": sub.skill_overlap,
                "experience": sub.experience,
                "location": sub.location,
                "notice_period": sub.notice_period,
                "salary": sub.salary,
            },
            "weights": weights.model_dump(),
            "matched_skills": sub.matched_skills,
            "missing_skills": sub.missing_skills,
            "candidate_years": sub.candidate_years,
            "required_years": sub.required_years,
        }
        row = match_repo.upsert(candidate_id, job_id, float(match), blob)

        return MatchResponse(
            candidate_id=candidate_id,
            job_id=job_id,
            match_score=match,
            subscores=MatchSubscores(
                semantic=sub.semantic,
                skill_overlap=sub.skill_overlap,
                experience=sub.experience,
                location=sub.location,
                notice_period=sub.notice_period,
                salary=sub.salary,
            ),
            reasoning=bullets,
            weights_used=weights,
            cached=False,
            computed_at=row.computed_at if row.computed_at.tzinfo else row.computed_at.replace(tzinfo=timezone.utc),
        )

    def score_by_job(
        self,
        session: Session,
        *,
        job_id: UUID,
        weights: MatchWeights,
        top_k: int,
    ) -> MatchByJobResponse:
        """
        Score every candidate (that has an embedding) against this job.
        Deterministic math only — NO LLM call per candidate. Use the single-pair
        `score()` endpoint to drill into a specific match with full LLM reasoning.
        """
        job_repo = JobRepository(session)
        job = job_repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found.")

        # JD embedding (required)
        jd_vec_raw = session.execute(
            select(JobEmbedding.embedding).where(JobEmbedding.job_id == job_id)
        ).scalar_one_or_none()
        if jd_vec_raw is None:
            raise NotFoundError(
                f"Job {job_id} has no JD embedding. Re-create the job to regenerate it."
            )
        jd_vec = np.asarray(jd_vec_raw, dtype=np.float64)
        jd_norm = float(np.linalg.norm(jd_vec))

        required_skills = JobRepository.required_skills(job)
        required_years = JobRepository.required_years(job)
        job_salary = JobRepository.salary(job)
        job_notice_max = JobRepository.notice_period_max(job)
        job_location = job.location

        # All candidates that have an embedding, joined with their resume vector
        rows = session.execute(
            select(
                Candidate.id,
                Candidate.full_name,
                Candidate.headline,
                Candidate.location,
                ResumeEmbedding.embedding,
            ).join(ResumeEmbedding, ResumeEmbedding.candidate_id == Candidate.id)
        ).all()

        candidate_repo = CandidateRepository(session)
        candidate_ids = [r[0] for r in rows]
        prefs_map = candidate_repo.get_preferences_many(candidate_ids)
        hits: list[CandidateMatchHit] = []
        embeddings: dict[UUID, np.ndarray] = {}

        for cand_id, full_name, headline, location, resume_vec_raw in rows:
            resume_vec = np.asarray(resume_vec_raw, dtype=np.float64)
            denom = float(np.linalg.norm(resume_vec)) * jd_norm
            cosine = float(np.dot(resume_vec, jd_vec) / denom) if denom > 0 else 0.0

            candidate_skills = candidate_repo.get_skills(cand_id)
            candidate_years = candidate_repo.years_of_experience(cand_id)
            prefs = prefs_map.get(cand_id) or {}

            sub = compute_subscores(
                cosine_similarity=cosine,
                required_skills=required_skills,
                candidate_skills=candidate_skills,
                candidate_skill_years={
                    str(k).lower(): float(v) for k, v in (prefs.get("skill_years") or {}).items()
                },
                candidate_years=candidate_years,
                required_years=required_years,
                job_location=job_location,
                candidate_location=location,
                preferred_locations=list(prefs.get("preferred_locations") or []),
                open_to_remote=bool(prefs.get("open_to_remote", True)),
                candidate_notice_days=prefs.get("available_notice_days"),
                job_notice_max=job_notice_max,
                candidate_expected_salary=prefs.get("expected_salary"),
                job_salary=job_salary,
            )
            score = composite_score(
                sub,
                w_sem=weights.semantic,
                w_skill=weights.skill_overlap,
                w_exp=weights.experience,
                w_loc=weights.location,
                w_notice=weights.notice_period,
                w_sal=weights.salary,
            )

            summary = self._one_line_summary(sub)
            embeddings[cand_id] = resume_vec
            hits.append(
                CandidateMatchHit(
                    candidate_id=cand_id,
                    full_name=full_name,
                    headline=headline,
                    location=location,
                    match_score=score,
                    subscores=MatchSubscores(
                        semantic=sub.semantic,
                        skill_overlap=sub.skill_overlap,
                        experience=sub.experience,
                        location=sub.location,
                        notice_period=sub.notice_period,
                        salary=sub.salary,
                    ),
                    matched_skills=sub.matched_skills,
                    missing_skills=sub.missing_skills,
                    candidate_years=sub.candidate_years,
                    summary=summary,
                )
            )

        hits.sort(key=lambda h: h.match_score, reverse=True)
        top_hits = hits[:top_k]

        # Enrich top-K with fake_profile_risk + pairwise duplicates (within this set).
        self._enrich_with_trust_and_duplicates(
            session=session,
            hits=top_hits,
            embeddings={h.candidate_id: embeddings[h.candidate_id] for h in top_hits},
            candidate_repo=candidate_repo,
        )

        return MatchByJobResponse(
            job_id=job_id,
            job_title=job.title,
            total_candidates_scored=len(hits),
            top_k=top_k,
            weights_used=weights,
            hits=top_hits,
        )

    def _enrich_with_trust_and_duplicates(
        self,
        *,
        session: Session,
        hits: list[CandidateMatchHit],
        embeddings: dict[UUID, np.ndarray],
        candidate_repo: CandidateRepository,
    ) -> None:
        if not hits:
            return

        ids = [h.candidate_id for h in hits]
        fake_repo = FakeProfileRepository(session)
        fp_map = fake_repo.get_many(ids)
        contact = candidate_repo.get_contact_info_many(ids)
        names_by_id = {h.candidate_id: h.full_name for h in hits}

        # Pre-normalize embeddings for cosine
        normed: dict[UUID, np.ndarray] = {}
        for cid, vec in embeddings.items():
            n = float(np.linalg.norm(vec))
            normed[cid] = vec / n if n > 0 else vec

        dup_index: dict[UUID, list[DuplicateRef]] = {cid: [] for cid in ids}
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                a_email, a_phone = (contact.get(a) or (None, None, None))[1:]
                b_email, b_phone = (contact.get(b) or (None, None, None))[1:]

                kind: str | None = None
                if a_email and a_email == b_email:
                    kind = "hard"
                    sim = 1.0
                elif a_phone and a_phone == b_phone:
                    kind = "hard"
                    sim = 1.0
                else:
                    cos = float(np.dot(normed[a], normed[b]))
                    if cos >= 0.95:
                        kind = "likely"
                        sim = cos
                    elif cos >= 0.90:
                        kind = "similar"
                        sim = cos
                    else:
                        continue

                dup_index[a].append(
                    DuplicateRef(
                        candidate_id=b,
                        full_name=names_by_id[b],
                        similarity=round(sim, 3),
                        kind=kind,  # type: ignore[arg-type]
                    )
                )
                dup_index[b].append(
                    DuplicateRef(
                        candidate_id=a,
                        full_name=names_by_id[a],
                        similarity=round(sim, 3),
                        kind=kind,  # type: ignore[arg-type]
                    )
                )

        for h in hits:
            fp = fp_map.get(h.candidate_id)
            if fp is not None:
                h.fake_profile_risk = fp.risk_level  # type: ignore[assignment]
                h.trust_score = int(round(float(fp.trust_score)))
            h.possible_duplicates = sorted(
                dup_index[h.candidate_id], key=lambda d: d.similarity, reverse=True
            )

    @staticmethod
    def _one_line_summary(sub: SubScores) -> str:
        parts: list[str] = []
        if sub.matched_skills:
            parts.append(f"{len(sub.matched_skills)} matched skills")
        if sub.missing_skills:
            parts.append(f"{len(sub.missing_skills)} missing")
        if sub.required_years is not None:
            gap = sub.candidate_years - sub.required_years
            if gap >= 0:
                parts.append(f"{gap:+.1f}y exp")
            else:
                parts.append(f"{gap:.1f}y exp")
        if not parts:
            parts.append("semantic only")
        return " · ".join(parts)

    # ---------- internals ----------

    def _cosine_similarity(self, session: Session, candidate_id: UUID, job_id: UUID) -> float:
        resume_vec = session.execute(
            select(ResumeEmbedding.embedding).where(ResumeEmbedding.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if resume_vec is None:
            raise NotFoundError(
                f"Candidate {candidate_id} has no resume embedding. Re-parse the resume first."
            )
        job_vec = session.execute(
            select(JobEmbedding.embedding).where(JobEmbedding.job_id == job_id)
        ).scalar_one_or_none()
        if job_vec is None:
            raise NotFoundError(
                f"Job {job_id} has no JD embedding. Re-create the job to regenerate it."
            )

        a = np.asarray(resume_vec, dtype=np.float64)
        b = np.asarray(job_vec, dtype=np.float64)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0.0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def _reasoning(self, *, job_title: str, job_summary: str, sub: SubScores) -> list[str]:
        try:
            user_prompt = MATCH_REASONING_USER_TEMPLATE.format(
                job_title=job_title,
                job_summary=(job_summary or "")[:1500],
                required_skills=", ".join([str(s) for s in (sub.matched_skills + sub.missing_skills)]) or "—",
                required_years=sub.required_years if sub.required_years is not None else "—",
                candidate_skills=", ".join(sub.matched_skills) or "—",
                candidate_years=f"{sub.candidate_years:.1f}",
                semantic_score=sub.semantic,
                skill_score=sub.skill_overlap,
                experience_score=sub.experience,
                matched_skills=", ".join(sub.matched_skills) or "—",
                missing_skills=", ".join(sub.missing_skills) or "—",
            )
            response = self.llm.complete_json(MATCH_REASONING_SYSTEM, user_prompt)
            data = self._parse_llm_json(response.text)
            bullets = data.get("bullets") if isinstance(data, dict) else None
            if isinstance(bullets, list) and bullets and all(isinstance(b, str) for b in bullets):
                return [b.strip() for b in bullets if b.strip()][:5]
        except (LLMError, ValueError, json.JSONDecodeError) as exc:
            log.warning("match_reasoning_llm_failed", error=str(exc)[:300])

        return rule_based_bullets(sub, job_title)

    @staticmethod
    def _parse_llm_json(text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        return json.loads(cleaned)

    @staticmethod
    def _cached_to_response(row, weights: MatchWeights) -> MatchResponse:
        blob = row.reasoning if isinstance(row.reasoning, dict) else {}
        sub = blob.get("subscores") or {}
        stored_weights = blob.get("weights") or {}
        weights_used = MatchWeights(
            semantic=stored_weights.get("semantic", weights.semantic),
            skill_overlap=stored_weights.get("skill_overlap", weights.skill_overlap),
            experience=stored_weights.get("experience", weights.experience),
            location=stored_weights.get("location", weights.location),
            notice_period=stored_weights.get("notice_period", weights.notice_period),
            salary=stored_weights.get("salary", weights.salary),
        )
        computed = row.computed_at
        if computed.tzinfo is None:
            computed = computed.replace(tzinfo=timezone.utc)
        return MatchResponse(
            candidate_id=row.candidate_id,
            job_id=row.job_id,
            match_score=int(round(float(row.score))),
            subscores=MatchSubscores(
                semantic=float(sub.get("semantic", 50)),
                skill_overlap=float(sub.get("skill_overlap", 50)),
                experience=float(sub.get("experience", 50)),
                location=float(sub.get("location", 50)),
                notice_period=float(sub.get("notice_period", 50)),
                salary=float(sub.get("salary", 50)),
            ),
            reasoning=list(blob.get("bullets") or []),
            weights_used=weights_used,
            cached=True,
            computed_at=computed,
        )
