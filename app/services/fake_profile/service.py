from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateSkill,
)
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.fake_profile import FakeProfileRepository
from app.schemas.fake_profile import (
    CandidateSummary,
    FakeProfileResponse,
    GitHubCheck,
    SignalBreakdown,
)
from app.services.fake_profile.github import (
    GitHubChecker,
    GitHubResult,
    extract_username_from_text,
)
from app.services.fake_profile.signals import (
    ExperienceRow,
    Finding,
    detect_duplicate_contact,
    detect_employment_gaps,
    detect_overlaps,
    detect_perfect_completeness,
    detect_timeline_inconsistency,
    risk_level_from_score,
    trust_score_from_findings,
)

log = get_logger(__name__)


class FakeProfileService:
    def __init__(self, github_checker: GitHubChecker):
        self.github = github_checker

    # ---------- public API ----------

    def score(
        self,
        session: Session,
        *,
        candidate_id: UUID,
        force_recompute: bool,
        github_username: str | None,
        skip_github: bool,
    ) -> FakeProfileResponse:
        candidate_repo = CandidateRepository(session)
        candidate = candidate_repo.get(candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {candidate_id} not found.")

        repo = FakeProfileRepository(session)
        if not force_recompute:
            cached = repo.get(candidate_id)
            if cached is not None and isinstance(cached.anomalies, dict):
                return self._cached_to_response(candidate, cached)

        # 1. Load candidate detail rows
        experiences = self._load_experiences(session, candidate_id)
        educations = self._load_educations(session, candidate_id)
        skills = self._load_skills(session, candidate_id)
        cert_count = (
            session.execute(
                select(CandidateCertification.id).where(
                    CandidateCertification.candidate_id == candidate_id
                )
            ).scalars().all().__len__()
        )
        # `candidate_languages` was dropped in the new schema; the signal still
        # accepts a language count but we always pass 0 now.
        lang_count = 0

        # 2. Internal duplicate contact lookup (other candidates with same email/phone)
        email_matches: list[str] = []
        phone_matches: list[str] = []
        if candidate.email:
            rows = session.execute(
                select(Candidate.id).where(
                    Candidate.email == candidate.email, Candidate.id != candidate_id
                )
            ).scalars().all()
            email_matches = [str(r) for r in rows]
        if candidate.phone_number:
            rows = session.execute(
                select(Candidate.id).where(
                    Candidate.phone_number == candidate.phone_number,
                    Candidate.id != candidate_id,
                )
            ).scalars().all()
            phone_matches = [str(r) for r in rows]

        # 3. Run 5 signals
        today = date.today()
        findings: list[Finding] = [
            detect_employment_gaps(experiences, today=today),
            detect_overlaps(experiences, today=today),
            detect_duplicate_contact(
                email_matches=email_matches, phone_matches=phone_matches
            ),
            detect_perfect_completeness(
                has_headline=bool(candidate.headline),
                has_location=bool(candidate.location),
                has_phone=bool(candidate.phone),
                has_certifications=cert_count > 0,
                has_languages=lang_count > 0,
                skill_count=len(skills),
            ),
            detect_timeline_inconsistency(
                earliest_education_end=_earliest_education_end(educations),
                earliest_job_start=_earliest_job_start(experiences),
            ),
        ]

        # 4. GitHub cross-check
        github_result = self._run_github_check(
            candidate.raw_text,
            override=github_username,
            claimed_skills=skills,
            skip=skip_github,
        )

        # 5. Compose
        trust_score = trust_score_from_findings(findings)
        risk_level = risk_level_from_score(trust_score)
        breakdown = [self._finding_to_breakdown(f) for f in findings]
        bullets = self._build_bullets(findings, github_result)

        # 6. Persist
        anomalies_blob = {
            "breakdown": [b.model_dump() for b in breakdown],
            "bullets": bullets,
            "github_check": github_result.__dict__,
        }
        row = repo.upsert(candidate_id, float(trust_score), risk_level, anomalies_blob)

        summary = _candidate_summary(candidate, len(skills), experiences, len(educations))
        return FakeProfileResponse(
            candidate_id=candidate_id,
            candidate=summary,
            trust_score=trust_score,
            risk_level=risk_level,
            reasoning_bullets=bullets,
            score_breakdown=breakdown,
            github_check=_github_result_to_dto(github_result),
            cached=False,
            computed_at=_aware(row.computed_at),
        )

    # ---------- internals ----------

    @staticmethod
    def _load_experiences(session: Session, candidate_id: UUID) -> list[ExperienceRow]:
        rows = session.execute(
            select(
                CandidateExperience.company,
                CandidateExperience.title,
                CandidateExperience.start_date,
                CandidateExperience.end_date,
                CandidateExperience.is_current,
            ).where(CandidateExperience.candidate_id == candidate_id)
        ).all()
        return [
            ExperienceRow(
                company=r.company,
                title=r.title,
                start_date=r.start_date,
                end_date=r.end_date,
                is_current=bool(r.is_current),
            )
            for r in rows
        ]

    @staticmethod
    def _load_educations(session: Session, candidate_id: UUID) -> list:
        rows = session.execute(
            select(CandidateEducation.start_date, CandidateEducation.end_date).where(
                CandidateEducation.candidate_id == candidate_id
            )
        ).all()
        return list(rows)

    @staticmethod
    def _load_skills(session: Session, candidate_id: UUID) -> list[str]:
        rows = session.execute(
            select(CandidateSkill.skill).where(CandidateSkill.candidate_id == candidate_id)
        ).scalars().all()
        return list(rows)

    def _run_github_check(
        self,
        raw_text: str | None,
        *,
        override: str | None,
        claimed_skills: list[str],
        skip: bool,
    ) -> GitHubResult:
        if skip:
            return GitHubResult(checked=False, warnings=["GitHub check skipped by request."])
        username = (override or "").strip() or extract_username_from_text(raw_text)
        if not username:
            return GitHubResult(
                checked=False,
                warnings=["No GitHub username found in resume; provide one in the request to check."],
            )
        return self.github.check(username, claimed_skills)

    @staticmethod
    def _finding_to_breakdown(f: Finding) -> SignalBreakdown:
        return SignalBreakdown(
            signal=f.signal,  # type: ignore[arg-type]
            fired=f.fired,
            penalty=-f.penalty if f.fired else 0,
            severity=f.severity,  # type: ignore[arg-type]
            message=f.message,
            details=f.details,
        )

    @staticmethod
    def _build_bullets(findings: list[Finding], gh: GitHubResult) -> list[str]:
        bullets: list[str] = []
        for f in findings:
            if not f.fired:
                continue
            bullets.append(f.message)
        # Always include at least one positive note if available
        positives = [f for f in findings if not f.fired]
        if positives:
            bullets.append(positives[0].message)
        # GitHub commentary
        if gh.checked and gh.username:
            if gh.error:
                bullets.append(f"GitHub check: {gh.error}")
            else:
                hit_count = len(gh.claimed_skills_found_in_repos)
                miss_count = len(gh.claimed_skills_missing_in_repos)
                if hit_count or miss_count:
                    bullets.append(
                        f"GitHub: {hit_count} claimed skill(s) confirmed in public work, "
                        f"{miss_count} not visible."
                    )
                for w in gh.warnings:
                    bullets.append(f"GitHub: {w}")
        elif not gh.checked and gh.warnings:
            bullets.append(gh.warnings[0])
        return bullets

    @staticmethod
    def _cached_to_response(candidate: Candidate, row) -> FakeProfileResponse:
        blob = row.anomalies if isinstance(row.anomalies, dict) else {}
        breakdown_data = blob.get("breakdown") or []
        breakdown = [SignalBreakdown.model_validate(b) for b in breakdown_data]
        bullets = list(blob.get("bullets") or [])
        gh_raw = blob.get("github_check") or {}
        gh = GitHubCheck(
            checked=bool(gh_raw.get("checked")),
            username=gh_raw.get("username"),
            profile_url=gh_raw.get("profile_url"),
            account_age_days=gh_raw.get("account_age_days"),
            public_repos=gh_raw.get("public_repos"),
            followers=gh_raw.get("followers"),
            top_languages=list(gh_raw.get("top_languages") or []),
            claimed_skills_found_in_repos=list(gh_raw.get("claimed_skills_found_in_repos") or []),
            claimed_skills_missing_in_repos=list(gh_raw.get("claimed_skills_missing_in_repos") or []),
            warnings=list(gh_raw.get("warnings") or []),
            error=gh_raw.get("error"),
        )
        # Quick re-derive candidate summary (cheap)
        # We don't store skill_count / experience_years in the cache; compute live.
        summary = CandidateSummary(
            full_name=candidate.full_name,
            email=candidate.email,
            phone=candidate.phone,
            headline=candidate.headline,
            location=candidate.location,
            skill_count=0,  # will be filled by caller if needed; cheap default
            experience_years=0.0,
            education_count=0,
            raw_resume_url=candidate.raw_resume_url,
        )
        return FakeProfileResponse(
            candidate_id=row.candidate_id,
            candidate=summary,
            trust_score=int(round(float(row.trust_score))),
            risk_level=row.risk_level,  # type: ignore[arg-type]
            reasoning_bullets=bullets,
            score_breakdown=breakdown,
            github_check=gh,
            cached=True,
            computed_at=_aware(row.computed_at),
        )


# ---------- module-level helpers ----------


def _earliest_job_start(experiences: list[ExperienceRow]) -> date | None:
    starts = [e.start_date for e in experiences if e.start_date is not None]
    return min(starts) if starts else None


def _earliest_education_end(educations: list) -> date | None:
    ends = [e.end_date for e in educations if getattr(e, "end_date", None) is not None]
    return min(ends) if ends else None


def _candidate_summary(
    candidate: Candidate,
    skill_count: int,
    experiences: list[ExperienceRow],
    education_count: int,
) -> CandidateSummary:
    today = date.today()
    intervals: list[tuple[date, date]] = []
    for e in experiences:
        if e.start_date is None:
            continue
        end = e.end_date or today
        if end >= e.start_date:
            intervals.append((e.start_date, end))
    intervals.sort()
    merged: list[tuple[date, date]] = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    total_days = sum((e - s).days for s, e in merged)
    years = round(total_days / 365.25, 2) if total_days else 0.0
    return CandidateSummary(
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        headline=candidate.headline,
        location=candidate.location,
        skill_count=skill_count,
        experience_years=years,
        education_count=education_count,
        raw_resume_url=candidate.raw_resume_url,
    )


def _github_result_to_dto(r: GitHubResult) -> GitHubCheck:
    return GitHubCheck(
        checked=r.checked,
        username=r.username,
        profile_url=r.profile_url,
        account_age_days=r.account_age_days,
        public_repos=r.public_repos,
        followers=r.followers,
        top_languages=list(r.top_languages),
        claimed_skills_found_in_repos=list(r.claimed_skills_found_in_repos),
        claimed_skills_missing_in_repos=list(r.claimed_skills_missing_in_repos),
        warnings=list(r.warnings),
        error=r.error,
    )


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
