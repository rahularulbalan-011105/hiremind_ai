from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
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
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings),
) -> ParseJobAccepted:
    """
    Returns `202 Accepted` immediately with a `parse_job_id`. Poll
    `GET /api/v1/resumes/parse-jobs/{id}` until status is `succeeded` or `failed`.
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
        args=[str(job.id), str(stored_path)],
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
        candidate_id=job.candidate_id,
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
    bundle = CandidateRepository(session).get_with_children(candidate_id)
    if bundle is None:
        raise NotFoundError(f"Candidate {candidate_id} not found.")
    candidate, experiences, educations, skills, certifications, languages = bundle
    return CandidateProfile(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        headline=candidate.headline,
        location=candidate.location,
        skills=[s.skill for s in skills],
        experience=[
            ParsedExperience(
                company=e.company,
                title=e.title,
                start_date=e.start_date,
                end_date=e.end_date,
                is_current=e.is_current,
                description=e.description,
            )
            for e in experiences
        ],
        education=[
            ParsedEducation(
                institution=e.institution,
                degree=e.degree,
                field=e.field,
                start_date=e.start_date,
                end_date=e.end_date,
                grade=e.grade,
            )
            for e in educations
        ],
        certifications=[
            ParsedCertification(
                name=c.name,
                issuer=c.issuer,
                issued_date=c.issued_date,
                expires_date=c.expires_date,
            )
            for c in certifications
        ],
        languages=[ParsedLanguage(language=l.language, proficiency=l.proficiency) for l in languages],
        raw_resume_url=candidate.raw_resume_url,
        created_at=_aware(candidate.created_at),
    )


def _aware(dt: datetime) -> datetime:
    """Postgres returns timezone-aware; this guard is just for typing/tests."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
