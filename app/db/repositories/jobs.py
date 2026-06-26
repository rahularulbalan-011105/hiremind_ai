"""
Job repository — operates on the `hiremind_company` Postgres DB.

The new schema replaced the old `metadata` JSONB with:
  * proper columns on `jobs` (salary_*, notice_period, experience_min_years, …)
  * `job_skills`           — required/preferred skills with min_experience per row
  * `job_benefits`         — many-to-one benefits
  * `job_employment_type_prefs` / `job_notice_period_prefs` — multi-select prefs

The Pythonic surface that services depend on (`required_skills`, `required_years`,
`notice_period_max`, `salary`) is preserved as static helpers — they just read
from columns + child tables now instead of poking metadata jsonb.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    # ── reads ──────────────────────────────────────────────────────────────
    def get(self, job_id: UUID) -> Job | None:
        return self.session.get(Job, job_id)

    def get_many(self, ids: list[UUID]) -> dict[UUID, Job]:
        if not ids:
            return {}
        rows = self.session.execute(select(Job).where(Job.id.in_(ids))).scalars().all()
        return {row.id: row for row in rows}

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
        stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if recruiter_id is not None:
            stmt = stmt.where(Job.user_id == recruiter_id)
        return list(self.session.execute(stmt).scalars().all())

    # ── writes ─────────────────────────────────────────────────────────────
    def create(
        self,
        *,
        title: str,
        description: str,
        company_id: UUID | None = None,
        user_id: UUID | None = None,
        company: str | None = None,  # ignored — no name column on new jobs table
        location: str | None = None,
        workplace_location: str | None = None,
        employment_type: str | None = None,
        required_skills: list[dict] | None = None,
        required_years_experience: float | None = None,
        notice_period_days_max: int | None = None,
        salary: dict | None = None,
        status: str = "DRAFT",
    ) -> Job:
        """Lightweight create — used by the AI test harness. Production callers
        use the company-service Spring Boot app, which writes far more fields.

        Back-compat: accepts the legacy `company`/`location` kwargs and folds
        them in (`company` is ignored since the new schema has no name column;
        `location` becomes `workplace_location`).
        """
        from uuid import uuid4

        if company is not None and not workplace_location and location is None:
            # Old callers passed the company name; nothing to do with it here.
            pass
        if location is not None and workplace_location is None:
            workplace_location = location

        job = Job(
            company_id=company_id or uuid4(),
            user_id=user_id or uuid4(),
            title=title,
            description=description,
            workplace_location=workplace_location,
            employment_type=employment_type,
            status=status,
        )
        if required_years_experience is not None:
            job.experience_min_years = int(required_years_experience)
        if notice_period_days_max is not None:
            job.notice_period = f"{notice_period_days_max} Days"
        if salary:
            job.currency = salary.get("currency")
            if salary.get("min") is not None:
                job.salary_min_ctc = salary["min"]
            if salary.get("max") is not None:
                job.salary_max_ctc = salary["max"]
            if salary.get("min") is None and salary.get("max") is None and salary.get("ctc"):
                job.annual_ctc = salary["ctc"]

        self.session.add(job)
        self.session.flush()

        for idx, sk in enumerate(required_skills or []):
            self.session.add(
                JobSkill(
                    job_id=job.id,
                    name=sk["skill"],
                    min_experience=int(sk.get("min_years") or 0),
                    mandatory=bool(sk.get("mandatory", True)),
                    sort_order=idx,
                )
            )

        self.session.commit()
        self.session.refresh(job)
        return job

    def bump_last_activity(self, job_id: UUID) -> None:
        """Recruiter-driven activity bump — used by Module 7 to keep ghost-score honest."""
        from sqlalchemy import update
        self.session.execute(
            update(Job).where(Job.id == job_id).values(last_activity_at=Job.last_activity_at.op("+")("'0 seconds'::interval"))
        )
        # simpler: set to now()
        from sqlalchemy.sql import func
        self.session.execute(
            update(Job).where(Job.id == job_id).values(last_activity_at=func.now())
        )
        self.session.commit()

    # ── derived getters (replaces the old metadata-jsonb helpers) ──────────
    def required_skills(self, job: Job) -> list[dict]:
        """Returns `[{skill, min_years, mandatory}]` from job_skills rows."""
        rows = self.session.execute(
            select(JobSkill.name, JobSkill.min_experience, JobSkill.mandatory)
            .where(JobSkill.job_id == job.id)
            .order_by(JobSkill.sort_order)
        ).all()
        return [
            {"skill": r[0].lower(), "min_years": float(r[1] or 0), "mandatory": bool(r[2])}
            for r in rows
        ]

    def required_skill_names(self, job: Job) -> list[str]:
        return [s["skill"] for s in self.required_skills(job)]

    @staticmethod
    def required_years(job: Job) -> float | None:
        return float(job.experience_min_years) if job.experience_min_years is not None else None

    @staticmethod
    def notice_period_max(job: Job) -> int | None:
        """
        Live schema stores the notice as a free-text label (e.g. "30 Days").
        Best-effort parse to an int day-count; returns None if not numeric.
        """
        if not job.notice_period:
            return None
        token = job.notice_period.strip().split()[0]
        try:
            return int(token)
        except ValueError:
            return None

    @staticmethod
    def salary(job: Job) -> dict | None:
        """Returns `{min, max, currency, ctc}` if any salary info is set."""
        if (
            job.annual_ctc is None
            and job.salary_min_ctc is None
            and job.salary_max_ctc is None
        ):
            return None
        return {
            "min": float(job.salary_min_ctc) if job.salary_min_ctc is not None else None,
            "max": float(job.salary_max_ctc) if job.salary_max_ctc is not None else None,
            "ctc": float(job.annual_ctc) if job.annual_ctc is not None else None,
            "currency": job.currency,
        }
