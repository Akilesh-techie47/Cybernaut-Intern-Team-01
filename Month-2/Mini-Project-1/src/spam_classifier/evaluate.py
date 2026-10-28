"""Metrics and plotting utilities. Spam is the positive class."""

from __future__ import annotations

import pathlib
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


def compute_metrics(y_true, y_pred, pos_label: str = "spam") -> Dict:
    y_true = list(y_true)
    y_pred = list(y_pred)
    cm = confusion_matrix(y_true, y_pred, labels=["ham", "spam"])
    tn, fp, fn, tp = cm.ravel().tolist()
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "spam_precision": float(precision_score(y_true, y_pred, pos_label=pos_label, zero_division=0)),
        "spam_recall": float(recall_score(y_true, y_pred, pos_label=pos_label, zero_division=0)),
        "spam_f1": float(f1_score(y_true, y_pred, pos_label=pos_label, zero_division=0)),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "confusion_labels": ["ham", "spam"],
        "n_test": int(len(y_true)),
    }


def plot_label_distribution(label_counts: Dict[str, int], out_path: pathlib.Path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = ["ham", "spam"]
    values = [int(label_counts.get(l, 0)) for l in labels]
    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(labels, values)
    ax.set_title("Label distribution (cleaned dataset)")
    ax.set_ylabel("Count")
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:,}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_model_comparison(results: Dict[str, Dict], out_path: pathlib.Path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    models = list(results.keys())
    metrics = ["accuracy", "spam_precision", "spam_recall", "spam_f1"]
    x = np.arange(len(models))
    width = 0.2
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, m in enumerate(metrics):
        vals = [float(results[mdl].get(m, 0.0)) for mdl in models]
        ax.bar(x + (i - 1.5) * width, vals, width, label=m.replace("spam_", "spam ").title())
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=10)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Score")
    ax.set_title("Model comparison (held-out test set, spam = positive)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_confusion_matrix(cm: List[List[int]], labels: List[str], title: str, out_path: pathlib.Path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.array(cm)
    fig, ax = plt.subplots(figsize=(4.2, 3.8))
    im = ax.imshow(arr, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels([f"Pred {l}" for l in labels])
    ax.set_yticklabels([f"Actual {l}" for l in labels])
    ax.set_title(title)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, str(arr[i, j]), ha="center", va="center",
                    color="white" if arr[i, j] > arr.max() / 2 else "black", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_top_spam_terms(pipeline, top_n: int, out_path: pathlib.Path) -> pathlib.Path:
    """Bar chart of top terms most indicative of spam.

    Works for linear models with coef_ (LogisticRegression/LinearSVC) and
    Naive Bayes via log-prob difference. Falls back gracefully.
    """
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        vec = pipeline.named_steps["tfidf"]
        clf = pipeline.named_steps["clf"]
        terms = np.array(vec.get_feature_names_out())
        if hasattr(clf, "coef_"):
            scores = np.asarray(clf.coef_).ravel()
            # For binary clf, positive coef -> spam if classes_[1]=='spam'
            if list(getattr(clf, "classes_", ["ham", "spam"]))[0] == "spam":
                scores = -scores
        elif hasattr(clf, "feature_log_prob_"):
            # NB: log P(term|spam) - log P(term|ham)
            classes = list(clf.classes_)
            i_spam, i_ham = classes.index("spam"), classes.index("ham")
            scores = clf.feature_log_prob_[i_spam] - clf.feature_log_prob_[i_ham]
        else:
            raise AttributeError("classifier has no coef_ or feature_log_prob_")
        idx = np.argsort(scores)[-top_n:][::-1]
        top_terms, top_scores = terms[idx], scores[idx]
    except Exception as e:  # noqa: BLE001
        fig, ax = plt.subplots(figsize=(6, 2.5))
        ax.text(0.5, 0.5, f"Top-terms plot unavailable:\n{e}", ha="center", va="center", fontsize=9)
        ax.axis("off")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        return out_path
    fig, ax = plt.subplots(figsize=(7, max(3, top_n * 0.28)))
    y = np.arange(len(top_terms))
    ax.barh(y, top_scores)
    ax.set_yticks(y)
    ax.set_yticklabels(top_terms, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Spam association score (higher = more spam-indicative)")
    ax.set_title(f"Top {len(top_terms)} spam-indicative terms (trained model)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def metrics_to_frame(results: Dict[str, Dict]) -> "pd.DataFrame":
    rows = []
    for model, m in results.items():
        rows.append({
            "model": model,
            "accuracy": m.get("accuracy"),
            "spam_precision": m.get("spam_precision"),
            "spam_recall": m.get("spam_recall"),
            "spam_f1": m.get("spam_f1"),
            "n_test": m.get("n_test"),
        })
    return pd.DataFrame(rows)
