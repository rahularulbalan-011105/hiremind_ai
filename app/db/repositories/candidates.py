from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateSkill,
)
from app.schemas.resume_parser import ParsedResume


class CandidateRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, candidate_id: UUID) -> Candidate | None:
        return self.session.get(Candidate, candidate_id)

    def get_many(self, ids: list[UUID]) -> dict[UUID, Candidate]:
        if not ids:
            return {}
        rows = self.session.execute(select(Candidate).where(Candidate.id.in_(ids))).scalars().all()
        return {row.id: row for row in rows}

    def exists(self, candidate_id: UUID) -> bool:
        return self.session.get(Candidate, candidate_id) is not None

    def find_by_email(self, email: str) -> Candidate | None:
        return self.session.execute(
            select(Candidate).where(Candidate.email == email)
        ).scalar_one_or_none()

    def get_skills(self, candidate_id: UUID) -> list[str]:
        rows = self.session.execute(
            select(CandidateSkill.skill).where(CandidateSkill.candidate_id == candidate_id)
        ).scalars().all()
        return list(rows)

    def get_contact_info_many(
        self, candidate_ids: list[UUID]
    ) -> dict[UUID, tuple[str, str | None, str | None]]:
        """Return {id: (full_name, email, phone)} for a batch."""
        if not candidate_ids:
            return {}
        rows = self.session.execute(
            select(Candidate.id, Candidate.full_name, Candidate.email, Candidate.phone).where(
                Candidate.id.in_(candidate_ids)
            )
        ).all()
        return {r.id: (r.full_name, r.email, r.phone) for r in rows}

    def get_education_count(self, candidate_id: UUID) -> int:
        return self.session.execute(
            select(CandidateEducation.id).where(CandidateEducation.candidate_id == candidate_id)
        ).scalars().all().__len__()

    def get_preferences(self, candidate_id: UUID) -> dict:
        candidate = self.session.get(Candidate, candidate_id)
        if candidate is None:
            return {}
        return dict(candidate.preferences or {})

    def update_preferences(self, candidate_id: UUID, preferences: dict) -> None:
        candidate = self.session.get(Candidate, candidate_id)
        if candidate is None:
            return
        candidate.preferences = preferences
        self.session.commit()

    def get_preferences_many(self, candidate_ids: list[UUID]) -> dict[UUID, dict]:
        if not candidate_ids:
            return {}
        rows = self.session.execute(
            select(Candidate.id, Candidate.preferences).where(Candidate.id.in_(candidate_ids))
        ).all()
        return {r.id: dict(r.preferences or {}) for r in rows}

    def get_location_many(self, candidate_ids: list[UUID]) -> dict[UUID, str | None]:
        if not candidate_ids:
            return {}
        rows = self.session.execute(
            select(Candidate.id, Candidate.location).where(Candidate.id.in_(candidate_ids))
        ).all()
        return {r.id: r.location for r in rows}

    def years_of_experience(self, candidate_id: UUID) -> float:
        """
        Sum non-overlapping experience intervals. Open-ended (`end_date IS NULL`)
        ranges are treated as ending today. Returns 0.0 when no data is present.
        """
        rows = self.session.execute(
            select(CandidateExperience.start_date, CandidateExperience.end_date)
            .where(CandidateExperience.candidate_id == candidate_id)
        ).all()

        today = date.today()
        intervals: list[tuple[date, date]] = []
        for start, end in rows:
            if start is None:
                continue
            real_end = end or today
            if real_end < start:
                continue
            intervals.append((start, real_end))

        if not intervals:
            return 0.0

        # Merge overlapping intervals so concurrent jobs don't double-count.
        intervals.sort()
        merged: list[tuple[date, date]] = [intervals[0]]
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))

        total_days = sum((e - s).days for s, e in merged)
        return round(total_days / 365.25, 2)

    def create_from_parsed(
        self, parsed: ParsedResume, *, raw_resume_url: str | None, raw_text: str | None
    ) -> Candidate:
        """
        Insert a candidate and all children. If a candidate with the same email
        already exists, update the top-level row and replace its children.
        """
        candidate: Candidate | None = None
        if parsed.email:
            candidate = self.find_by_email(parsed.email)

        if candidate is None:
            candidate = Candidate(
                full_name=parsed.full_name,
                email=parsed.email,
                phone=parsed.phone,
                headline=parsed.headline,
                location=parsed.location,
                raw_resume_url=raw_resume_url,
                raw_text=raw_text,
                source="resume_upload",
            )
            self.session.add(candidate)
            self.session.flush()
        else:
            candidate.full_name = parsed.full_name
            candidate.phone = parsed.phone or candidate.phone
            candidate.headline = parsed.headline or candidate.headline
            candidate.location = parsed.location or candidate.location
            candidate.raw_resume_url = raw_resume_url or candidate.raw_resume_url
            candidate.raw_text = raw_text or candidate.raw_text
            self._clear_children(candidate.id)
            self.session.flush()

        self._add_children(candidate.id, parsed)
        self.session.commit()
        self.session.refresh(candidate)
        return candidate

    def get_with_children(self, candidate_id: UUID) -> tuple[
        Candidate,
        list[CandidateExperience],
        list[CandidateEducation],
        list[CandidateSkill],
        list[CandidateCertification],
        list[CandidateLanguage],
    ] | None:
        candidate = self.session.get(Candidate, candidate_id)
        if candidate is None:
            return None

        def _by_candidate(model):
            return (
                self.session.execute(select(model).where(model.candidate_id == candidate_id))
                .scalars()
                .all()
            )

        return (
            candidate,
            list(_by_candidate(CandidateExperience)),
            list(_by_candidate(CandidateEducation)),
            list(_by_candidate(CandidateSkill)),
            list(_by_candidate(CandidateCertification)),
            list(_by_candidate(CandidateLanguage)),
        )

    # ---------- internal ----------

    def _clear_children(self, candidate_id: UUID) -> None:
        for model in (
            CandidateExperience,
            CandidateEducation,
            CandidateSkill,
            CandidateCertification,
            CandidateLanguage,
        ):
            self.session.query(model).filter(model.candidate_id == candidate_id).delete()

    def _add_children(self, candidate_id: UUID, parsed: ParsedResume) -> None:
        for exp in parsed.experience:
            self.session.add(
                CandidateExperience(
                    candidate_id=candidate_id,
                    company=exp.company,
                    title=exp.title,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    is_current=exp.is_current,
                    description=exp.description,
                )
            )
        for edu in parsed.education:
            self.session.add(
                CandidateEducation(
                    candidate_id=candidate_id,
                    institution=edu.institution,
                    degree=edu.degree,
                    field=edu.field,
                    start_date=edu.start_date,
                    end_date=edu.end_date,
                    grade=edu.grade,
                )
            )
        seen_skills: set[str] = set()
        for skill in parsed.skills:
            normalized = skill.strip().lower()
            if not normalized or normalized in seen_skills:
                continue
            seen_skills.add(normalized)
            self.session.add(CandidateSkill(candidate_id=candidate_id, skill=normalized))
        for cert in parsed.certifications:
            self.session.add(
                CandidateCertification(
                    candidate_id=candidate_id,
                    name=cert.name,
                    issuer=cert.issuer,
                    issued_date=cert.issued_date,
                    expires_date=cert.expires_date,
                )
            )
        seen_langs: set[str] = set()
        for lang in parsed.languages:
            key = lang.language.strip().lower()
            if not key or key in seen_langs:
                continue
            seen_langs.add(key)
            self.session.add(
                CandidateLanguage(
                    candidate_id=candidate_id,
                    language=lang.language,
                    proficiency=lang.proficiency,
                )
            )
