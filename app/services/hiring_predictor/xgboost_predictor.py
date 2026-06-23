"""
XGBoost-backed predictor. Loads a model from the registry and produces real
SHAP explanations via the booster's `pred_contribs` API (which is what `shap`
uses under the hood — but without the heavyweight `shap` dependency at
inference time).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.logging import get_logger
from app.services.hiring_predictor.features import FEATURE_NAMES, FeatureVector
from app.services.hiring_predictor.registry import ModelArtifacts

log = get_logger(__name__)


@dataclass(frozen=True)
class PredictResult:
    probability: float
    confidence: float
    contributions: list[tuple[str, float]]


class XGBoostPredictor:
    def __init__(self, artifacts: ModelArtifacts):
        try:
            import xgboost as xgb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("xgboost is required to load this predictor") from exc

        self.version = artifacts.version
        self.metadata = artifacts.metadata
        self.booster = xgb.Booster()
        self.booster.load_model(str(artifacts.model_path))

        # Validate feature ordering matches what we train against
        stored = list(self.metadata.get("feature_names") or [])
        if stored != list(FEATURE_NAMES):
            log.warning(
                "xgboost_feature_mismatch",
                version=self.version,
                stored=stored,
                expected=list(FEATURE_NAMES),
            )

    def predict(self, fv: FeatureVector) -> PredictResult:
        import xgboost as xgb

        x = fv.as_array().reshape(1, -1)
        dmat = xgb.DMatrix(x, feature_names=list(FEATURE_NAMES))

        # Probability (model trained with binary:logistic)
        prob = float(self.booster.predict(dmat)[0])
        prob = max(0.0, min(1.0, prob))
        confidence = abs(prob - 0.5) * 2.0

        # SHAP contributions via XGBoost's built-in pred_contribs (faster + no
        # extra dep at inference time). Last column is the bias term — skip it.
        contribs_full = self.booster.predict(dmat, pred_contribs=True)
        # shape: (1, n_features + 1)
        per_feature = np.asarray(contribs_full[0][:-1], dtype=np.float64)
        contributions = [
            (name, float(per_feature[i])) for i, name in enumerate(FEATURE_NAMES)
        ]
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)
        return PredictResult(
            probability=prob,
            confidence=confidence,
            contributions=contributions,
        )


def try_load_xgboost(registry_root: str, version: str) -> XGBoostPredictor | None:
    """Try to load; return None if no artifacts on disk."""
    from app.services.hiring_predictor.registry import ModelRegistry

    reg = ModelRegistry(registry_root)
    artifacts = reg.load(version)
    if artifacts is None:
        return None
    try:
        return XGBoostPredictor(artifacts)
    except Exception as exc:
        log.warning("xgboost_load_failed", version=version, error=str(exc))
        return None


def _path_to_str(p: Path) -> str:  # pragma: no cover — for log readability only
    return str(p)
