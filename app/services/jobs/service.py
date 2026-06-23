from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Job
from app.db.repositories.jobs import JobRepository
from app.schemas.job import JobCreateRequest
from app.services.embeddings import EmbeddingService

log = get_logger(__name__)


class JobService:
    """Creates a job row + generates the JD embedding atomically (from the caller's POV)."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    def create(self, session: Session, payload: JobCreateRequest) -> Job:
        repo = JobRepository(session)
        skills_dicts = [
            {"skill": rs.skill, "min_years": rs.min_years}
            for rs in payload.required_skills
        ]
        salary_dict = payload.salary.model_dump(mode="json") if payload.salary else None

        job = repo.create(
            title=payload.title,
            description=payload.description,
            company=payload.company,
            location=payload.location,
            employment_type=payload.employment_type,
            required_skills=skills_dicts,
            required_years_experience=payload.required_years_experience,
            notice_period_days_max=payload.notice_period_days_max,
            salary=salary_dict,
        )

        embed_text = self._jd_embed_text(payload)
        vector = self.embedding_service.embed(embed_text)
        self.embedding_service.store(session, "job", job.id, vector)
        log.info(
            "job_created",
            job_id=str(job.id),
            title=job.title,
            skills=len(payload.required_skills),
        )
        return job

    @staticmethod
    def _jd_embed_text(payload: JobCreateRequest) -> str:
        parts: list[str] = [payload.title]
        if payload.required_skills:
            skill_summary = ", ".join(
                f"{rs.skill} ({rs.min_years:.0f}+y)" if rs.min_years > 0 else rs.skill
                for rs in payload.required_skills
            )
            parts.append("Required skills: " + skill_summary)
        if payload.required_years_experience is not None:
            parts.append(f"Required experience: {payload.required_years_experience}+ years")
        if payload.location:
            parts.append(f"Location: {payload.location}")
        parts.append(payload.description)
        return "\n".join(parts)
