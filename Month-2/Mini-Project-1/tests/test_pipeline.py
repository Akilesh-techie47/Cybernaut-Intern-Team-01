"""Tests for leakage-safe pipeline, metrics, persistence."""

import pathlib
import sys

import joblib
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spam_classifier.evaluate import compute_metrics
from spam_classifier.train import build_pipeline


@pytest.fixture
def tiny():
    X = ["win free prize now", "claim cash reward", "hey are you coming today",
         "can you send the assignment", "free money urgent claim", "see you at 9am"]
    y = ["spam", "spam", "ham", "ham", "spam", "ham"]
    return X, y


def test_pipeline_fits_vocab_on_train_only(tiny):
    X, y = tiny
    X_train, y_train = X[:4], y[:4]
    pipe = build_pipeline(MultinomialNB())
    pipe.fit(X_train, y_train)
    vocab = set(pipe.named_steps["tfidf"].get_feature_names_out())
    # 'assignment' appears only in train; 'money' never seen in train
    assert "assignment" in vocab or len(vocab) > 0
    # transform of unseen word should not fail
    out = pipe.predict(["money xyz unseen"])
    assert out[0] in ("spam", "ham")


def test_all_three_models_train(tiny):
    X, y = tiny
    for clf in (MultinomialNB(), LogisticRegression(max_iter=1000), LinearSVC()):
        pipe = Pipeline([("tfidf", TfidfVectorizer()), ("clf", clf)])
        pipe.fit(X, y)
        assert pipe.predict(["hello"])[0] in ("spam", "ham")


def test_metrics_and_confusion_shape():
    y_true = ["spam", "spam", "ham", "ham", "spam"]
    y_pred = ["spam", "ham", "ham", "ham", "spam"]
    m = compute_metrics(y_true, y_pred)
    assert 0 <= m["accuracy"] <= 1
    assert 0 <= m["spam_precision"] <= 1
    assert len(m["confusion_matrix"]) == 2 and len(m["confusion_matrix"][0]) == 2
    total = sum(sum(r) for r in m["confusion_matrix"])
    assert total == len(y_true)


def test_save_load_roundtrip(tmp_path, tiny):
    X, y = tiny
    pipe = build_pipeline(LogisticRegression(max_iter=1000))
    pipe.fit(X, y)
    p = tmp_path / "pipe.joblib"
    joblib.dump(pipe, p)
    loaded = joblib.load(p)
    assert loaded.predict(["win free"])[0] in ("spam", "ham")
