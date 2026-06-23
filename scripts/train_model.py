"""
Train an XGBoost hiring-probability model and save it to the model registry.

Steps:
  1. Load every (candidate_id, job_id, outcome) from `hiring_outcomes`.
  2. Build the feature matrix via FeatureExtractor.
  3. Map outcome → binary label (hired=1; rejected/withdrawn/no_show=0).
  4. Train/test split + XGBoost binary classifier.
  5. Save model + metadata to MODEL_REGISTRY_PATH/<version>/.
  6. Insert a row into `ml_models` table.

Usage:
    .\\.venv\\Scripts\\Activate.ps1
    python -m scripts.train_model --version v1
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session, init_engine
from app.llm import get_llm_client
from app.services.hiring_predictor.features import FEATURE_NAMES, FeatureExtractor
from app.services.hiring_predictor.registry import ModelRegistry

log = get_logger("scripts.train_model")

_HIRED_LABELS = {"hired"}
_NOT_HIRED_LABELS = {"rejected", "withdrawn", "no_show"}


def main() -> None:
    configure_logging("INFO")
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default=None,
                        help="Model version to write (defaults to MODEL_VERSION env).")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-rounds", type=int, default=200)
    args = parser.parse_args()

    settings = get_settings()
    version = args.version or settings.model_version
    init_engine(settings)

    # Lazy imports — xgboost is heavy
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    llm = get_llm_client(settings)
    extractor = FeatureExtractor(llm=llm)

    session_iter = get_session()
    session = next(session_iter)
    try:
        rows = session.execute(
            text("SELECT candidate_id, job_id, outcome FROM hiring_outcomes")
        ).all()
        log.info("hiring_outcomes_loaded", count=len(rows))
        if len(rows) < 20:
            log.error(
                "insufficient_data",
                msg=(
                    f"Found only {len(rows)} hiring_outcomes rows. Run "
                    "`python -m scripts.seed_hiring_outcomes` first."
                ),
            )
            return

        X_list: list[list[float]] = []
        y_list: list[int] = []
        skipped = 0
        for r in rows:
            outcome = (r.outcome or "").lower()
            if outcome in _HIRED_LABELS:
                label = 1
            elif outcome in _NOT_HIRED_LABELS:
                label = 0
            else:
                skipped += 1
                continue
            try:
                fv = extractor.extract(session, candidate_id=r.candidate_id, job_id=r.job_id)
            except Exception as exc:
                log.warning("feature_extract_failed", error=str(exc)[:200])
                skipped += 1
                continue
            X_list.append([fv.values[name] for name in FEATURE_NAMES])
            y_list.append(label)

        log.info("features_built", n=len(X_list), skipped=skipped, positives=sum(y_list))
        if len(X_list) < 10:
            log.error("not_enough_after_extraction")
            return

        X = np.array(X_list, dtype=np.float64)
        y = np.array(y_list, dtype=np.int32)

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=args.test_size, random_state=args.seed, stratify=y
        )

        # Class weight to handle imbalance
        n_pos = int(np.sum(y_train == 1))
        n_neg = int(np.sum(y_train == 0))
        scale_pos_weight = max(n_neg / max(n_pos, 1), 0.5)

        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(FEATURE_NAMES))
        dtest = xgb.DMatrix(X_test, label=y_test, feature_names=list(FEATURE_NAMES))

        params = {
            "objective": "binary:logistic",
            "eval_metric": "auc",
            "tree_method": "hist",
            "max_depth": 4,
            "eta": 0.08,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "min_child_weight": 2.0,
            "scale_pos_weight": scale_pos_weight,
            "seed": args.seed,
            "verbosity": 1,
        }
        booster = xgb.train(
            params,
            dtrain,
            num_boost_round=args.n_rounds,
            evals=[(dtrain, "train"), (dtest, "test")],
            early_stopping_rounds=20,
            verbose_eval=20,
        )

        # Eval
        y_pred_proba = booster.predict(dtest)
        y_pred = (y_pred_proba >= 0.5).astype(np.int32)
        auc = float(roc_auc_score(y_test, y_pred_proba))
        acc = float(accuracy_score(y_test, y_pred))
        log.info("training_metrics", auc=round(auc, 4), accuracy=round(acc, 4))

        # Persist artifact
        trained_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "feature_names": list(FEATURE_NAMES),
            "trained_at": trained_at,
            "training_rows": len(X_train),
            "test_rows": len(X_test),
            "positives": int(np.sum(y_train == 1) + np.sum(y_test == 1)),
            "metrics": {"auc": auc, "accuracy": acc},
            "params": params,
            "best_iteration": int(booster.best_iteration or 0),
        }
        registry = ModelRegistry(settings.model_registry_path)
        out = registry.save(version=version, booster=booster, metadata=metadata)
        log.info("model_saved", version=version, path=str(out))

        # Mirror to ml_models table
        session.execute(
            text(
                """
                INSERT INTO ml_models (name, version, artifact_path, metrics, is_active)
                VALUES (:name, :version, :path, :metrics, :is_active)
                ON CONFLICT (name, version) DO UPDATE
                  SET artifact_path = EXCLUDED.artifact_path,
                      metrics = EXCLUDED.metrics,
                      is_active = EXCLUDED.is_active
                """
            ),
            {
                "name": "hiring_predictor",
                "version": version,
                "path": str(out),
                "metrics": json.dumps({
                    "auc": auc,
                    "accuracy": acc,
                    "n_train": len(X_train),
                    "n_test": len(X_test),
                }),
                "is_active": True,
            },
        )
        session.commit()
        log.info("ml_models_row_upserted", version=version)

        # Final user note
        print()
        print("=" * 60)
        print(f"Model version {version} saved to {out}")
        print(f"  AUC: {auc:.4f} · Accuracy: {acc:.4f}")
        print("  Restart uvicorn to load the new model into the predictor.")
        print("=" * 60)
    finally:
        try:
            next(session_iter)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()


# Keep a reference to Decimal so import-time linters don't complain about the
# unused import — Decimal is used implicitly by the ml_models table mapping.
_ = Decimal
