"""
Synthetic hiring-outcome generator.

Walks the cross-product of (candidates with embeddings) × (jobs with embeddings),
computes match features for each pair, then probabilistically assigns
{hired, rejected, withdrawn, no_show} based on a "ground-truth" rule that
matches the real-world intuition the rules-based predictor encodes.

Adds noise so the labels aren't perfectly separable — gives XGBoost something
to actually learn.

Usage:
    .\\.venv\\Scripts\\Activate.ps1
    python -m scripts.seed_hiring_outcomes --target 200
"""

from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import Candidate, Job, JobEmbedding, ResumeEmbedding
from app.db.session import get_session, init_engine
from app.llm import get_llm_client
from app.services.hiring_predictor.features import FeatureExtractor

log = get_logger("scripts.seed_hiring_outcomes")

# Coefficients for the synthetic "true" hiring probability — chosen to be DIFFERENT
# from the rules predictor weights so the trained XGBoost has something distinct
# to learn (otherwise it would just memorize the rules).
_TRUE_WEIGHTS = {
    "semantic_score":             0.55,
    "skill_overlap_score":        1.10,
    "experience_score":           0.30,
    "location_score":             0.15,
    "notice_period_score":        0.25,
    "salary_score":               0.35,
    "trust_score":                0.60,
    "candidate_years":            0.08,
    "required_years_gap":         0.12,
    "meets_all_required_skills":  1.00,
    "github_verified_skills":     0.40,
}
_TRUE_BIAS = -0.35


def _true_probability(values: dict[str, float]) -> float:
    logit = _TRUE_BIAS
    for name, w in _TRUE_WEIGHTS.items():
        raw = values.get(name, 0.0)
        if name.endswith("_score"):
            normalized = (raw - 50.0) / 50.0
        elif name == "candidate_years":
            normalized = (raw - 5.0) / 5.0
        elif name == "required_years_gap":
            normalized = raw / 3.0
        else:  # binary
            normalized = raw - 0.5
        logit += w * normalized
    return 1.0 / (1.0 + math.exp(-logit))


def _sample_outcome(prob: float, rng: random.Random) -> str:
    """Given P(hire), sample one of the 4 outcome categories with realistic priors."""
    # Add noise so the boundary isn't perfectly sharp
    noisy = max(0.0, min(1.0, prob + rng.gauss(0, 0.08)))
    r = rng.random()
    if r < noisy:
        return "hired"
    # The remaining 1 - noisy is split across rejected/withdrawn/no_show
    # Rejected dominates; withdrawn/no_show are tail
    sub = rng.random()
    if sub < 0.75:
        return "rejected"
    if sub < 0.92:
        return "withdrawn"
    return "no_show"


def main() -> None:
    configure_logging("INFO")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target", type=int, default=200,
        help="Approximate target number of outcome rows to insert."
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Truncate hiring_outcomes before inserting new ones.",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility.",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    settings = get_settings()
    init_engine(settings)
    llm = get_llm_client(settings)
    extractor = FeatureExtractor(llm=llm)

    session_iter = get_session()
    session = next(session_iter)
    try:
        if args.reset:
            session.execute(text("DELETE FROM hiring_outcomes"))
            session.commit()
            log.info("hiring_outcomes_cleared")

        # All candidates with an embedding × all jobs with an embedding
        candidate_ids: list[UUID] = list(
            session.execute(
                select(Candidate.id)
                .join(ResumeEmbedding, ResumeEmbedding.candidate_id == Candidate.id)
            ).scalars().all()
        )
        job_ids: list[UUID] = list(
            session.execute(
                select(Job.id).join(JobEmbedding, JobEmbedding.job_id == Job.id)
            ).scalars().all()
        )
        log.info(
            "candidates_jobs_loaded",
            candidates=len(candidate_ids),
            jobs=len(job_ids),
            target=args.target,
        )
        if not candidate_ids or not job_ids:
            log.error(
                "no_data",
                msg="Need at least one candidate and one job with embeddings. "
                    "Parse a resume and create a job first.",
            )
            return

        pairs = [(c, j) for c in candidate_ids for j in job_ids]
        rng.shuffle(pairs)
        pairs = pairs[: args.target]

        now = datetime.now(timezone.utc)
        inserted = 0
        skipped = 0
        for cand_id, job_id in pairs:
            try:
                fv = extractor.extract(session, candidate_id=cand_id, job_id=job_id)
            except Exception as exc:
                log.warning("feature_extraction_failed", error=str(exc)[:200])
                skipped += 1
                continue
            p = _true_probability(fv.values)
            outcome = _sample_outcome(p, rng)
            decided_at = now - timedelta(days=rng.randint(7, 180))

            try:
                session.execute(
                    text(
                        """
                        INSERT INTO hiring_outcomes
                            (candidate_id, job_id, outcome, decided_at)
                        VALUES (:cid, :jid, :outcome, :decided)
                        ON CONFLICT (candidate_id, job_id) DO UPDATE
                          SET outcome = EXCLUDED.outcome, decided_at = EXCLUDED.decided_at
                        """
                    ),
                    {"cid": cand_id, "jid": job_id, "outcome": outcome, "decided": decided_at},
                )
                inserted += 1
            except Exception as exc:
                log.warning("insert_failed", error=str(exc)[:200])
                skipped += 1

        session.commit()
        log.info("seed_done", inserted=inserted, skipped=skipped)
    finally:
        try:
            next(session_iter)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
