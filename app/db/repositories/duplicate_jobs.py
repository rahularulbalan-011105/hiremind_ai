from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import DuplicateJobCluster


class DuplicateJobRepository:
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
        stmt = (
            pg_insert(DuplicateJobCluster)
            .values(
                job_id=job_id,
                duplicate_of_job_id=duplicate_of_job_id,
                similarity=Decimal(str(round(similarity, 4))),
                method=method,
            )
            .on_conflict_do_update(
                index_elements=[
                    DuplicateJobCluster.job_id,
                    DuplicateJobCluster.duplicate_of_job_id,
                    DuplicateJobCluster.method,
                ],
                set_={"similarity": Decimal(str(round(similarity, 4)))},
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
            self.session.add(
                DuplicateJobCluster(
                    job_id=job_id,
                    duplicate_of_job_id=dup_id,
                    similarity=Decimal(str(round(sim, 4))),
                    method=method,
                )
            )
        self.session.commit()
