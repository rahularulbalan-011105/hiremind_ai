from fastapi import APIRouter, Depends, Request

from app.api.v1.deps import embedding_service_dep
from app.core.config import Settings, get_settings
from app.db.session import ping
from app.schemas.common import HealthResponse
from app.services.embeddings import EmbeddingService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    request: Request,
    embedding_service: EmbeddingService = Depends(embedding_service_dep),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    try:
        results = ping()
    except Exception:
        results = {}
    # Healthy only if every wired DB responded. Embedding model is loaded
    # eagerly at startup, so by here it's already in memory.
    db_ok = bool(results) and all(results.values())

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        embedding_model=embedding_service.model_name,
        embedding_dim=embedding_service.dim,
        app_env=settings.app_env,
    )
