from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import DuplicateJobCluster


class DuplicateJobRepository:
    """Lives in `hiremind_company`.

    The live schema kept the old `(job_id, duplicate_of_job_id, similarity, method)`
    pair AND added a richer `(job_a, job_b, verdict, title_sim, embedding_sim,
    skill_jaccard)` pair. This repo writes the legacy pair (no API change) and
    mirrors `job_id`/`duplicate_of_job_id` into `job_a`/`job_b` for parity.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_for_job(self, job_id: UUID, method: str = "combined") -> list[DuplicateJobCluster]:
        return list(
            self.session.execute(
                select(DuplicateJobCluster).where(
                    DuplicateJobCluster.job_id == job_id,
                    DuplicateJobCluster.method == method,
                )
            ).scalars().all()
        )

    def upsert(
        self,
        *,
        job_id: UUID,
        duplicate_of_job_id: UUID,
        similarity: float,
        method: str,
    ) -> None:
        sim = Decimal(str(round(similarity, 4)))
        stmt = (
            pg_insert(DuplicateJobCluster)
            .values(
                job_id=job_id,
                duplicate_of_job_id=duplicate_of_job_id,
                similarity=sim,
                method=method,
                job_a=job_id,
                job_b=duplicate_of_job_id,
            )
            .on_conflict_do_update(
                index_elements=[
                    DuplicateJobCluster.job_id,
                    DuplicateJobCluster.duplicate_of_job_id,
                    DuplicateJobCluster.method,
                ],
                set_={"similarity": sim},
            )
        )
        self.session.execute(stmt)
        self.session.commit()

    def replace_for_job(
        self,
        *,
        job_id: UUID,
        method: str,
        pairs: list[tuple[UUID, float]],
    ) -> None:
        """Replace all rows for (job_id, method) with the given list."""
        self.session.execute(
            delete(DuplicateJobCluster).where(
                DuplicateJobCluster.job_id == job_id,
                DuplicateJobCluster.method == method,
            )
        )
        for dup_id, sim in pairs:
            sim_dec = Decimal(str(round(sim, 4)))
            self.session.add(
                DuplicateJobCluster(
                    job_id=job_id,
                    duplicate_of_job_id=dup_id,
                    similarity=sim_dec,
                    method=method,
                    job_a=job_id,
                    job_b=dup_id,
                )
            )
        self.session.commit()
