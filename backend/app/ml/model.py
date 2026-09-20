"""
DataGuard AI — ML Model Architecture Definition

Defines the supervised classification pipeline combining feature transformers
and an ensemble Random Forest classifier for tabular column domain inference.
"""

from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from app.ml.feature_extractor import build_preprocessor

MODEL_VERSION = "column-risk-v1"
FEATURE_SCHEMA_VERSION = "1.0.0"


def create_column_classifier_pipeline(random_state: int = 42) -> Pipeline:
    """
    Constructs the end-to-end scikit-learn Pipeline for column domain classification.
    Combines text TF-IDF vectorization, numeric feature standardization,
    and a balanced ensemble Random Forest classifier.
    """
    preprocessor = build_preprocessor()

    classifier = RandomForestClassifier(
        n_estimators=120,
        max_depth=16,
        min_samples_split=2,
        min_samples_leaf=1,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])

    return pipeline
