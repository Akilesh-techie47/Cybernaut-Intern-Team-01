"""Tests for prediction service: validation, labels, missing model."""

import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spam_classifier.predict import (
    MAX_INPUT_CHARS,
    ModelNotTrainedError,
    load_artifact,
    predict_spam_ham,
    validate_text,
)


def test_empty_and_whitespace_rejected():
    with pytest.raises(ValueError):
        validate_text("")
    with pytest.raises(ValueError):
        validate_text("   \n\t  ")
    with pytest.raises(ValueError):
        validate_text(None)


def test_too_long_rejected():
    with pytest.raises(ValueError):
        validate_text("x" * (MAX_INPUT_CHARS + 1))


def test_missing_artifact(tmp_path):
    with pytest.raises(ModelNotTrainedError):
        load_artifact(tmp_path / "nope.joblib")


def test_valid_input_returns_spam_or_ham():
    pytest.importorskip("sklearn")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline

    X = ["win free prize", "claim now", "hello how are you", "see you tomorrow"] * 5
    y = ["spam", "spam", "ham", "ham"] * 5
    model = Pipeline([("tfidf", TfidfVectorizer()), ("clf", MultinomialNB())])
    model.fit(X, y)
    label, _ = predict_spam_ham("win a free prize now", model=model)
    assert label in ("spam", "ham")
    label2, _ = predict_spam_ham("see you tomorrow at class", model=model)
    assert label2 in ("spam", "ham")
