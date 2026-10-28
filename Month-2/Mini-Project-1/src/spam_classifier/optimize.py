"""Hyperparameter optimization for the three PDF models (NB, LR, LinearSVC).

Leakage-safe protocol (per project spec):
  1. Same stratified 80/20 split (random_state=42) as train.py.
  2. GridSearchCV with StratifiedKFold runs on the TRAIN split only,
     scoring spam F1 (spam = positive class).
  3. Each tuned pipeline is evaluated ONCE on the held-off test set.
  4. Results are compared against the baselines in reports/metrics/metrics.json.

This script NEVER touches the deployed artifact
(models/spam_classifier_pipeline.joblib) — it only reports whether tuning
helped. Promoting a tuned model is a separate, explicit step.

Usage (from project root):
    $env:PYTHONPATH = "src"
    python -m spam_classifier.optimize [--data data/raw/SMSSpamCollection]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split  # noqa: E402
from sklearn.metrics import f1_score, make_scorer  # noqa: E402
from sklearn.naive_bayes import MultinomialNB  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.svm import LinearSVC  # noqa: E402

from spam_classifier.data import load_dataset  # noqa: E402
from spam_classifier.evaluate import compute_metrics, metrics_to_frame  # noqa: E402
from spam_classifier.train import RANDOM_STATE, TEST_SIZE  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

CV_SPLITS = 5

# Small, honest grids: TF-IDF variants from PDF Step 6 + one key
# regularization/smoothing knob per classifier.
GRIDS = {
    "naive_bayes": {
        "estimator": Pipeline([
            ("tfidf", TfidfVectorizer(lowercase=True)),
            ("clf", MultinomialNB()),
        ]),
        "param_grid": {
            "tfidf__max_features": [3000, 5000],
            "tfidf__ngram_range": [(1, 1), (1, 2)],
            "clf__alpha": [0.1, 0.5, 1.0],
        },
    },
    "logistic_regression": {
        "estimator": Pipeline([
            ("tfidf", TfidfVectorizer(lowercase=True)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]),
        "param_grid": {
            "tfidf__max_features": [3000, 5000],
            "tfidf__ngram_range": [(1, 1), (1, 2)],
            "clf__C": [0.5, 1.0, 2.0],
        },
    },
    "svm": {
        "estimator": Pipeline([
            ("tfidf", TfidfVectorizer(lowercase=True)),
            ("clf", LinearSVC()),
        ]),
        "param_grid": {
            "tfidf__max_features": [3000, 5000],
            "tfidf__ngram_range": [(1, 1), (1, 2)],
            "clf__C": [0.5, 1.0, 2.0],
        },
    },
}


def plot_baseline_vs_tuned(baseline: dict, tuned: dict, out_path: pathlib.Path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    models = list(tuned.keys())
    base_f1 = [float(baseline.get(m, {}).get("spam_f1", 0.0)) for m in models]
    tuned_f1 = [float(tuned[m]["test_metrics"]["spam_f1"]) for m in models]
    x = np.arange(len(models))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - width / 2, base_f1, width, label="Baseline (train.py)")
    ax.bar(x + width / 2, tuned_f1, width, label="Tuned (GridSearchCV)")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=10)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Spam F1 (held-out test)")
    ax.set_title("Baseline vs tuned — spam F1 per model (same test split)")
    ax.legend()
    for i, (b, t) in enumerate(zip(base_f1, tuned_f1)):
        ax.text(i - width / 2, b + 0.01, f"{b:.3f}", ha="center", fontsize=8)
        ax.text(i + width / 2, t + 0.01, f"{t:.3f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def optimize(
    data_path=None,
    metrics_dir: pathlib.Path | None = None,
    figures_dir: pathlib.Path | None = None,
) -> dict:
    metrics_dir = pathlib.Path(metrics_dir or PROJECT_ROOT / "reports" / "metrics")
    figures_dir = pathlib.Path(figures_dir or PROJECT_ROOT / "reports" / "figures")
    metrics_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    df, data_report = load_dataset(data_path)
    stratify = df["label"] if df["label"].nunique() > 1 and df["label"].value_counts().min() >= 2 else None
    train_df, test_df = train_test_split(
        df, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=stratify,
    )
    X_train, y_train = train_df["text"].tolist(), train_df["label"].tolist()
    X_test, y_test = test_df["text"].tolist(), test_df["label"].tolist()

    baseline_file = metrics_dir / "metrics.json"
    baseline: dict = {}
    if baseline_file.exists():
        baseline = json.loads(baseline_file.read_text(encoding="utf-8")).get("results", {})

    cv = StratifiedKFold(n_splits=CV_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    scorer = make_scorer(f1_score, pos_label="spam")

    tuned: dict = {}
    for name, spec in GRIDS.items():
        print(f"[{name}] GridSearchCV on train ({len(X_train)} rows, {CV_SPLITS}-fold CV)...", flush=True)
        gs = GridSearchCV(
            spec["estimator"], spec["param_grid"], cv=cv,
            scoring=scorer, n_jobs=-1, refit=True, verbose=0,
        )
        gs.fit(X_train, y_train)  # CV on TRAIN only
        best = gs.best_estimator_
        test_pred = best.predict(X_test)  # single final look at test
        test_metrics = compute_metrics(y_test, test_pred)
        tuned[name] = {
            "best_params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in gs.best_params_.items()},
            "mean_cv_spam_f1": float(gs.best_score_),
            "test_metrics": test_metrics,
            "baseline_test_metrics": baseline.get(name),
            "test_f1_delta_vs_baseline": (
                float(test_metrics["spam_f1"] - baseline[name]["spam_f1"])
                if name in baseline else None
            ),
        }
        print(f"[{name}] best={tuned[name]['best_params']} "
              f"CV-F1={gs.best_score_:.4f} test-F1={test_metrics['spam_f1']:.4f} "
              f"test-acc={test_metrics['accuracy']:.4f}", flush=True)

    with open(metrics_dir / "optimization_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {"cv_splits": CV_SPLITS, "scoring": "spam F1 (pos_label=spam), CV on train only",
             "tuned": tuned, "baseline": baseline},
            f, indent=2,
        )
    frame = metrics_to_frame({k: v["test_metrics"] for k, v in tuned.items()})
    frame.to_csv(metrics_dir / "optimization_comparison.csv", index=False)
    plot_baseline_vs_tuned(baseline, tuned, figures_dir / "optimization_comparison.png")

    print("\n=== Tuned test-set summary (same split as baselines) ===")
    for name, t in tuned.items():
        m = t["test_metrics"]
        d = t["test_f1_delta_vs_baseline"]
        print(f"{name}: acc={m['accuracy']:.4f} prec={m['spam_precision']:.4f} "
              f"rec={m['spam_recall']:.4f} f1={m['spam_f1']:.4f} "
              f"cm={m['confusion_matrix']} (dF1 vs baseline: {d:+.4f})" if d is not None else "")
    return tuned


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Tune NB/LR/SVM via CV on train; evaluate once on test.")
    p.add_argument("--data", default=None)
    p.add_argument("--metrics-dir", default=str(PROJECT_ROOT / "reports" / "metrics"))
    p.add_argument("--figures-dir", default=str(PROJECT_ROOT / "reports" / "figures"))
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    optimize(data_path=args.data, metrics_dir=pathlib.Path(args.metrics_dir),
             figures_dir=pathlib.Path(args.figures_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
