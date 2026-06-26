import math

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import (
    candidate_session_dep,
    company_session_dep,
    embedding_service_dep,
)
from app.schemas.embeddings import EmbeddingRequest, EmbeddingResponse
from app.services.embeddings import EmbeddingService

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post(
    "/generate",
    response_model=EmbeddingResponse,
    summary="Generate (and optionally store) an embedding.",
    response_description="Embedding vector + metadata.",
)
def generate_embedding(
    body: EmbeddingRequest,
    candidate_session: Session = Depends(candidate_session_dep),
    company_session: Session = Depends(company_session_dep),
    embedding_service: EmbeddingService = Depends(embedding_service_dep),
) -> EmbeddingResponse:
    """
    **Example request**:
    ```json
    {
      "text": "Senior Python engineer with FastAPI and pgvector experience.",
      "store_as": {"kind": "resume", "id": "11111111-1111-1111-1111-111111111111"},
      "include_vector": false
    }
    ```
    """
    vector = embedding_service.embed(body.text)
    norm = math.sqrt(sum(v * v for v in vector))

    stored = False
    stored_kind = None
    stored_entity_id = None
    if body.store_as is not None:
        # Resume embeddings live in hiremind_candidate; job embeddings in hiremind_company.
        session = candidate_session if body.store_as.kind == "resume" else company_session
        embedding_service.store(session, body.store_as.kind, body.store_as.id, vector)
        stored = True
        stored_kind = body.store_as.kind
        stored_entity_id = body.store_as.id

    return EmbeddingResponse(
        model=embedding_service.model_name,
        dim=embedding_service.dim,
        norm=norm,
        stored=stored,
        stored_kind=stored_kind,
        stored_entity_id=stored_entity_id,
        embedding=vector if body.include_vector else None,
    )
