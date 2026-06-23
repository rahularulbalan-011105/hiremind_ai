from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.embeddings import EmbeddingService
from app.vector_store import VectorStore


def session_dep() -> Iterator[Session]:
    yield from get_session()


def embedding_service_dep(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


def vector_store_dep(request: Request) -> VectorStore:
    return request.app.state.vector_store


SessionDep = Depends(session_dep)
EmbeddingServiceDep = Depends(embedding_service_dep)
VectorStoreDep = Depends(vector_store_dep)
