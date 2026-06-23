from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, job_id: UUID) -> Job | None:
        return self.session.get(Job, job_id)

    def exists(self, job_id: UUID) -> bool:
        return self.session.get(Job, job_id) is not None

    def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        recruiter_id: UUID | None = None,
    ) -> list[Job]:
        stmt = select(Job).order_by(Job.posted_at.desc()).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if recruiter_id is not None:
            stmt = stmt.where(Job.recruiter_id == recruiter_id)
        return list(self.session.execute(stmt).scalars().all())

    def create(
        self,
        *,
        title: str,
        description: str,
        company: str | None,
        location: str | None,
        employment_type: str | None,
        required_skills: list[dict],
        required_years_experience: float | None,
        notice_period_days_max: int | None,
        salary: dict | None,
        extra_metadata: dict | None = None,
    ) -> Job:
        metadata: dict = dict(extra_metadata or {})
        metadata["required_skills"] = required_skills  # list of {skill, min_years}
        metadata["required_years_experience"] = required_years_experience
        metadata["notice_period_days_max"] = notice_period_days_max
        metadata["salary"] = salary  # {min, max, currency} or None

        job = Job(
            title=title,
            description=description,
            company=company,
            location=location,
            employment_type=employment_type,
            metadata_=metadata,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    @staticmethod
    def required_skills(job: Job) -> list[dict]:
        """
        Returns required_skills as a list of {skill, min_years}.
        Backwards-compat: jobs created before the schema change stored a flat
        list of strings; we normalize them on read.
        """
        meta = job.metadata_ or {}
        raw = meta.get("required_skills") or []
        out: list[dict] = []
        for entry in raw:
            if isinstance(entry, str):
                out.append({"skill": entry.lower(), "min_years": 0})
            elif isinstance(entry, dict) and entry.get("skill"):
                out.append({
                    "skill": str(entry["skill"]).lower(),
                    "min_years": float(entry.get("min_years") or 0),
                })
        return out

    @staticmethod
    def required_skill_names(job: Job) -> list[str]:
        return [s["skill"] for s in JobRepository.required_skills(job)]

    @staticmethod
    def required_years(job: Job) -> float | None:
        meta = job.metadata_ or {}
        val = meta.get("required_years_experience")
        return float(val) if val is not None else None

    @staticmethod
    def notice_period_max(job: Job) -> int | None:
        meta = job.metadata_ or {}
        val = meta.get("notice_period_days_max")
        return int(val) if val is not None else None

    @staticmethod
    def salary(job: Job) -> dict | None:
        meta = job.metadata_ or {}
        val = meta.get("salary")
        if not val or not isinstance(val, dict):
            return None
        return val
