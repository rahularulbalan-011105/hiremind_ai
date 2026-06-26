from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Candidate, Job, JobEmbedding, ResumeEmbedding
from app.vector_store.base import CandidateHit, JobHit, VectorStore


class PgVectorStore(VectorStore):
    """pgvector-backed implementation. Uses HNSW cosine indexes from db/init/03_indexes.sql."""

    def upsert_resume(
        self, session: Session, candidate_id: UUID, vector: list[float], model: str
    ) -> None:
        stmt = (
            pg_insert(ResumeEmbedding)
            .values(candidate_id=candidate_id, embedding=vector, model=model)
            .on_conflict_do_update(
                index_elements=[ResumeEmbedding.candidate_id],
                set_={"embedding": vector, "model": model},
            )
        )
        session.execute(stmt)
        session.commit()

    def upsert_job(self, session: Session, job_id: UUID, vector: list[float], model: str) -> None:
        stmt = (
            pg_insert(JobEmbedding)
            .values(job_id=job_id, embedding=vector, model=model)
            .on_conflict_do_update(
                index_elements=[JobEmbedding.job_id],
                set_={"embedding": vector, "model": model},
            )
        )
        session.execute(stmt)
        session.commit()

    def search_candidates(
        self, session: Session, query: list[float], top_k: int
    ) -> list[CandidateHit]:
        distance = ResumeEmbedding.embedding.cosine_distance(query)
        stmt = (
            select(
                ResumeEmbedding.candidate_id,
                ResumeEmbedding.model,
                (1.0 - distance).label("similarity"),
                Candidate.full_name,
                Candidate.email,
                Candidate.headline,
                Candidate.location,
            )
            .join(Candidate, Candidate.id == ResumeEmbedding.candidate_id)
            .order_by(distance)
            .limit(top_k)
        )
        rows = session.execute(stmt).all()
        return [
            CandidateHit(
                candidate_id=row.candidate_id,
                similarity=float(row.similarity),
                model=row.model,
                full_name=row.full_name,
                email=row.email,
                headline=row.headline,
                location=row.location,
            )
            for row in rows
        ]

    def search_jobs(self, session: Session, query: list[float], top_k: int) -> list[JobHit]:
        distance = JobEmbedding.embedding.cosine_distance(query)
        stmt = (
            select(
                JobEmbedding.job_id,
                JobEmbedding.model,
                (1.0 - distance).label("similarity"),
                Job.title,
                Job.company_id,
                Job.workplace_location,
            )
            .join(Job, Job.id == JobEmbedding.job_id)
            .order_by(distance)
            .limit(top_k)
        )
        rows = session.execute(stmt).all()
        return [
            JobHit(
                job_id=row.job_id,
                similarity=float(row.similarity),
                model=row.model,
                title=row.title,
                # New schema doesn't carry a company name string column on `jobs`.
                # Returning the company_id as a string keeps the field populated;
                # callers that need the human name should look it up separately.
                company=str(row.company_id) if row.company_id is not None else None,
                location=row.workplace_location,
            )
            for row in rows
        ]
