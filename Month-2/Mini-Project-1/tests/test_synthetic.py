"""Tests for the synthetic ham generator: labeled, deterministic, ham-only dev aid."""

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spam_classifier.synthetic_ham import TEMPLATES, generate


def test_all_rows_ham_with_category():
    df, manifest = generate(per_category=5, seed=7)
    assert set(df["label"].unique()) == {"ham"}
    assert set(df["category"].unique()) == set(TEMPLATES.keys())
    assert (df["subject"].str.len() > 0).all() and (df["body"].str.len() > 0).all()


def test_deterministic_and_labeled_synthetic():
    df1, _ = generate(per_category=5, seed=7)
    df2, _ = generate(per_category=5, seed=7)
    assert df1.equals(df2)
    df3, _ = generate(per_category=5, seed=8)
    assert not df1.equals(df3)


def test_manifest_marks_synthetic_dev_aid():
    _, manifest = generate(per_category=5, seed=7)
    assert "synthetic" in manifest["generator"].lower()
    assert "not genuine" in manifest["warning"].lower()
    assert manifest["rows_after_dedupe"] == len(
        generate(per_category=5, seed=7)[0]
    )
