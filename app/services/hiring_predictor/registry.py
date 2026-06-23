"""
File-system model registry for hiring-predictor XGBoost artifacts.

Layout under MODEL_REGISTRY_PATH:
    <registry_path>/
      v1/
        model.json        # XGBoost native JSON (portable)
        metadata.json     # feature_names, training_stats, sklearn version etc.
      v2/
        ...

The active version is pinned by MODEL_VERSION. Listing also tracks rows in the
`ml_models` table (see scripts/train_model.py for the writer side).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelArtifacts:
    version: str
    model_path: Path
    metadata: dict[str, Any]


class ModelRegistry:
    def __init__(self, root: str):
        self.root = Path(root)

    def version_dir(self, version: str) -> Path:
        return self.root / version

    def exists(self, version: str) -> bool:
        v = self.version_dir(version)
        return (v / "model.json").exists() and (v / "metadata.json").exists()

    def load(self, version: str) -> ModelArtifacts | None:
        if not self.exists(version):
            return None
        v = self.version_dir(version)
        with (v / "metadata.json").open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        return ModelArtifacts(version=version, model_path=v / "model.json", metadata=metadata)

    def save(
        self,
        *,
        version: str,
        booster,  # xgboost.Booster
        metadata: dict[str, Any],
    ) -> Path:
        v = self.version_dir(version)
        v.mkdir(parents=True, exist_ok=True)
        model_path = v / "model.json"
        booster.save_model(str(model_path))
        with (v / "metadata.json").open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)
        return v
