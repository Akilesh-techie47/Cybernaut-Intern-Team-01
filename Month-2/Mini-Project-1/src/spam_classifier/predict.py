"""Artifact loading and single-message prediction.

The app must load the trained pipeline — never retrain at request time.
Only the trusted artifact produced by this project's training is loaded.
"""

from __future__ import annotations

import json
import pathlib
from functools import lru_cache
from typing import Dict, Optional, Tuple

import joblib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
ARTIFACT_PATH = PROJECT_ROOT / "models" / "spam_classifier_pipeline.joblib"
METADATA_PATH = PROJECT_ROOT / "models" / "metadata.json"
MAX_INPUT_CHARS = 10_000


class ModelNotTrainedError(FileNotFoundError):
    pass


def _resolve_artifact(path: Optional[pathlib.Path] = None) -> pathlib.Path:
    p = pathlib.Path(path) if path else ARTIFACT_PATH
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve() if not p.exists() else p
    return p


def load_artifact(path: Optional[pathlib.Path] = None):
    """Load the fitted Pipeline. Raises ModelNotTrainedError with next steps."""
    p = _resolve_artifact(path)
    if not p.exists():
        # Fallback: legacy two-file format (vectorizer + model) if present
        legacy_vec = p.parent / "tfidf_vectorizer.pkl"
        legacy_model = p.parent / "spam_classifier.pkl"
        if legacy_vec.exists() and legacy_model.exists():
            from sklearn.pipeline import Pipeline
            vec = joblib.load(legacy_vec)
            clf = joblib.load(legacy_model)
            return Pipeline([("tfidf", vec), ("clf", clf)])
        raise ModelNotTrainedError(
            f"Model artifact not found at {p}. Train it first:\n"
            f"  python -m spam_classifier.train  (run from project root)\n"
            f"or: python src/spam_classifier/train.py"
        )
    try:
        obj = joblib.load(p)
    except Exception as e:  # noqa: BLE001
        raise ModelNotTrainedError(f"Could not load model artifact at {p}: {e}") from e
    if not hasattr(obj, "predict"):
        raise ModelNotTrainedError(f"Artifact at {p} is not a predictor (missing .predict). Retrain the model.")
    return obj


@lru_cache(maxsize=1)
def get_model():
    return load_artifact()


def load_metadata() -> Dict:
    if METADATA_PATH.exists():
        try:
            return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def validate_text(text: object) -> str:
    from .preprocessing import validate_input_text

    return validate_input_text(text, max_chars=MAX_INPUT_CHARS)


def predict_spam_ham(text: str, model=None) -> Tuple[str, Optional[Dict[str, float]]]:
    """Predict 'spam' or 'ham'. Returns (label, probabilities|None).

    Probabilities are returned ONLY when the underlying estimator genuinely
    supports predict_proba. LinearSVC scores are NOT presented as probabilities.
    """
    clean = validate_text(text)
    mdl = model if model is not None else get_model()
    label = str(mdl.predict([clean])[0])
    if label not in ("spam", "ham"):
        # Defensive: normalize unexpected outputs
        label = "spam" if label.lower() == "spam" else "ham"
    proba: Optional[Dict[str, float]] = None
    if hasattr(mdl, "predict_proba"):
        try:
            classes = list(mdl.classes_)
            dist = list(mdl.predict_proba([clean])[0])
            proba = {str(c): float(v) for c, v in zip(classes, dist)}
        except Exception:
            proba = None
    return label, proba
