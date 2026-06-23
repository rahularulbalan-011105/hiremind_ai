"""
Feature extraction for the hiring probability predictor.

All features pulled (or derived) from data we already have:
  - match_scores  (six match sub-scores when cached, else computed live via MatchEngine)
  - fake_profile_scores  (trust_score, falls back to 100 if not scored)
  - candidate_experience (years calc)
  - jobs.metadata (required_skills with min_years, required_years_experience)
  - fake_profile_scores.anomalies.github_check (verified-skill flag)

Feature order is FROZEN — XGBoost models trained against this list must be
re-trained when the order changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from app.db.models import FakeProfileScore, MatchScore
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.jobs import JobRepository
from app.llm import LLMClient
from app.schemas.match import MatchWeights
from app.services.match_engine import MatchEngineService

# Authoritative list. ORDER MATTERS — used as the column order in train + predict.
FEATURE_NAMES: tuple[str, ...] = (
    "semantic_score",
    "skill_overlap_score",
    "experience_score",
    "location_score",
    "notice_period_score",
    "salary_score",
    "trust_score",
    "candidate_years",
    "required_years_gap",
    "meets_all_required_skills",
    "github_verified_skills",
)


@dataclass(frozen=True)
class FeatureVector:
    values: dict[str, float]

    def as_array(self) -> np.ndarray:
        return np.array([self.values[name] for name in FEATURE_NAMES], dtype=np.float64)


class FeatureExtractor:
    """
    Builds a FeatureVector for one (candidate, job) pair. Uses cached match
    scores when available, computes fresh via MatchEngine otherwise.
    """

    def __init__(self, llm: LLMClient | None = None):
        # llm is optional — only needed if we fall through to recomputing matches
        # AND the user wants LLM reasoning. Predictor doesn't use it.
        self._match_service = MatchEngineService(llm) if llm is not None else None

    def extract(
        self,
        session: Session,
        *,
        candidate_id: UUID,
        job_id: UUID,
    ) -> FeatureVector:
        candidate_repo = CandidateRepository(session)
        job_repo = JobRepository(session)

        candidate = candidate_repo.get(candidate_id)
        job = job_repo.get(job_id)
        if candidate is None or job is None:
            raise ValueError(f"Candidate {candidate_id} or Job {job_id} not found.")

        # 1. Match sub-scores — pull from cached match_scores when present
        match_row = session.execute(
            MatchScore.__table__.select().where(
                (MatchScore.candidate_id == candidate_id)
                & (MatchScore.job_id == job_id)
            )
        ).first()

        sub: dict[str, float]
        if match_row is not None and isinstance(match_row.reasoning, dict):
            cached_sub = match_row.reasoning.get("subscores") or {}
            sub = {
                "semantic_score": float(cached_sub.get("semantic", 50.0)),
                "skill_overlap_score": float(cached_sub.get("skill_overlap", 50.0)),
                "experience_score": float(cached_sub.get("experience", 50.0)),
                "location_score": float(cached_sub.get("location", 50.0)),
                "notice_period_score": float(cached_sub.get("notice_period", 50.0)),
                "salary_score": float(cached_sub.get("salary", 50.0)),
            }
        elif self._match_service is not None:
            mr = self._match_service.score(
                session,
                candidate_id=candidate_id,
                job_id=job_id,
                weights=MatchWeights(),
                force_recompute=False,
            )
            sub = {
                "semantic_score": mr.subscores.semantic,
                "skill_overlap_score": mr.subscores.skill_overlap,
                "experience_score": mr.subscores.experience,
                "location_score": mr.subscores.location,
                "notice_period_score": mr.subscores.notice_period,
                "salary_score": mr.subscores.salary,
            }
        else:
            # No cached match and no LLM available — neutral defaults
            sub = {k: 50.0 for k in (
                "semantic_score", "skill_overlap_score", "experience_score",
                "location_score", "notice_period_score", "salary_score",
            )}

        # 2. Trust score
        fp_row = session.execute(
            FakeProfileScore.__table__.select().where(
                FakeProfileScore.candidate_id == candidate_id
            )
        ).first()
        trust = float(fp_row.trust_score) if fp_row is not None else 100.0
        github_verified = 0.0
        if fp_row is not None and isinstance(fp_row.anomalies, dict):
            gh = (fp_row.anomalies or {}).get("github_check") or {}
            found = gh.get("claimed_skills_found_in_repos") or []
            github_verified = 1.0 if len(found) > 0 else 0.0

        # 3. Experience
        candidate_years = candidate_repo.years_of_experience(candidate_id)
        required_years = JobRepository.required_years(job)
        required_years_gap = (
            candidate_years - required_years if required_years is not None else 0.0
        )

        # 4. Meets all required skills (at min_years)
        candidate_skills = set(candidate_repo.get_skills(candidate_id))
        prefs = candidate_repo.get_preferences(candidate_id)
        skill_years_overrides = {
            str(k).lower(): float(v) for k, v in (prefs.get("skill_years") or {}).items()
        }
        meets_all = 1.0
        required = JobRepository.required_skills(job)
        if required:
            for entry in required:
                skill = str(entry["skill"]).lower()
                min_years = float(entry.get("min_years") or 0)
                if skill not in candidate_skills:
                    meets_all = 0.0
                    break
                if skill_years_overrides.get(skill, candidate_years) < min_years:
                    meets_all = 0.0
                    break
        else:
            meets_all = 0.5  # neutral — no requirements specified

        values = {
            **sub,
            "trust_score": trust,
            "candidate_years": float(candidate_years),
            "required_years_gap": float(required_years_gap),
            "meets_all_required_skills": meets_all,
            "github_verified_skills": github_verified,
        }
        # Sanity: every authoritative feature must be populated
        for name in FEATURE_NAMES:
            if name not in values:
                values[name] = 50.0 if name.endswith("_score") else 0.0
        return FeatureVector(values=values)
