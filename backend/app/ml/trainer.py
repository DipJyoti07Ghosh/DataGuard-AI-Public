"""
DataGuard AI — ML Model Training, Evaluation & Serialization Workflow

Trains the column domain classifier on bootstrap training data,
computes stratified cross-validation and test set evaluation metrics,
and serializes the trained pipeline and metadata to disk.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import joblib
import sklearn
from sklearn.metrics import classification_report, accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from app.ml.feature_extractor import prepare_training_dataframe
from app.ml.model import (
    MODEL_VERSION,
    FEATURE_SCHEMA_VERSION,
    create_column_classifier_pipeline,
)
from app.ml.training_data import generate_bootstrap_training_data, DOMAINS

logger = logging.getLogger("dataguard.ml.trainer")

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
MODEL_FILE_PATH = ARTIFACTS_DIR / f"{MODEL_VERSION}.joblib"
METADATA_FILE_PATH = ARTIFACTS_DIR / f"metadata_{MODEL_VERSION}.json"


def train_and_evaluate_model(
    samples_per_domain: int = 180,
    random_state: int = 42,
    save_artifacts: bool = True,
) -> Dict[str, Any]:
    """
    Executes full training pipeline:
    1. Generates bootstrap training dataset
    2. Performs stratified 80/20 train/test split
    3. Runs 5-fold cross-validation on training set
    4. Evaluates test set performance (Accuracy, Precision, Recall, F1)
    5. Fits pipeline on all data and serializes artifacts
    """
    logger.info("Generating bootstrap training dataset for column classification...")
    raw_df = generate_bootstrap_training_data(
        samples_per_domain=samples_per_domain,
        random_state=random_state,
    )
    df = prepare_training_dataframe(raw_df)

    X = df.drop(columns=["target_domain"])
    y = df["target_domain"]

    total_samples = len(df)
    logger.info(f"Total training samples generated: {total_samples} across {len(DOMAINS)} domains.")

    # 1. Stratified Train/Test Split (80% Train, 20% Test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_state, stratify=y
    )

    # 2. 5-Fold Stratified Cross-Validation on Training Split
    eval_pipeline = create_column_classifier_pipeline(random_state=random_state)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
    cv_scores = cross_val_score(eval_pipeline, X_train, y_train, cv=cv, scoring="accuracy", n_jobs=-1)
    cv_mean = float(cv_scores.mean())
    cv_std = float(cv_scores.std())

    # 3. Test Set Evaluation
    eval_pipeline.fit(X_train, y_train)
    y_pred = eval_pipeline.predict(X_test)

    acc = float(accuracy_score(y_test, y_pred))
    prec_macro = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
    rec_macro = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
    f1_macro = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
    report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    logger.info(
        f"Model Evaluation: Test Accuracy={acc:.4f}, Weighted F1={f1_macro:.4f}, CV Mean={cv_mean:.4f} (+/- {cv_std:.4f})"
    )

    # 4. Final Fit on Complete Dataset for Production Serialization
    final_pipeline = create_column_classifier_pipeline(random_state=random_state)
    final_pipeline.fit(X, y)

    # 5. Build Comprehensive Metadata
    metadata = {
        "model_version": MODEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "sklearn_version": sklearn.__version__,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "random_state": random_state,
        "total_samples": total_samples,
        "samples_per_domain": samples_per_domain,
        "classes": sorted(list(final_pipeline.classes_)),
        "is_bootstrap_dataset": True,
        "notes": (
            "Model trained on synthetic bootstrap column metadata. "
            "Production deployments should retrain using human-labelled enterprise schemas."
        ),
        "metrics": {
            "test_accuracy": round(acc, 4),
            "test_precision_weighted": round(prec_macro, 4),
            "test_recall_weighted": round(rec_macro, 4),
            "test_f1_weighted": round(f1_macro, 4),
            "cv_accuracy_mean": round(cv_mean, 4),
            "cv_accuracy_std": round(cv_std, 4),
            "classification_report": report_dict,
        },
    }

    # 6. Save Artifacts
    if save_artifacts:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(final_pipeline, MODEL_FILE_PATH)
        with open(METADATA_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Model saved to '{MODEL_FILE_PATH}' and metadata to '{METADATA_FILE_PATH}'")

    return {
        "pipeline": final_pipeline,
        "metadata": metadata,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = train_and_evaluate_model()
    print("=== MODEL TRAINING COMPLETE ===")
    print(json.dumps(res["metadata"]["metrics"], indent=2))
