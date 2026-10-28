"""Leakage-safe training: TF-IDF inside Pipeline, stratified split, 3 models.

Compares MultinomialNB, LogisticRegression, LinearSVC on the same split.
Selects the final model by highest spam F1 (tie-break: spam precision,
to favour a low false-positive rate), saves the full fitted pipeline as
one joblib artifact plus metadata, metrics, and plots.

Usage:
    python -m spam_classifier.train --data data/raw/SMSSpamCollection
    python src/spam_classifier/train.py --data data/raw/SMSSpamCollection
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from spam_classifier.data import load_dataset  # noqa: E402
from spam_classifier.evaluate import (  # noqa: E402
    compute_metrics,
    metrics_to_frame,
    plot_confusion_matrix,
    plot_label_distribution,
    plot_model_comparison,
    plot_top_spam_terms,
)

RANDOM_STATE = 42
TEST_SIZE = 0.2
MAX_FEATURES = 5000
NGRAM_RANGE = (1, 2)

CANDIDATES = {
    "naive_bayes": MultinomialNB(),
    "logistic_regression": LogisticRegression(max_iter=1000),
    "svm": LinearSVC(),
}


def build_pipeline(classifier) -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=MAX_FEATURES,
            ngram_range=NGRAM_RANGE,
            lowercase=True,
        )),
        ("clf", classifier),
    ])


def select_best(results: dict) -> str:
    """Best = highest spam F1; tie-break = highest spam precision."""
    return sorted(
        results.keys(),
        key=lambda k: (results[k]["spam_f1"], results[k]["spam_precision"]),
        reverse=True,
    )[0]


def train(
    data_path=None,
    models_dir: pathlib.Path | None = None,
    metrics_dir: pathlib.Path | None = None,
    figures_dir: pathlib.Path | None = None,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> dict:
    models_dir = pathlib.Path(models_dir or PROJECT_ROOT / "models")
    metrics_dir = pathlib.Path(metrics_dir or PROJECT_ROOT / "reports" / "metrics")
    figures_dir = pathlib.Path(figures_dir or PROJECT_ROOT / "reports" / "figures")
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    df, data_report = load_dataset(data_path)
    stratify = df["label"] if df["label"].nunique() > 1 and df["label"].value_counts().min() >= 2 else None
    train_df, test_df = train_test_split(
        df, test_size=test_size, random_state=random_state, stratify=stratify,
    )
    X_train, y_train = train_df["text"].tolist(), train_df["label"].tolist()
    X_test, y_test = test_df["text"].tolist(), test_df["label"].tolist()

    results: dict = {}
    fitted: dict = {}
    for name, clf in CANDIDATES.items():
        pipe = build_pipeline(clf)
        pipe.fit(X_train, y_train)  # vocabulary fit on TRAIN only (leakage-safe)
        pred = pipe.predict(X_test)
        results[name] = compute_metrics(y_test, pred)
        fitted[name] = pipe

    best_name = select_best(results)
    best_pipe = fitted[best_name]

    # Save single pipeline artifact + metadata
    artifact_path = models_dir / "spam_classifier_pipeline.joblib"
    joblib.dump(best_pipe, artifact_path)
    metadata = {
        "model_name": best_name,
        "model_class": type(best_pipe.named_steps["clf"]).__name__,
        "dataset": data_report.get("source_path"),
        "trained_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "random_state": random_state,
        "test_size": test_size,
        "tfidf": {"max_features": MAX_FEATURES, "ngram_range": list(NGRAM_RANGE), "lowercase": True},
        "data_report": data_report,
        "test_metrics": results[best_name],
        "all_metrics": results,
        "n_train": len(train_df),
        "n_test": len(test_df),
        "supports_predict_proba": hasattr(best_pipe.named_steps["clf"], "predict_proba"),
        "artifact": str(artifact_path.name),
    }
    with open(models_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Metrics CSV/JSON
    with open(metrics_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump({"best_model": best_name, "results": results, "data_report": data_report}, f, indent=2)
    frame = metrics_to_frame(results)
    frame.to_csv(metrics_dir / "model_comparison.csv", index=False)

    # Plots (from ACTUAL data/results)
    plot_label_distribution(data_report["label_counts"], figures_dir / "label_distribution.png")
    plot_model_comparison(results, figures_dir / "model_comparison.png")
    for name, m in results.items():
        plot_confusion_matrix(
            m["confusion_matrix"], ["ham", "spam"],
            f"Confusion matrix — {name} (test set)",
            figures_dir / f"confusion_matrix_{name}.png",
        )
    plot_top_spam_terms(best_pipe, 20, figures_dir / "top_spam_terms.png")

    # Smoke test: reload in-process and predict
    reloaded = joblib.load(artifact_path)
    _ = reloaded.predict(["Free prize! Claim now", "Can we meet tomorrow?"])

    print(f"Rows: {data_report['kept_rows']} kept ({data_report['removed_rows']} removed). Labels: {data_report['label_counts']}")
    for name, m in results.items():
        print(f"{name}: acc={m['accuracy']:.4f} prec={m['spam_precision']:.4f} "
              f"rec={m['spam_recall']:.4f} f1={m['spam_f1']:.4f} cm={m['confusion_matrix']}")
    print(f"Selected: {best_name} -> {artifact_path}")
    return {"best_model": best_name, "results": results, "metadata": metadata,
            "artifact_path": str(artifact_path)}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Train spam classifier (3 models, TF-IDF pipeline).")
    p.add_argument("--data", default=None, help="Path to dataset file (default: auto-detect in data/raw/).")
    p.add_argument("--models-dir", default=str(PROJECT_ROOT / "models"))
    p.add_argument("--metrics-dir", default=str(PROJECT_ROOT / "reports" / "metrics"))
    p.add_argument("--figures-dir", default=str(PROJECT_ROOT / "reports" / "figures"))
    p.add_argument("--test-size", type=float, default=TEST_SIZE)
    p.add_argument("--random-state", type=int, default=RANDOM_STATE)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    train(data_path=args.data, models_dir=pathlib.Path(args.models_dir),
          metrics_dir=pathlib.Path(args.metrics_dir), figures_dir=pathlib.Path(args.figures_dir),
          test_size=args.test_size, random_state=args.random_state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
