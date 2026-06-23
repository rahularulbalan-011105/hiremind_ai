from typing import Literal

from pydantic import BaseModel

EntityKind = Literal["resume", "job"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    embedding_model: str
    embedding_dim: int
    app_env: str
