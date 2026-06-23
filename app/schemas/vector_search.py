from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CandidateSearchFilters(BaseModel):
    location: str | None = None
    min_experience_years: float | None = None


class CandidateSearchRequest(BaseModel):
    query_text: str | None = Field(default=None, description="Free-text query; will be embedded server-side.")
    query_embedding: list[float] | None = Field(
        default=None, description="Precomputed embedding. Mutually exclusive with query_text."
    )
    top_k: int = Field(default=10, ge=1, le=200)
    filters: CandidateSearchFilters = Field(default_factory=CandidateSearchFilters)

    @model_validator(mode="after")
    def _exactly_one_query(self) -> "CandidateSearchRequest":
        if (self.query_text is None) == (self.query_embedding is None):
            raise ValueError("Provide exactly one of `query_text` or `query_embedding`.")
        return self


class CandidateHit(BaseModel):
    candidate_id: UUID
    similarity: float
    model: str
    full_name: str | None = None
    email: str | None = None
    headline: str | None = None
    location: str | None = None


class CandidateSearchResponse(BaseModel):
    hits: list[CandidateHit]
    model: str
    top_k: int
    ignored_filters: list[str] = Field(
        default_factory=list,
        description="Filters accepted by the schema but not yet applied in this build.",
    )
