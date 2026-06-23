"""
Pure functions for the duplicate-job signals.

Three independent signals (fuzzy title, embedding similarity, skill overlap) get
combined into a single verdict by `classify`. Same-company is a multiplier:
two jobs from the same company are held to a lower bar.
"""

from __future__ import annotations

from typing import Literal

from rapidfuzz import fuzz

Verdict = Literal["hard", "likely", "similar"]


def title_similarity(a: str, b: str) -> float:
    """RapidFuzz token-set ratio — handles word reordering. Returns [0, 1]."""
    if not a or not b:
        return 0.0
    # token_set_ratio is robust to extra/missing words; ratio is in [0, 100]
    return fuzz.token_set_ratio(a, b) / 100.0


def skill_overlap(a: list[str], b: list[str]) -> tuple[float, list[str]]:
    """Jaccard of skill name sets. Returns (overlap_ratio, intersection_list)."""
    set_a = {s.strip().lower() for s in a if s and s.strip()}
    set_b = {s.strip().lower() for s in b if s and s.strip()}
    if not set_a or not set_b:
        return 0.0, []
    intersection = sorted(set_a & set_b)
    union = set_a | set_b
    if not union:
        return 0.0, []
    return len(intersection) / len(union), intersection


def normalize_company(c: str | None) -> str | None:
    if not c:
        return None
    return c.strip().lower() or None


def classify(
    *,
    title_sim: float,
    embedding_sim: float,
    same_company: bool,
) -> Verdict | None:
    """
    Returns the verdict label or None if the pair shouldn't be reported at all.
    Thresholds explained in the module docstring above; lowered slightly when
    the two jobs are from the same company.
    """
    # Same company → almost certainly the same posting if either dimension is strong
    if same_company:
        if title_sim >= 0.90 or embedding_sim >= 0.97:
            return "hard"
        if title_sim >= 0.80 and embedding_sim >= 0.88:
            return "likely"
        if embedding_sim >= 0.85 or title_sim >= 0.75:
            return "similar"
        return None

    # Different (or unknown) company — need both signals to be strong
    if title_sim >= 0.92 and embedding_sim >= 0.95:
        return "hard"
    if title_sim >= 0.85 and embedding_sim >= 0.92:
        return "likely"
    if embedding_sim >= 0.90 or title_sim >= 0.85:
        return "similar"
    return None
