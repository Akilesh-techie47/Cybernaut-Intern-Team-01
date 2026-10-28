"""Tests for the validated ham importer (provenance preserved, no silent relabeling)."""

import pathlib
import sys

import pandas as pd
import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spam_classifier.data import DatasetError
from spam_classifier.ham_import import build_pool, validate_ham_csv


def _write(tmp_path, name, rows):
    p = tmp_path / name
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def test_valid_import_stamps_source(tmp_path):
    p = _write(tmp_path, "ham.csv", [
        {"label": "ham", "subject": "Payslip", "body": "Your pay is here"},
        {"label": "spam", "subject": "Win", "body": "Claim prize now"},
    ])
    frame, rep = validate_ham_csv(p, "modern_ham")
    assert len(frame) == 2
    assert set(frame["source"].unique()) == {"modern_ham"}
    assert rep["label_counts"] == {"ham": 1, "spam": 1}
    assert rep["kept_rows"] == 2


def test_unknown_labels_abort_import(tmp_path):
    p = _write(tmp_path, "bad.csv", [
        {"label": "ham", "subject": "Ok", "body": "fine"},
        {"label": "maybe", "subject": "?", "body": "unknown label"},
    ])
    with pytest.raises(DatasetError):
        validate_ham_csv(p, "modern_ham")


def test_empty_and_duplicate_rows_counted(tmp_path):
    p = _write(tmp_path, "dirty.csv", [
        {"label": "ham", "subject": "", "body": ""},
        {"label": "ham", "subject": "Hi", "body": "hello"},
        {"label": "ham", "subject": "Hi", "body": "hello"},
    ])
    frame, rep = validate_ham_csv(p, "modern_ham")
    assert rep["empty_dropped"] == 1
    assert rep["exact_duplicates_dropped"] == 1
    assert len(frame) == 1


def test_missing_columns_and_source_rejected(tmp_path):
    p = _write(tmp_path, "nobody.csv", [{"label": "ham", "text": "no body col"}])
    with pytest.raises(DatasetError):
        validate_ham_csv(p, "modern_ham")
    p2 = _write(tmp_path, "ok.csv", [{"label": "ham", "subject": "s", "body": "b"}])
    with pytest.raises(DatasetError):
        validate_ham_csv(p2, "customer_inbox")
    with pytest.raises(FileNotFoundError):
        validate_ham_csv(tmp_path / "absent.csv", "modern_ham")


def test_pool_combines_sources_with_provenance(tmp_path):
    a = _write(tmp_path, "a.csv", [{"label": "ham", "subject": "A", "body": "one"}])
    b = _write(tmp_path, "b.csv", [{"label": "ham", "subject": "B", "body": "two"}])
    pool, prov = build_pool(
        [(a, "modern_ham"), (b, "synthetic")],
        tmp_path / "pool.csv", tmp_path / "prov.json",
    )
    assert len(pool) == 2
    assert prov["by_source_label"] == {"modern_ham/ham": 1, "synthetic/ham": 1}
    assert (tmp_path / "prov.json").exists()
