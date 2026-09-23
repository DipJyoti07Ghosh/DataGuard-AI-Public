"""
DataGuard AI — Phase D: Gradient-Boosted Training Script

Trains a GradientBoosting or XGBoost classifier (whichever performs better)
on the merged training CSV, evaluates with 5-fold CV, and saves:

  - artifacts/column-risk-v4.joblib
  - artifacts/metadata_column-risk-v4.json

Compares against RandomForest internally and picks the best.

Usage (from backend/, in the dataguard env):

    python -m app.ml.scripts.train_boosted
    python -m app.ml.scripts.train_boosted --data app/ml/artifacts/training_data_merged.csv
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

from app.ml.feature_extractor import build_preprocessor, prepare_training_dataframe

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
DEFAULT_DATA = ARTIFACTS_DIR / "training_data_merged.csv"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.train_boosted")


def build_pipeline(classifier_name: str, random_state: int = 42) -> Pipeline:
    """Construct a pipeline with the named classifier."""
    pre = build_preprocessor()

    if classifier_name == "RandomForest":
        clf = RandomForestClassifier(
            n_estimators=120, max_depth=16, class_weight="balanced",
            random_state=random_state, n_jobs=-1,
        )
    elif classifier_name == "GradientBoosting":
        clf = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.1, max_depth=5,
            random_state=random_state,
        )
    elif classifier_name == "XGBoost":
        if not HAS_XGBOOST:
            raise ValueError("XGBoost not installed")
        clf = XGBClassifier(
            n_estimators=300, learning_rate=0.1, max_depth=6,
            subsample=0.9, colsample_bytree=0.9,
            objective="multi:softprob",
            eval_metric="mlogloss",
            random_state=random_state, n_jobs=-1,
            tree_method="hist", verbosity=0,
        )
    else:
        raise ValueError(f"Unknown classifier: {classifier_name}")

    return Pipeline([("preprocessor", pre), ("classifier", clf)])


def evaluate(name: str, data_path: Path) -> dict:
    logger.info(f"=== Evaluating {name} ===")

    df = prepare_training_dataframe(pd.read_csv(data_path))
    X = df.drop(columns=["target_domain"])
    y = df["target_domain"]
    n_classes = y.nunique()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    pipe = build_pipeline(name)

    # Cross-validation
    t0 = time.time()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="accuracy", n_jobs=-1)
    cv_mean = float(cv_scores.mean())
    cv_std = float(cv_scores.std())
    cv_time = time.time() - t0

    # Held-out test
    t0 = time.time()
    pipe.fit(X_train, y_train)
    fit_time = time.time() - t0
    y_pred = pipe.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    f1_w = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

    logger.info(f"  CV: {cv_mean:.4f} (+/- {cv_std:.4f})  [{cv_time:.1f}s]")
    logger.info(f"  Test accuracy: {acc:.4f}  F1: {f1_w:.4f}  [fit {fit_time:.1f}s]")

    return {
        "name": name,
        "cv_mean": cv_mean,
        "cv_std": cv_std,
        "test_accuracy": acc,
        "test_f1": f1_w,
        "pipe": pipe,
        "cv_time": cv_time,
        "fit_time": fit_time,
        "n_classes": n_classes,
        "n_samples": len(df),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA))
    parser.add_argument("--tag", type=str, default="column-risk-v4")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        logger.error(f"Data file not found: {data_path}")
        return

    logger.info("=" * 60)
    logger.info("  Boosted Training Script (Phase D)")
    logger.info("=" * 60)
    logger.info(f"Data: {data_path}")
    logger.info(f"XGBoost available: {HAS_XGBOOST}")
    logger.info("")

    # Evaluate candidates
    candidates = ["RandomForest", "GradientBoosting"]
    if HAS_XGBOOST:
        candidates.append("XGBoost")

    results = []
    for name in candidates:
        try:
            r = evaluate(name, data_path)
            results.append(r)
        except Exception as e:
            logger.warning(f"  {name} failed: {e}")

    if not results:
        logger.error("No model trained successfully")
        return

    # Pick the best by test accuracy
    results.sort(key=lambda r: r["test_accuracy"], reverse=True)
    best = results[0]

    logger.info("=" * 60)
    logger.info("  LEADERBOARD")
    logger.info("=" * 60)
    for r in results:
        logger.info(
            f"  {r['name']:<20s}  test={r['test_accuracy']:.4f}  "
            f"f1={r['test_f1']:.4f}  cv={r['cv_mean']:.4f}±{r['cv_std']:.4f}"
        )

    logger.info("")
    logger.info(f"Best model: {best['name']}  (test accuracy {best['test_accuracy']:.4f})")

    # Save best model
    model_path = ARTIFACTS_DIR / f"{args.tag}.joblib"
    meta_path = ARTIFACTS_DIR / f"metadata_{args.tag}.json"

    joblib.dump(best["pipe"], model_path)

    metadata = {
        "model_version": args.tag,
        "algorithm": best["name"],
        "sklearn_version": sklearn.__version__,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_source": data_path.name,
        "total_samples": best["n_samples"],
        "num_classes": best["n_classes"],
        "classes": sorted(list(best["pipe"].classes_)),
        "leaderboard": [
            {
                "name": r["name"],
                "test_accuracy": round(r["test_accuracy"], 4),
                "test_f1": round(r["test_f1"], 4),
                "cv_mean": round(r["cv_mean"], 4),
                "cv_std": round(r["cv_std"], 4),
            }
            for r in results
        ],
        "metrics": {
            "test_accuracy": round(best["test_accuracy"], 4),
            "test_f1_weighted": round(best["test_f1"], 4),
            "cv_accuracy_mean": round(best["cv_mean"], 4),
            "cv_accuracy_std": round(best["cv_std"], 4),
        },
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info(f"Model saved: {model_path}  ({model_path.stat().st_size / 1024:.0f} KB)")
    logger.info(f"Metadata: {meta_path}")
    logger.info("=" * 60)

    print()
    print("Leaderboard:")
    print(pd.DataFrame([{k: v for k, v in r.items() if k != 'pipe'} for r in results]).to_string(index=False))


if __name__ == "__main__":
    main()