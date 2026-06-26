from __future__ import annotations

from pathlib import Path
from uuid import UUID

from celery import shared_task

from app.core.config import get_settings
from app.core.exceptions import HrmsAIError
from app.core.logging import get_logger
from app.db.repositories.parse_jobs import ParseJobRepository
from app.db.session import get_candidate_session, init_engine
from app.llm import get_llm_client
from app.services.embeddings import EmbeddingService
from app.services.resume_parser import ResumeParserService
from app.vector_store import get_vector_store

log = get_logger(__name__)

# Worker-process singletons. Each Celery worker process holds its own.
_embedding_service: EmbeddingService | None = None


def _get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        settings = get_settings()
        # The worker process has its own copy of the settings, engines etc.
        # init_engine is idempotent; safe to call here.
        init_engine(settings)
        store = get_vector_store(settings)
        _embedding_service = EmbeddingService(settings.embedding_model, store)
        _embedding_service.warm_up()
    return _embedding_service


@shared_task(
    name="app.workers.tasks.resume_parser.parse_resume",
    bind=True,
    autoretry_for=(),
    max_retries=0,
)
def parse_resume(self, parse_job_id: str, file_path: str) -> dict:
    """
    Parse one uploaded resume file end-to-end. State transitions are persisted
    in `parse_jobs`. We don't auto-retry — failures are surfaced to the user.
    """
    settings = get_settings()
    job_uuid = UUID(parse_job_id)
    path = Path(file_path)

    # Resume parsing writes to the candidate DB (candidate, parse_jobs,
    # resume_embeddings, fake_profile_scores etc.).
    session_iter = get_candidate_session()
    session = next(session_iter)
    try:
        llm = get_llm_client(settings)
        service = ResumeParserService(settings, llm, _get_embedding_service())
        candidate_id = service.parse(session, job_uuid, path)
        ParseJobRepository(session).mark(job_uuid, "succeeded", candidate_id=candidate_id)
        return {"status": "succeeded", "candidate_id": str(candidate_id)}
    except HrmsAIError as exc:
        log.warning("parse_task_known_error", parse_job_id=parse_job_id, error=exc.message)
        ParseJobRepository(session).mark(job_uuid, "failed", error=exc.message)
        return {"status": "failed", "error": exc.message}
    except Exception as exc:  # noqa: BLE001
        log.exception("parse_task_uncaught")
        ParseJobRepository(session).mark(job_uuid, "failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}
    finally:
        try:
            next(session_iter)
        except StopIteration:
            pass
