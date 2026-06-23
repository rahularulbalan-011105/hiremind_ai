from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import embedding_service_dep, session_dep, vector_store_dep
from app.core.exceptions import ValidationError
from app.schemas.vector_search import (
    CandidateHit,
    CandidateSearchRequest,
    CandidateSearchResponse,
)
from app.services.embeddings import EmbeddingService
from app.vector_store import VectorStore

router = APIRouter(prefix="/vector-search", tags=["vector-search"])


@router.post(
    "/candidates",
    response_model=CandidateSearchResponse,
    summary="Top-K cosine search over stored resume embeddings.",
)
def search_candidates(
    body: CandidateSearchRequest,
    session: Session = Depends(session_dep),
    embedding_service: EmbeddingService = Depends(embedding_service_dep),
    vector_store: VectorStore = Depends(vector_store_dep),
) -> CandidateSearchResponse:
    """
    **Example request**:
    ```json
    {
      "query_text": "FastAPI engineer with pgvector experience",
      "top_k": 10,
      "filters": {"location": null, "min_experience_years": 3}
    }
    ```
    """
    if body.query_embedding is not None:
        if len(body.query_embedding) != embedding_service.dim:
            raise ValidationError(
                f"query_embedding has dim {len(body.query_embedding)}; expected {embedding_service.dim}."
            )
        query_vec = list(body.query_embedding)
    else:
        assert body.query_text is not None
        query_vec = embedding_service.embed(body.query_text)

    hits = vector_store.search_candidates(session, query_vec, body.top_k)

    ignored: list[str] = []
    if body.filters.location is not None:
        ignored.append("location")
    if body.filters.min_experience_years is not None:
        ignored.append("min_experience_years")

    return CandidateSearchResponse(
        hits=[
            CandidateHit(
                candidate_id=h.candidate_id,
                similarity=h.similarity,
                model=h.model,
                full_name=h.full_name,
                email=h.email,
                headline=h.headline,
                location=h.location,
            )
            for h in hits
        ],
        model=embedding_service.model_name,
        top_k=body.top_k,
        ignored_filters=ignored,
    )
