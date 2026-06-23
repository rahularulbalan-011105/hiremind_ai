from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import candidates as candidates_router
from app.api.v1.routers import duplicate_jobs as duplicate_jobs_router
from app.api.v1.routers import embeddings as embeddings_router
from app.api.v1.routers import fake_profile as fake_profile_router
from app.api.v1.routers import ghost_jobs as ghost_jobs_router
from app.api.v1.routers import health as health_router
from app.api.v1.routers import hiring_predictor as hiring_predictor_router
from app.api.v1.routers import jobs as jobs_router
from app.api.v1.routers import match as match_router
from app.api.v1.routers import ranker as ranker_router
from app.api.v1.routers import resumes as resumes_router
from app.api.v1.routers import vector_search as vector_search_router

# Import the configured Celery app so the API process knows which broker
# (Redis) to publish tasks to. Without this, kombu falls back to AMQP defaults.
from app.workers import celery_app as _celery_app_module  # noqa: F401
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import init_engine
from app.services.embeddings import EmbeddingService
from app.vector_store import get_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("app.startup")

    log.info("starting", app_env=settings.app_env)
    init_engine(settings)

    vector_store = get_vector_store(settings)
    embedding_service = EmbeddingService(settings.embedding_model, vector_store)
    embedding_service.warm_up()  # loads the sentence-transformers model

    app.state.settings = settings
    app.state.vector_store = vector_store
    app.state.embedding_service = embedding_service

    log.info("ready")
    try:
        yield
    finally:
        log.info("shutdown")


app = FastAPI(
    title="HRMS AI",
    version="0.1.0",
    description="AI subsystem for the HRMS recruitment platform.",
    lifespan=lifespan,
)

# CORS — permissive in development; tighten for prod via env.
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list if _settings.app_env != "development" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Routers — versioned under /api/v1.
app.include_router(health_router.router, prefix="/api/v1")
app.include_router(embeddings_router.router, prefix="/api/v1")
app.include_router(vector_search_router.router, prefix="/api/v1")
app.include_router(resumes_router.router, prefix="/api/v1")
app.include_router(jobs_router.router, prefix="/api/v1")
app.include_router(match_router.router, prefix="/api/v1")
app.include_router(fake_profile_router.router, prefix="/api/v1")
app.include_router(candidates_router.router, prefix="/api/v1")
app.include_router(duplicate_jobs_router.router, prefix="/api/v1")
app.include_router(ghost_jobs_router.router, prefix="/api/v1")
app.include_router(hiring_predictor_router.router, prefix="/api/v1")
app.include_router(ranker_router.router, prefix="/api/v1")
