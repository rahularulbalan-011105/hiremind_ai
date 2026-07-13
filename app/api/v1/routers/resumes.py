from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import session_dep
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.parse_jobs import ParseJobRepository
from app.schemas.resume_parser import (
    CandidateProfile,
    ParsedCertification,
    ParsedEducation,
    ParsedExperience,
    ParsedLanguage,
    ParseJobAccepted,
    ParseJobStatusResponse,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])

_ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/parse",
    response_model=ParseJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a resume for async parsing.",
)
def parse_resume(
    file: UploadFile = File(...),
    candidate_id: uuid.UUID | None = Form(default=None),
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings),
) -> ParseJobAccepted:
    """
    Returns `202 Accepted` immediately with a `parse_job_id`. Poll
    `GET /api/v1/resumes/parse-jobs/{id}` until status is `succeeded` or `failed`.

    Optional `candidate_id` (multipart form field) binds the parse to an existing
    candidate profile (candidate-side self-service upload) so the resume embedding is
    stored under that profile id — required for the candidate's own job match scores.
    Omit it for recruiter bulk-import, which creates a fresh candidate row.
    """
    if not file.filename:
        raise ValidationError("Upload is missing a filename.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValidationError(f"Unsupported file type {suffix!r}. Use PDF or DOCX.")

    upload_dir = Path(settings.artifacts_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = upload_dir / stored_name

    written = 0
    with stored_path.open("wb") as out:
        while True:
            chunk = file.file.read(1 << 20)
            if not chunk:
                break
            written += len(chunk)
            if written > _MAX_BYTES:
                out.close()
                stored_path.unlink(missing_ok=True)
                raise ValidationError(f"Resume exceeds {_MAX_BYTES // (1024 * 1024)}MB limit.")
            out.write(chunk)

    job = ParseJobRepository(session).create(source_url=f"file://{stored_path.as_posix()}")

    # Use the configured celery_app directly so we always publish to the Redis
    # broker (not kombu's AMQP default).
    from app.workers.celery_app import celery_app

    celery_app.send_task(
        "app.workers.tasks.resume_parser.parse_resume",
        args=[str(job.id), str(stored_path), str(candidate_id) if candidate_id else None],
        queue="resume_parsing",
    )

    return ParseJobAccepted(parse_job_id=job.id, status="queued")


@router.get(
    "/parse-jobs/{parse_job_id}",
    response_model=ParseJobStatusResponse,
    summary="Poll a parse job until it succeeds or fails.",
)
def get_parse_job(
    parse_job_id: uuid.UUID,
    session: Session = Depends(session_dep),
) -> ParseJobStatusResponse:
    job = ParseJobRepository(session).get(parse_job_id)
    if job is None:
        raise NotFoundError(f"Parse job {parse_job_id} not found.")
    return ParseJobStatusResponse(
        parse_job_id=job.id,
        status=job.status,  # type: ignore[arg-type]
        candidate_id=job.candidate_user_id,
        source_url=job.source_url,
        error=job.error,
        created_at=_aware(job.created_at),
        updated_at=_aware(job.updated_at),
    )


@router.get(
    "/{candidate_id}",
    response_model=CandidateProfile,
    summary="Fetch a parsed candidate profile (with experience, skills, etc.).",
)
def get_candidate(
    candidate_id: uuid.UUID,
    session: Session = Depends(session_dep),
) -> CandidateProfile:
    repo = CandidateRepository(session)
    bundle = repo.get_with_children(candidate_id)
    if bundle is None:
        raise NotFoundError(f"Candidate {candidate_id} not found.")
    candidate, experiences, educations, _skills, certifications, _languages = bundle
    return CandidateProfile(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        headline=candidate.headline,
        location=candidate.location,
        # Skill names resolved via the master `skills` table (candidate_skills stores skill_id).
        skills=repo.get_skills(candidate_id),
        experience=[
            ParsedExperience(
                company=e.company_name,
                title=e.job_title,
                start_date=e.start_date,
                end_date=e.end_date,
                is_current=e.currently_working,
                description=None,
            )
            for e in experiences
        ],
        education=[
            ParsedEducation(
                institution=e.institution,
                degree=e.degree,
                field=e.specialization,
                start_date=None,
                end_date=None,
                grade=e.grade,
            )
            for e in educations
        ],
        certifications=[
            ParsedCertification(
                name=c.certification_name,
                issuer=c.issuing_institution,
                issued_date=None,
                expires_date=c.valid_till,
            )
            for c in certifications
        ],
        languages=[],
        raw_resume_url=candidate.raw_resume_url,
        created_at=_aware(candidate.created_at),
    )


def _aware(dt: datetime) -> datetime:
    """Postgres returns timezone-aware; this guard is just for typing/tests."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
