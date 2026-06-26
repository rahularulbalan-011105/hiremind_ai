"""
Candidate repository — operates on the `hiremind_candidate` Postgres DB.

Field-name mapping vs the old standalone schema (services should be aware):
  Candidate.phone        → phone_number
  Candidate.location     → current_location
  Candidate.raw_resume_url → resume_file_key  (S3-style key, no longer a URL)
  Candidate.raw_text     → raw_resume_text
  CandidateExperience.company / .title / .is_current / .description
      → company_name / job_title / currently_working / (no equivalent)
  CandidateEducation.field → specialization
  CandidateSkill.skill / .years → joined with `skills` master / experience_years
  CandidateCertification.name / .issuer / .issued_date / .expires_date
      → certification_name / issuing_institution / passed_year / valid_till
  Candidate.preferences (jsonb) → CandidatePreference rows (preference_type / preference_value)

The repo presents the same public surface where possible — see `get_preferences`
which now folds the typed rows back into a dict shape.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidatePreference,
    CandidateSkill,
    Skill,
)
from app.schemas.resume_parser import ParsedResume


class CandidateRepository:
    def __init__(self, session: Session):
        self.session = session

    # ── reads ──────────────────────────────────────────────────────────────
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
            select(Skill.name)
            .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
            .where(CandidateSkill.candidate_id == candidate_id)
        ).scalars().all()
        return list(rows)

    def get_skills_with_years(
        self, candidate_id: UUID
    ) -> list[tuple[str, float | None]]:
        """Returns `[(skill_name, years), …]` — needed by Match Engine's per-skill min_years check."""
        rows = self.session.execute(
            select(Skill.name, CandidateSkill.experience_years)
            .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
            .where(CandidateSkill.candidate_id == candidate_id)
        ).all()
        return [(r[0], float(r[1]) if r[1] is not None else None) for r in rows]

    def get_contact_info_many(
        self, candidate_ids: list[UUID]
    ) -> dict[UUID, tuple[str | None, str | None, str | None]]:
        """Return {id: (full_name, email, phone_number)} for a batch."""
        if not candidate_ids:
            return {}
        rows = self.session.execute(
            select(
                Candidate.id, Candidate.full_name, Candidate.email, Candidate.phone_number
            ).where(Candidate.id.in_(candidate_ids))
        ).all()
        return {r.id: (r.full_name, r.email, r.phone_number) for r in rows}

    def get_education_count(self, candidate_id: UUID) -> int:
        return self.session.execute(
            select(CandidateEducation.id).where(CandidateEducation.candidate_id == candidate_id)
        ).scalars().all().__len__()

    def get_preferences(self, candidate_id: UUID) -> dict:
        """
        Returns a flat dict shape compatible with the old jsonb-based code:

            {
              "notice_period": "...",
              "expected_salary": "...",
              "preferred_location": "...",
              "open_to_relocate": bool,
              "additional_preferences": "...",
              "roles":            ["Team Lead", "Software Engineer"],
              "employment_types": ["FULL_TIME", "REMOTE"],
              "benefits":         ["Work From Home"],
              "skill_years":      {"java": 5.0, "spring boot": 3.0, ...},  # not stored in candidate DB
            }
        """
        candidate = self.session.get(Candidate, candidate_id)
        if candidate is None:
            return {}

        # Scalar columns
        out: dict = {
            "notice_period": candidate.notice_period,
            "expected_salary": candidate.expected_salary,
            "salary_type": candidate.salary_type,
            "preferred_location": candidate.preferred_location,
            "open_to_relocate": candidate.open_to_relocate,
            "additional_preferences": candidate.additional_preferences,
        }

        # Typed rows from candidate_preferences → buckets
        typed = self.session.execute(
            select(CandidatePreference.preference_type, CandidatePreference.preference_value).where(
                CandidatePreference.candidate_id == candidate_id
            )
        ).all()
        buckets: dict[str, list[str]] = {}
        for ptype, pval in typed:
            buckets.setdefault(ptype.lower() + "s", []).append(pval)
        out.update(buckets)

        # skill_years is reconstructed from candidate_skills
        out["skill_years"] = {
            name.lower(): years for name, years in self.get_skills_with_years(candidate_id)
            if years is not None
        }

        return out

    def update_preferences(self, candidate_id: UUID, preferences: dict) -> None:
        """Mirrors the old API — splits the dict back into scalar cols + typed rows."""
        candidate = self.session.get(Candidate, candidate_id)
        if candidate is None:
            return
        for col in (
            "notice_period",
            "expected_salary",
            "salary_type",
            "preferred_location",
            "additional_preferences",
        ):
            if col in preferences:
                setattr(candidate, col, preferences[col])
        if "open_to_relocate" in preferences:
            candidate.open_to_relocate = bool(preferences["open_to_relocate"])

        # Typed buckets — wipe and re-insert.
        self.session.query(CandidatePreference).filter(
            CandidatePreference.candidate_id == candidate_id
        ).delete()
        for bucket_key, ptype in (
            ("roles", "ROLE"),
            ("employment_types", "EMPLOYMENT_TYPE"),
            ("benefits", "BENEFIT"),
        ):
            for value in preferences.get(bucket_key, []) or []:
                self.session.add(
                    CandidatePreference(
                        candidate_id=candidate_id,
                        preference_type=ptype,
                        preference_value=str(value),
                    )
                )
        self.session.commit()

    def get_preferences_many(self, candidate_ids: list[UUID]) -> dict[UUID, dict]:
        if not candidate_ids:
            return {}
        return {cid: self.get_preferences(cid) for cid in candidate_ids}

    def get_location_many(self, candidate_ids: list[UUID]) -> dict[UUID, str | None]:
        if not candidate_ids:
            return {}
        rows = self.session.execute(
            select(Candidate.id, Candidate.current_location).where(
                Candidate.id.in_(candidate_ids)
            )
        ).all()
        return {r.id: r.current_location for r in rows}

    def years_of_experience(self, candidate_id: UUID) -> float:
        """
        Sum non-overlapping experience intervals. Open-ended ranges are treated
        as ending today. Returns 0.0 when no data is present.

        Note: candidate.total_experience_years is also stored, but we recompute
        from the raw intervals because the column can drift if children change.
        """
        rows = self.session.execute(
            select(CandidateExperience.start_date, CandidateExperience.end_date).where(
                CandidateExperience.candidate_id == candidate_id
            )
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
            # Fall back to the stored scalar if intervals are empty.
            candidate = self.session.get(Candidate, candidate_id)
            if candidate is not None and candidate.total_experience_years is not None:
                return float(candidate.total_experience_years)
            return 0.0

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

    # ── writes ─────────────────────────────────────────────────────────────
    def create_from_parsed(
        self,
        parsed: ParsedResume,
        *,
        user_id: UUID | None = None,
        raw_resume_url: str | None = None,
        raw_text: str | None = None,
    ) -> Candidate:
        """
        Upsert candidate + replace children based on a freshly-parsed resume.

        In production, `user_id` should be the auth user from users-service.
        For the dev test harness we generate a fresh UUID — the resulting row
        is an orphan from the users-service POV but unblocks local testing.
        """
        from uuid import uuid4

        candidate: Candidate | None = None
        if parsed.email:
            candidate = self.find_by_email(parsed.email)

        if candidate is None:
            candidate = Candidate(
                user_id=user_id or uuid4(),
                full_name=parsed.full_name,
                email=parsed.email,
                phone_number=parsed.phone,
                headline=parsed.headline,
                current_location=parsed.location,
                resume_file_key=raw_resume_url,
                raw_resume_text=raw_text,
            )
            self.session.add(candidate)
            self.session.flush()
        else:
            if parsed.full_name:
                candidate.full_name = parsed.full_name
            candidate.phone_number = parsed.phone or candidate.phone_number
            candidate.headline = parsed.headline or candidate.headline
            candidate.current_location = parsed.location or candidate.current_location
            candidate.resume_file_key = raw_resume_url or candidate.resume_file_key
            candidate.raw_resume_text = raw_text or candidate.raw_resume_text
            self._clear_children(candidate.id)
            self.session.flush()

        self._add_children(candidate.id, parsed)
        self.session.commit()
        self.session.refresh(candidate)
        return candidate

    def get_with_children(
        self, candidate_id: UUID
    ) -> tuple[
        Candidate,
        list[CandidateExperience],
        list[CandidateEducation],
        list[CandidateSkill],
        list[CandidateCertification],
        list,  # languages — no longer supported; always returns []
    ] | None:
        candidate = self.session.get(Candidate, candidate_id)
        if candidate is None:
            return None

        def _by_candidate(model):
            return list(
                self.session.execute(
                    select(model).where(model.candidate_id == candidate_id)
                ).scalars().all()
            )

        return (
            candidate,
            _by_candidate(CandidateExperience),
            _by_candidate(CandidateEducation),
            _by_candidate(CandidateSkill),
            _by_candidate(CandidateCertification),
            [],
        )

    # ── internal ───────────────────────────────────────────────────────────
    def _clear_children(self, candidate_id: UUID) -> None:
        for model in (
            CandidateExperience,
            CandidateEducation,
            CandidateSkill,
            CandidateCertification,
        ):
            self.session.query(model).filter(model.candidate_id == candidate_id).delete()

    def _ensure_skill(self, name: str) -> UUID:
        """Find-or-create on the master `skills` table. Returns the skill_id."""
        normalized = name.strip()
        if not normalized:
            raise ValueError("empty skill name")
        existing = self.session.execute(
            select(Skill.id).where(Skill.name.ilike(normalized))
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        skill = Skill(name=normalized)
        self.session.add(skill)
        self.session.flush()
        return skill.id

    def _add_children(self, candidate_id: UUID, parsed: ParsedResume) -> None:
        for exp in parsed.experience:
            self.session.add(
                CandidateExperience(
                    candidate_id=candidate_id,
                    company_name=exp.company,
                    job_title=exp.title or "",
                    employment_type="FULL_TIME",  # default; the parser doesn't extract this
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    currently_working=exp.is_current,
                )
            )
        for edu in parsed.education:
            self.session.add(
                CandidateEducation(
                    candidate_id=candidate_id,
                    institution=edu.institution,
                    degree=edu.degree or "",
                    specialization=edu.field,
                    year_of_passing=(
                        str(edu.end_date.year) if edu.end_date else None
                    ),
                    grade=edu.grade,
                )
            )

        seen_skills: set[str] = set()
        for skill in parsed.skills:
            normalized = skill.strip().lower()
            if not normalized or normalized in seen_skills:
                continue
            seen_skills.add(normalized)
            skill_id = self._ensure_skill(normalized)
            # Duplicate-skill guard (the unique key is (candidate_id, skill_id)):
            already = self.session.execute(
                select(CandidateSkill.id).where(
                    CandidateSkill.candidate_id == candidate_id,
                    CandidateSkill.skill_id == skill_id,
                )
            ).scalar_one_or_none()
            if already is not None:
                continue
            self.session.add(
                CandidateSkill(
                    candidate_id=candidate_id,
                    skill_id=skill_id,
                    proficiency_level="INTERMEDIATE",  # default; parser doesn't infer
                )
            )

        for cert in parsed.certifications:
            self.session.add(
                CandidateCertification(
                    candidate_id=candidate_id,
                    certification_name=cert.name,
                    issuing_institution=cert.issuer or "",
                    passed_year=(cert.issued_date.year if cert.issued_date else None),
                    valid_till=cert.expires_date,
                )
            )
