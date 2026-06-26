from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import (
    get_candidate_session,
    get_company_session,
    get_users_session,
)
from app.services.embeddings import EmbeddingService
from app.vector_store import VectorStore


def candidate_session_dep() -> Iterator[Session]:
    yield from get_candidate_session()


def company_session_dep() -> Iterator[Session]:
    yield from get_company_session()


def users_session_dep() -> Iterator[Session]:
    yield from get_users_session()


# Back-compat shim: the old single-DB code called this `session_dep`. Most
# legacy callers operated on candidate data, so we keep it pointing there.
# New code should use the explicit `candidate_session_dep` / `company_session_dep`.
def session_dep() -> Iterator[Session]:
    yield from get_candidate_session()


def embedding_service_dep(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


def vector_store_dep(request: Request) -> VectorStore:
    return request.app.state.vector_store


SessionDep = Depends(session_dep)  # legacy alias → candidate DB
CandidateSessionDep = Depends(candidate_session_dep)
CompanySessionDep = Depends(company_session_dep)
UsersSessionDep = Depends(users_session_dep)
EmbeddingServiceDep = Depends(embedding_service_dep)
VectorStoreDep = Depends(vector_store_dep)
