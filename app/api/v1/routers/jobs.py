from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import embedding_service_dep, session_dep
from app.core.exceptions import NotFoundError
from app.db.models import Job, JobEmbedding
from app.db.repositories.jobs import JobRepository
from app.schemas.job import JobCreateRequest, JobResponse, JobSalaryRange, RequiredSkill
from app.services.embeddings import EmbeddingService
from app.services.jobs import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_response(job: Job, embedding_stored: bool) -> JobResponse:
    salary_raw = JobRepository.salary(job)
    salary = JobSalaryRange.model_validate(salary_raw) if salary_raw else None
    skills = [RequiredSkill.model_validate(s) for s in JobRepository.required_skills(job)]
    return JobResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        company=job.company,
        location=job.location,
        employment_type=job.employment_type,
        status=job.status,  # type: ignore[arg-type]
        required_skills=skills,
        required_years_experience=JobRepository.required_years(job),
        notice_period_days_max=JobRepository.notice_period_max(job),
        salary=salary,
        embedding_stored=embedding_stored,
        posted_at=job.posted_at,
        last_activity_at=job.last_activity_at,
    )


def _jobs_with_embedding_flag(
    session: Session, jobs: list[Job]
) -> list[tuple[Job, bool]]:
    if not jobs:
        return []
    ids = [j.id for j in jobs]
    rows = session.execute(
        select(JobEmbedding.job_id).where(JobEmbedding.job_id.in_(ids))
    ).scalars().all()
    have = set(rows)
    return [(j, j.id in have) for j in jobs]


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job posting and generate its JD embedding.",
)
def create_job(
    body: JobCreateRequest,
    session: Session = Depends(session_dep),
    embedding_service: EmbeddingService = Depends(embedding_service_dep),
) -> JobResponse:
    """
    **Example request**:
    ```json
    {
      "title": "Senior Backend Engineer (Python)",
      "description": "We're hiring a senior Python engineer to own our async data pipeline...",
      "company": "Acme",
      "location": "Bengaluru",
      "employment_type": "full_time",
      "required_skills": [
        {"skill": "python", "min_years": 5},
        {"skill": "fastapi", "min_years": 3},
        {"skill": "postgresql", "min_years": 4},
        {"skill": "aws", "min_years": 2}
      ],
      "required_years_experience": 5,
      "notice_period_days_max": 60,
      "salary": {"min": 2000000, "max": 3500000, "currency": "INR"}
    }
    ```
    """
    service = JobService(embedding_service)
    job = service.create(session, body)
    return _to_response(job, embedding_stored=True)


@router.get(
    "",
    response_model=list[JobResponse],
    summary="List jobs (most recent first).",
)
def list_jobs(
    session: Session = Depends(session_dep),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: Literal["active", "paused", "closed", "archived"] | None = Query(
        default=None, alias="status"
    ),
) -> list[JobResponse]:
    repo = JobRepository(session)
    jobs = repo.list_all(limit=limit, offset=offset, status=status_filter)
    return [_to_response(j, embedding_stored=flag) for j, flag in _jobs_with_embedding_flag(session, jobs)]


@router.get("/{job_id}", response_model=JobResponse, summary="Fetch a job by id.")
def get_job(job_id: UUID, session: Session = Depends(session_dep)) -> JobResponse:
    job = JobRepository(session).get(job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found.")
    has_embedding = (
        session.execute(
            select(JobEmbedding.id).where(JobEmbedding.job_id == job_id)
        ).scalar_one_or_none()
        is not None
    )
    return _to_response(job, embedding_stored=has_embedding)
