"""
DataGuard AI — ML Model Predictor & Inference Engine

Provides lazy-loading singleton access to the trained scikit-learn column classifier.
Infers semantic domain categories and calibrated confidence probabilities from column feature vectors.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from app.ml.model import MODEL_VERSION

logger = logging.getLogger("dataguard.ml.predictor")

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
MODEL_FILE_PATH = ARTIFACTS_DIR / f"{MODEL_VERSION}.joblib"
METADATA_FILE_PATH = ARTIFACTS_DIR / f"metadata_{MODEL_VERSION}.json"


class MLDomainPredictor:
    """
    Singleton ML inference service for column domain classification.
    """
    _instance: Optional["MLDomainPredictor"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.model: Optional[Pipeline] = None
        self.metadata: Dict[str, Any] = {}
        self.classes: List[str] = []
        self._load_artifacts()

    @classmethod
    def get_instance(cls) -> "MLDomainPredictor":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_artifacts(self) -> None:
        """Loads serialized scikit-learn pipeline and metadata JSON."""
        if not MODEL_FILE_PATH.exists():
            logger.warning(
                f"Model file '{MODEL_FILE_PATH}' not found. Attempting to train initial baseline model..."
            )
            from app.ml.trainer import train_and_evaluate_model
            res = train_and_evaluate_model(samples_per_domain=180, save_artifacts=True)
            self.model = res["pipeline"]
            self.metadata = res["metadata"]
            self.classes = sorted(list(self.model.classes_))
            logger.info("Initial model trained and loaded successfully.")
            return

        try:
            self.model = joblib.load(MODEL_FILE_PATH)
            if METADATA_FILE_PATH.exists():
                with open(METADATA_FILE_PATH, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {"model_version": MODEL_VERSION}
            self.classes = sorted(list(self.model.classes_))
            logger.info(
                f"Loaded ML model '{self.metadata.get('model_version', MODEL_VERSION)}' with {len(self.classes)} domain classes."
            )
        except Exception as e:
            logger.error(f"Failed to load ML model from '{MODEL_FILE_PATH}': {e}", exc_info=True)
            raise RuntimeError(f"Unable to load ML model artifact: {e}")

    def predict_column(self, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predicts semantic domain and confidence for a single column feature dictionary.
        Returns:
            - predicted_domain: str
            - model_confidence: float (0.0 to 1.0)
            - class_probabilities: Dict[str, float]
            - model_version: str
        """
        df_row = pd.DataFrame([feature_dict])
        return self.predict_dataframe(df_row)[0]

    def predict_dataframe(self, feature_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Runs batch inference across multiple column feature vectors.
        """
        if self.model is None:
            self._load_artifacts()

        # Generate predictions and calibrated probabilities
        preds = self.model.predict(feature_df)
        probas = self.model.predict_proba(feature_df)
        classes = list(self.model.classes_)

        results = []
        for i, pred_class in enumerate(preds):
            prob_row = probas[i]
            class_prob_dict = {
                cls_name: round(float(prob_row[idx]), 4)
                for idx, cls_name in enumerate(classes)
            }
            top_conf = round(float(max(prob_row)), 4)

            results.append({
                "predicted_domain": str(pred_class),
                "model_confidence": top_conf,
                "class_probabilities": class_prob_dict,
                "model_version": self.metadata.get("model_version", MODEL_VERSION),
            })

        return results


def get_ml_predictor() -> MLDomainPredictor:
    """Convenience accessor for MLDomainPredictor singleton."""
    return MLDomainPredictor.get_instance()
