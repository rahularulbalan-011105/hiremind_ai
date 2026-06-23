from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import EntityKind


class StoreAs(BaseModel):
    kind: EntityKind
    id: UUID


class EmbeddingRequest(BaseModel):
    text: str = Field(min_length=1, description="Text to embed.")
    store_as: StoreAs | None = Field(
        default=None,
        description="If provided, persist the embedding against the given candidate or job.",
    )
    include_vector: bool = Field(
        default=True,
        description="Whether to return the full vector in the response.",
    )


class EmbeddingResponse(BaseModel):
    model: str
    dim: int
    norm: float
    stored: bool
    stored_kind: EntityKind | None = None
    stored_entity_id: UUID | None = None
    embedding: list[float] | None = None
