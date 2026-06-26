from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import ParseJob
from app.schemas.resume_parser import ParseJobStatus


class ParseJobRepository:
    """Lives in `hiremind_candidate`."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self, source_url: str | None = None, file_key: str | None = None
    ) -> ParseJob:
        job = ParseJob(status="queued", source_url=source_url, file_key=file_key)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, parse_job_id: UUID) -> ParseJob | None:
        return self.session.get(ParseJob, parse_job_id)

    def mark(
        self,
        parse_job_id: UUID,
        status: ParseJobStatus,
        *,
        candidate_id: UUID | None = None,
        error: str | None = None,
    ) -> None:
        job = self.session.get(ParseJob, parse_job_id)
        if job is None:
            return
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        if candidate_id is not None:
            # Schema column is `candidate_user_id` but stores the candidate id.
            job.candidate_user_id = candidate_id
        if error is not None:
            job.error = error[:2000]
        self.session.commit()
