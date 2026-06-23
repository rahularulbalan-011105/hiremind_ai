"""
Always-works predictor used when no trained XGBoost model is loaded.

Mirrors the structure of a logistic model so the response shape is identical
to the XGBoost path. "SHAP" here is just each weighted feature's contribution
to the logit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.hiring_predictor.features import FEATURE_NAMES, FeatureVector

# Weights applied to (feature_value - center) / scale, then summed into a logit.
# Scores in [0, 100] are centered at 50, scaled by 50, so the linear term lives
# in roughly [-1, 1].
_WEIGHTS: dict[str, tuple[float, float, float]] = {
    # feature: (weight, center, scale)
    "semantic_score":             (0.60, 50.0, 50.0),
    "skill_overlap_score":        (0.90, 50.0, 50.0),
    "experience_score":           (0.40, 50.0, 50.0),
    "location_score":             (0.20, 50.0, 50.0),
    "notice_period_score":        (0.20, 50.0, 50.0),
    "salary_score":               (0.30, 50.0, 50.0),
    "trust_score":                (0.50, 50.0, 50.0),
    "candidate_years":            (0.05,  5.0,  5.0),
    "required_years_gap":         (0.10,  0.0,  3.0),
    "meets_all_required_skills":  (0.80,  0.5,  0.5),
    "github_verified_skills":     (0.30,  0.0,  1.0),
}
_BIAS = -0.20  # Slight pessimistic prior — most candidates aren't hired.

assert set(_WEIGHTS.keys()) == set(FEATURE_NAMES), "rules predictor weights drifted from FEATURE_NAMES"


@dataclass(frozen=True)
class PredictResult:
    probability: float
    confidence: float
    contributions: list[tuple[str, float]]  # (feature, contribution_to_logit)


def predict_rules(fv: FeatureVector) -> PredictResult:
    contributions: list[tuple[str, float]] = []
    logit = _BIAS
    for name in FEATURE_NAMES:
        w, center, scale = _WEIGHTS[name]
        raw = fv.values[name]
        normalized = (raw - center) / scale if scale != 0 else 0.0
        c = w * normalized
        contributions.append((name, c))
        logit += c

    # Sigmoid for probability
    probability = 1.0 / (1.0 + math.exp(-logit))
    confidence = abs(probability - 0.5) * 2.0
    return PredictResult(
        probability=probability,
        confidence=confidence,
        contributions=sorted(contributions, key=lambda x: abs(x[1]), reverse=True),
    )
