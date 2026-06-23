from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CandidateHit:
    candidate_id: UUID
    similarity: float
    model: str
    full_name: str | None
    email: str | None
    headline: str | None
    location: str | None


@dataclass(frozen=True)
class JobHit:
    job_id: UUID
    similarity: float
    model: str
    title: str | None
    company: str | None
    location: str | None


class VectorStore(ABC):
    """
    Backend-agnostic interface for vector reads/writes.
    All services go through this — no raw SQL in service layer.
    """

    @abstractmethod
    def upsert_resume(self, session: Session, candidate_id: UUID, vector: list[float], model: str) -> None: ...

    @abstractmethod
    def upsert_job(self, session: Session, job_id: UUID, vector: list[float], model: str) -> None: ...

    @abstractmethod
    def search_candidates(
        self, session: Session, query: list[float], top_k: int
    ) -> list[CandidateHit]: ...

    @abstractmethod
    def search_jobs(self, session: Session, query: list[float], top_k: int) -> list[JobHit]: ...
