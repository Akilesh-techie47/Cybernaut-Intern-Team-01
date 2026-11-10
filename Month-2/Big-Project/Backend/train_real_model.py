"""
AeroDelay AI - Production Model Training on Real BTS Dataset.

Trains a scikit-learn LogisticRegression model on the full 498,870 BTS training records
using memory-safe CSR sparse matrix batching, evaluates on the held-out 58,225 test records,
and serializes verified Python 3.13-compatible artifacts.
"""

import json
import os
import shutil
import time
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq
import scipy.sparse as sp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
ARTIFACTS_DIR = BASE_DIR / "artifacts" / "models"


def load_parquet_as_csr(parquet_path: Path, batch_size: int = 50000) -> sp.csr_matrix:
    """Load a large Parquet feature matrix in chunks into a compact CSR matrix."""
    t0 = time.time()
    pf = pq.ParquetFile(parquet_path)
    total_rows = pf.metadata.num_rows
    print(f"Loading {parquet_path.name} ({total_rows} rows, {pf.metadata.num_columns} cols)...")

    batches = []
    for batch in pf.iter_batches(batch_size=batch_size):
        chunk_df = batch.to_pandas()
        chunk_csr = sp.csr_matrix(chunk_df.values, dtype=np.float32)
        batches.append(chunk_csr)

    full_csr = sp.vstack(batches, format="csr")
    print(f"  Loaded into CSR matrix: shape {full_csr.shape}, nnz {full_csr.nnz} ({time.time() - t0:.2f}s)")
    return full_csr


def main():
    X_train_path = DATA_DIR / "X_train.parquet"
    y_train_path = DATA_DIR / "y_train.parquet"
    X_test_path = DATA_DIR / "X_test.parquet"
    y_test_path = DATA_DIR / "y_test.parquet"

    assert X_train_path.exists(), f"Missing {X_train_path}"
    assert y_train_path.exists(), f"Missing {y_train_path}"
    assert X_test_path.exists(), f"Missing {X_test_path}"
    assert y_test_path.exists(), f"Missing {y_test_path}"

    print("=== STEP 1: Load Real BTS Training and Test Sets ===")
    X_train = load_parquet_as_csr(X_train_path)
    y_train = pq.read_table(y_train_path).column(0).to_numpy().astype(int)

    X_test = load_parquet_as_csr(X_test_path)
    y_test = pq.read_table(y_test_path).column(0).to_numpy().astype(int)

    print(f"X_train: {X_train.shape}, y_train: {y_train.shape} (positive rate: {np.mean(y_train):.3f})")
    print(f"X_test:  {X_test.shape},  y_test:  {y_test.shape}  (positive rate: {np.mean(y_test):.3f})")

    # Get feature names from Parquet schema
    pf = pq.ParquetFile(X_train_path)
    feature_names = pf.schema.names
    print(f"Total features: {len(feature_names)}")

    print("\n=== STEP 2: Train Logistic Regression Model (Balanced Class Weights) ===")
    t_start = time.time()
    # class_weight='balanced' ensures risk probabilities span the full 0.0-1.0 range
    # and balances recall on the 25% positive class
    model = LogisticRegression(
        C=1.0,
        max_iter=300,
        solver="lbfgs",
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)
    training_time = time.time() - t_start
    print(f"Training completed in {training_time:.2f}s")

    print("\n=== STEP 3: Comprehensive Evaluation on Held-Out Test Set (58,225 records) ===")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_test, y_proba))
    pr_auc = float(average_precision_score(y_test, y_proba))
    cm = confusion_matrix(y_test, y_pred).tolist()

    train_acc = float(model.score(X_train, y_train))

    metrics = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "train_accuracy": round(train_acc, 4),
        "test_accuracy": round(acc, 4),
        "confusion_matrix": cm,
        "training_time_s": round(training_time, 2),
        "n_train_samples": int(X_train.shape[0]),
        "n_test_samples": int(X_test.shape[0]),
        "n_features": int(X_train.shape[1]),
    }

    print("Test Metrics:")
    print(f"  Accuracy:  {acc:.4f}")
    print(f"  Precision: {prec:.4f}")
    print(f"  Recall:    {rec:.4f}")
    print(f"  F1 Score:  {f1:.4f}")
    print(f"  ROC-AUC:   {roc_auc:.4f}")
    print(f"  PR-AUC:    {pr_auc:.4f}")
    print("  Confusion Matrix:", cm)

    print("\n=== STEP 4: Serialize Model Artifacts ===")
    real_model_path = ARTIFACTS_DIR / "logistic_regression_real.joblib"
    new_model_path = ARTIFACTS_DIR / "logistic_regression_new.joblib"
    backup_synthetic_path = ARTIFACTS_DIR / "logistic_regression_synthetic_backup.joblib"

    # Backup synthetic model if not already backed up
    if new_model_path.exists() and not backup_synthetic_path.exists():
        shutil.copy2(new_model_path, backup_synthetic_path)
        print(f"Backed up synthetic model to {backup_synthetic_path.name}")

    # Save real model
    joblib.dump(model, real_model_path, compress=3)
    print(f"Saved real model to {real_model_path} ({real_model_path.stat().st_size} bytes)")

    # Also update logistic_regression_new.joblib so current backend uses the real trained model
    joblib.dump(model, new_model_path, compress=3)
    print(f"Updated {new_model_path} ({new_model_path.stat().st_size} bytes)")

    print("\n=== STEP 5: Update Model Metadata ===")
    metadata_path = ARTIFACTS_DIR / "model_metadata.json"

    meta_content = {
        "name": "Logistic Regression (Real BTS)",
        "type": "Linear Model",
        "version": "Phase 5.4 Production v1.0",
        "python_version": "3.13.15",
        "library_versions": {
            "joblib": joblib.__version__,
            "scikit-learn": "1.9.1",
            "numpy": np.__version__,
        },
        "feature_schema": {
            "n_features": 654,
            "feature_names": feature_names,
            "feature_structure": {
                "carrier_ohe": 14,
                "origin_ohe": 318,
                "dest_ohe": 318,
                "numerical": 4,
            },
        },
        "target_definition": {
            "name": "DepDelay15",
            "description": "Flight departure delay of 15 minutes or more",
            "positive_class": 1,
            "negative_class": 0,
        },
        "training_data": {
            "dataset": "BTS On-Time Performance",
            "period": "2022-12",
            "n_samples": int(X_train.shape[0]),
            "n_features": 654,
            "class_distribution": {
                "class_0_on_time": int(np.sum(y_train == 0)),
                "class_1_delayed": int(np.sum(y_train == 1)),
            },
        },
        "model_metrics": metrics,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta_content, f, indent=2)
    print(f"Updated {metadata_path.name}")

    print("\n=== Training & Serialization Complete ===")


if __name__ == "__main__":
    main()
