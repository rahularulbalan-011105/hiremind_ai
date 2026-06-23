from __future__ import annotations

from dataclasses import dataclass, field

# When the JD specifies no requirement on a dimension, that sub-score is neutral.
_NEUTRAL = 50.0
# Above this multiple of required years, no extra credit.
_EXP_CAP = 1.2

# Minimal location alias table — extend as needed.
_LOCATION_ALIASES: dict[str, str] = {
    "bengaluru": "bengaluru",
    "bangalore": "bengaluru",
    "blr": "bengaluru",
    "mumbai": "mumbai",
    "bombay": "mumbai",
    "delhi": "delhi",
    "new delhi": "delhi",
    "ncr": "delhi",
    "hyderabad": "hyderabad",
    "hyd": "hyderabad",
    "pune": "pune",
    "chennai": "chennai",
    "madras": "chennai",
    "kolkata": "kolkata",
    "calcutta": "kolkata",
    "gurgaon": "delhi",
    "gurugram": "delhi",
    "noida": "delhi",
}
_REMOTE_TOKENS = {"remote", "anywhere", "wfh", "work from home"}


@dataclass(frozen=True)
class SubScores:
    semantic: float
    skill_overlap: float
    experience: float
    location: float
    notice_period: float
    salary: float
    matched_skills: list[str]
    missing_skills: list[str]
    candidate_years: float
    required_years: float | None


def semantic_score(cosine_similarity: float) -> float:
    return max(0.0, min(100.0, ((cosine_similarity + 1.0) / 2.0) * 100.0))


def skill_overlap_score(
    required: list[dict],
    candidate_skills: list[str],
    *,
    candidate_skill_years: dict[str, float],
    candidate_total_years: float,
) -> tuple[float, list[str], list[str]]:
    """
    `required` is a list of {skill, min_years}.
    A skill is matched if the candidate lists it AND meets min_years.
    Candidate's years for a skill: explicit override OR fall back to total years.
    """
    if not required:
        return _NEUTRAL, [], []

    have_set = {s.strip().lower() for s in candidate_skills if s and s.strip()}
    matched: list[str] = []
    missing: list[str] = []
    for entry in required:
        skill = str(entry.get("skill", "")).strip().lower()
        if not skill:
            continue
        min_years = float(entry.get("min_years") or 0)
        if skill not in have_set:
            missing.append(skill)
            continue
        years = candidate_skill_years.get(skill, candidate_total_years)
        if years >= min_years:
            matched.append(skill)
        else:
            missing.append(skill)

    total = len(matched) + len(missing)
    if total == 0:
        return _NEUTRAL, [], []
    pct = (len(matched) / total) * 100.0
    return pct, matched, missing


def experience_score(candidate_years: float, required_years: float | None) -> float:
    if required_years is None or required_years <= 0:
        return _NEUTRAL
    ratio = candidate_years / required_years
    capped = min(ratio, _EXP_CAP)
    return (capped / _EXP_CAP) * 100.0


# ---------- NEW DIMENSIONS ----------


def _norm_location(s: str | None) -> str | None:
    if not s:
        return None
    key = s.strip().lower()
    if not key:
        return None
    if key in _REMOTE_TOKENS:
        return "remote"
    # Strip everything after / or , (e.g. "Bengaluru / Remote" → "Bengaluru")
    for sep in ("/", ","):
        if sep in key:
            key = key.split(sep, 1)[0].strip()
    return _LOCATION_ALIASES.get(key, key)


def location_score(
    job_location: str | None,
    candidate_location: str | None,
    preferred_locations: list[str],
    open_to_remote: bool,
) -> float:
    job_norm = _norm_location(job_location)
    cand_norm = _norm_location(candidate_location)

    if job_norm is None:
        return _NEUTRAL

    if job_norm == "remote":
        return 100.0 if open_to_remote else 60.0

    # Candidate's preferred locations win if set
    prefs_norm = [n for n in (_norm_location(p) for p in preferred_locations) if n]
    if prefs_norm:
        if job_norm in prefs_norm:
            return 100.0
        if "remote" in prefs_norm and job_norm == "remote":
            return 100.0
        # No overlap with preferences — major penalty
        return 20.0

    # Fall back to comparing the candidate's current location
    if cand_norm is None:
        return _NEUTRAL
    if cand_norm == job_norm:
        return 100.0
    return 20.0


def notice_period_score(
    candidate_notice_days: int | None, job_notice_max: int | None
) -> float:
    if job_notice_max is None or candidate_notice_days is None:
        return _NEUTRAL
    if candidate_notice_days <= job_notice_max:
        return 100.0
    # Scale down by how far over: 50% over → 50, 100%+ over → 0
    over_ratio = (candidate_notice_days - job_notice_max) / max(job_notice_max, 1)
    return max(0.0, 100.0 - over_ratio * 100.0)


def salary_score(candidate_expected: dict | None, job_salary: dict | None) -> float:
    """
    Overlap rule:
      - candidate's range overlaps JD's range → 100
      - candidate expects above JD max → scales down
      - candidate expects below JD min → 100 (they're cheaper than budget)
    Currency mismatch falls back to neutral.
    """
    if not job_salary or not candidate_expected:
        return _NEUTRAL
    if (candidate_expected.get("currency") or "INR") != (job_salary.get("currency") or "INR"):
        return _NEUTRAL

    c_min = float(candidate_expected.get("min") or 0)
    c_max = float(candidate_expected.get("max") or c_min)
    j_min = float(job_salary.get("min") or 0)
    j_max = float(job_salary.get("max") or j_min)
    if c_max <= 0 or j_max <= 0:
        return _NEUTRAL

    # Overlap?
    if c_min <= j_max and c_max >= j_min:
        return 100.0
    # Candidate is cheaper than the budget — great for the employer
    if c_max < j_min:
        return 100.0
    # Candidate's min exceeds JD max — scale down
    over = c_min - j_max
    over_ratio = over / max(j_max, 1.0)
    return max(0.0, 100.0 - over_ratio * 100.0)


# ---------- Composition ----------


def compute_subscores(
    *,
    cosine_similarity: float,
    required_skills: list[dict],
    candidate_skills: list[str],
    candidate_skill_years: dict[str, float],
    candidate_years: float,
    required_years: float | None,
    job_location: str | None,
    candidate_location: str | None,
    preferred_locations: list[str],
    open_to_remote: bool,
    candidate_notice_days: int | None,
    job_notice_max: int | None,
    candidate_expected_salary: dict | None,
    job_salary: dict | None,
) -> SubScores:
    sem = semantic_score(cosine_similarity)
    skill, matched, missing = skill_overlap_score(
        required_skills,
        candidate_skills,
        candidate_skill_years=candidate_skill_years,
        candidate_total_years=candidate_years,
    )
    exp = experience_score(candidate_years, required_years)
    loc = location_score(job_location, candidate_location, preferred_locations, open_to_remote)
    notice = notice_period_score(candidate_notice_days, job_notice_max)
    sal = salary_score(candidate_expected_salary, job_salary)
    return SubScores(
        semantic=round(sem, 2),
        skill_overlap=round(skill, 2),
        experience=round(exp, 2),
        location=round(loc, 2),
        notice_period=round(notice, 2),
        salary=round(sal, 2),
        matched_skills=matched,
        missing_skills=missing,
        candidate_years=candidate_years,
        required_years=required_years,
    )


def composite_score(
    sub: SubScores,
    *,
    w_sem: float,
    w_skill: float,
    w_exp: float,
    w_loc: float,
    w_notice: float,
    w_sal: float,
) -> int:
    total_w = w_sem + w_skill + w_exp + w_loc + w_notice + w_sal
    if total_w <= 0:
        return 0
    score = (
        sub.semantic * (w_sem / total_w)
        + sub.skill_overlap * (w_skill / total_w)
        + sub.experience * (w_exp / total_w)
        + sub.location * (w_loc / total_w)
        + sub.notice_period * (w_notice / total_w)
        + sub.salary * (w_sal / total_w)
    )
    return int(round(max(0.0, min(100.0, score))))


def rule_based_bullets(sub: SubScores, job_title: str) -> list[str]:
    bullets: list[str] = []

    if sub.matched_skills:
        shown = ", ".join(sub.matched_skills[:6])
        bullets.append(f"Matches {len(sub.matched_skills)} required skills: {shown}.")
    if sub.missing_skills:
        shown = ", ".join(sub.missing_skills[:6])
        bullets.append(f"Missing {len(sub.missing_skills)} required skills (or below required years): {shown}.")

    if sub.required_years is not None:
        if sub.candidate_years >= sub.required_years:
            bullets.append(
                f"{sub.candidate_years:.1f} years of experience meets the {sub.required_years:.0f}+ year requirement."
            )
        else:
            gap = sub.required_years - sub.candidate_years
            bullets.append(
                f"Experience gap of ~{gap:.1f} years vs. the {sub.required_years:.0f}+ year requirement."
            )

    if sub.semantic >= 70:
        bullets.append(f"Strong semantic alignment with the {job_title} role.")
    elif sub.semantic <= 30:
        bullets.append(f"Weak semantic alignment with the {job_title} role.")

    if sub.location >= 90:
        bullets.append("Location matches.")
    elif sub.location <= 30:
        bullets.append("Location mismatch with the JD.")

    if sub.notice_period >= 90:
        bullets.append("Notice period within the JD's acceptable window.")
    elif sub.notice_period <= 30:
        bullets.append("Notice period substantially exceeds what the JD accepts.")

    if sub.salary >= 90:
        bullets.append("Salary expectations align with the JD budget.")
    elif sub.salary <= 30:
        bullets.append("Salary expectations significantly above the JD budget.")

    if not bullets:
        bullets.append("Insufficient data on the JD to produce detailed reasoning.")
    return bullets
