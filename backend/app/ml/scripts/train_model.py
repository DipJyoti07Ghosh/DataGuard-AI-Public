"""
DataGuard AI — Training Script for Column Domain Classifier

Trains a RandomForest-based scikit-learn Pipeline on the merged training CSV,
evaluates on a held-out test split with 5-fold cross-validation, and serializes:

  - artifacts/column-risk-v1.joblib            (trained sklearn Pipeline)
  - artifacts/metadata_column-risk-v1.json     (metrics + model info)

The Pipeline combines:
  - TF-IDF vectorization over the normalized column name
  - StandardScaler over numeric features (missing %, unique %, moments, etc.)
  - RandomForestClassifier with balanced class weights

Usage (from backend/, in the `dataguard` conda env):

    python -m app.ml.scripts.train_model
    python -m app.ml.scripts.train_model --data app/ml/artifacts/training_data_synthetic.csv
    python -m app.ml.scripts.train_model --data app/ml/artifacts/training_data_merged.csv --tag v2
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
import pandas as pd
import sklearn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from app.ml.feature_extractor import prepare_training_dataframe
from app.ml.model import (
    MODEL_VERSION,
    FEATURE_SCHEMA_VERSION,
    create_column_classifier_pipeline,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
DEFAULT_DATA = ARTIFACTS_DIR / "training_data_synthetic.csv"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.train_model")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def train(
    data_path: Path,
    model_version: str = MODEL_VERSION,
    test_size: float = 0.20,
    cv_folds: int = 5,
    random_state: int = 42,
) -> dict:
    """
    Train, evaluate, and persist the column domain classifier.
    Returns a dict with the trained pipeline and metadata.
    """
    start_ts = time.time()
    logger.info("=" * 60)
    logger.info("  Column Domain Classifier — Training")
    logger.info("=" * 60)
    logger.info(f"Data source: {data_path}")
    logger.info(f"Model version: {model_version}")
    logger.info(f"Test split: {test_size:.0%}")
    logger.info(f"Cross-validation folds: {cv_folds}")
    logger.info(f"Random state: {random_state}")

    # ----- 1. Load CSV -----
    if not data_path.exists():
        raise FileNotFoundError(f"Training data not found: {data_path}")

    df_raw = pd.read_csv(data_path)
    logger.info(f"Loaded {len(df_raw)} rows from CSV")

    if "target_domain" not in df_raw.columns:
        raise ValueError(
            f"Training CSV must contain a 'target_domain' column. "
            f"Found columns: {list(df_raw.columns)}"
        )

    # ----- 2. Prepare features -----
    df = prepare_training_dataframe(df_raw)
    X = df.drop(columns=["target_domain"])
    y = df["target_domain"]

    total_samples = len(df)
    num_classes = y.nunique()
    logger.info(f"Prepared {total_samples} samples across {num_classes} classes")
    logger.info(f"Feature columns: {len(X.columns)}")

    # ----- 3. Train/test split -----
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    logger.info(
        f"Train: {len(X_train)} samples | Test: {len(X_test)} samples"
    )

    # ----- 4. 5-fold cross-validation on training set -----
    logger.info(f"Running {cv_folds}-fold stratified cross-validation...")
    cv_pipeline = create_column_classifier_pipeline(random_state=random_state)
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    cv_scores = cross_val_score(
        cv_pipeline, X_train, y_train, cv=cv, scoring="accuracy", n_jobs=-1
    )
    cv_mean = float(cv_scores.mean())
    cv_std = float(cv_scores.std())
    logger.info(f"CV Accuracy: {cv_mean:.4f} (+/- {cv_std:.4f})")

    # ----- 5. Fit on training set, evaluate on test set -----
    logger.info("Fitting pipeline on training set...")
    eval_pipeline = create_column_classifier_pipeline(random_state=random_state)
    eval_pipeline.fit(X_train, y_train)

    logger.info("Evaluating on held-out test set...")
    y_pred = eval_pipeline.predict(X_test)

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
    rec = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
    f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    logger.info(f"Test accuracy:    {acc:.4f}")
    logger.info(f"Test precision:   {prec:.4f}")
    logger.info(f"Test recall:      {rec:.4f}")
    logger.info(f"Test F1:          {f1:.4f}")

    # ----- 6. Refit on the FULL dataset for production -----
    logger.info("Refitting pipeline on the full dataset for production...")
    final_pipeline = create_column_classifier_pipeline(random_state=random_state)
    final_pipeline.fit(X, y)

    # ----- 7. Save artifacts -----
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACTS_DIR / f"{model_version}.joblib"
    metadata_path = ARTIFACTS_DIR / f"metadata_{model_version}.json"

    joblib.dump(final_pipeline, model_path)
    logger.info(f"Model saved: {model_path}  ({model_path.stat().st_size / 1024:.0f} KB)")

    elapsed = round(time.time() - start_ts, 2)
    metadata = {
        "model_version": model_version,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "sklearn_version": sklearn.__version__,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_source": str(data_path.name),
        "training_source_rows": int(total_samples),
        "training_source_path": str(data_path),
        "random_state": random_state,
        "test_size": test_size,
        "cv_folds": cv_folds,
        "total_samples": total_samples,
        "num_classes": num_classes,
        "classes": sorted(list(final_pipeline.classes_)),
        "training_time_seconds": elapsed,
        "metrics": {
            "test_accuracy": round(acc, 4),
            "test_precision_weighted": round(prec, 4),
            "test_recall_weighted": round(rec, 4),
            "test_f1_weighted": round(f1, 4),
            "cv_accuracy_mean": round(cv_mean, 4),
            "cv_accuracy_std": round(cv_std, 4),
            "classification_report": report,
        },
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info(f"Metadata saved: {metadata_path}")
    logger.info(f"Total training time: {elapsed}s")
    logger.info("=" * 60)

    return {"pipeline": final_pipeline, "metadata": metadata, "model_path": model_path}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the column domain classifier and save model artifacts."
    )
    parser.add_argument(
        "--data",
        type=str,
        default=str(DEFAULT_DATA),
        help=f"Path to the training CSV (default: {DEFAULT_DATA.name})",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=MODEL_VERSION,
        help=f"Model version tag (default: {MODEL_VERSION})",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.20,
        help="Fraction of data used for the held-out test set (default: 0.20)",
    )
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=5,
        help="Number of cross-validation folds (default: 5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    result = train(
        data_path=Path(args.data),
        model_version=args.tag,
        test_size=args.test_size,
        cv_folds=args.cv_folds,
        random_state=args.seed,
    )

    print()
    print("=" * 60)
    print("  TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Model:  {result['model_path']}")
    print(f"  Test accuracy: {result['metadata']['metrics']['test_accuracy']:.4f}")
    print(f"  CV accuracy:   {result['metadata']['metrics']['cv_accuracy_mean']:.4f} "
          f"(+/- {result['metadata']['metrics']['cv_accuracy_std']:.4f})")
    print("=" * 60)


if __name__ == "__main__":
    main()