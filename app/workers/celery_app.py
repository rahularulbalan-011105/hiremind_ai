from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import init_engine

_settings = get_settings()

celery_app = Celery(
    "hrms_ai",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=["app.workers.tasks.resume_parser"],
)

# Queue routing — each module gets its own queue (CLAUDE.md §10).
celery_app.conf.task_routes = {
    "app.workers.tasks.resume_parser.*": {"queue": "resume_parsing"},
}

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=200,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


@celery_app.on_after_configure.connect
def _on_worker_boot(sender, **_):
    """Init logging + DB engine once per worker process."""
    configure_logging(_settings.log_level)
    init_engine(_settings)
