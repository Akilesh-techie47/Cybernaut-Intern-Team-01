"""Tests for dataset loading / validation."""

import pathlib
import sys

import pandas as pd
import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spam_classifier.data import DatasetError, load_dataset, normalize_label


def test_normalize_labels():
    assert normalize_label("spam") == "spam"
    assert normalize_label("HAM") == "ham"
    assert normalize_label(" Spam ") == "spam"
    assert normalize_label("1") == "spam"
    assert normalize_label("0") == "ham"
    assert normalize_label("???") is None
    assert normalize_label(None) is None


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        load_dataset(PROJECT_ROOT / "data" / "raw" / "does_not_exist_xyz.csv")


def test_unexpected_columns(tmp_path):
    p = tmp_path / "weird.csv"
    pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6], "d": [7, 8]}).to_csv(p, index=False)
    with pytest.raises((DatasetError, Exception)):
        load_dataset(p)


def test_missing_values_handled(tmp_path):
    p = tmp_path / "mini.csv"
    pd.DataFrame({
        "label": ["spam", None, "ham", "???", "ham"],
        "message": ["win free now", "hello", None, "mystery", "   "],
    }).to_csv(p, index=False)
    df, report = load_dataset(p)
    assert set(df["label"].unique()) <= {"spam", "ham"}
    assert len(df) == 1  # only the valid spam row survives
    assert report["removed_rows"] >= 4


def test_real_dataset_if_present():
    candidate = PROJECT_ROOT / "data" / "raw" / "SMSSpamCollection"
    if not candidate.exists():
        pytest.skip("Real dataset not present.")
    df, report = load_dataset(candidate)
    assert {"text", "label"} == set(df.columns)
    assert set(df["label"].unique()) <= {"spam", "ham"}
    assert report["kept_rows"] > 5000
    assert report["label_counts"]["ham"] > report["label_counts"]["spam"]
