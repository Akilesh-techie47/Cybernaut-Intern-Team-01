"""Tests for leakage screening (exact + near-duplicate detection)."""

import pathlib
import sys

import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spam_classifier.leakage import check_pool, exclude_flagged, jaccard, normalize, token_set


def _refs():
    return [
        {"dataset": "short", "row": 0, "form": "text",
         "norm": normalize("Your order has shipped, tracking included")},
        {"dataset": "full", "row": 5, "form": "subject_body",
         "norm": normalize("Payslip\n\nYour September payslip is available")},
    ]


def test_normalize_and_jaccard():
    assert normalize("  Hello   WORLD ") == "hello world"
    assert jaccard(token_set("a b c"), token_set("a b c")) == 1.0
    assert jaccard(token_set("a b c"), token_set("x y z")) == 0.0


def test_exact_hit_flagged():
    pool = pd.DataFrame([{
        "label": "ham", "subject": "Payslip",
        "body": "Your September payslip is available", "source": "synthetic"}])
    rep = check_pool(pool, _refs())
    assert len(rep["exact_hits"]) == 1
    assert rep["n_excluded"] == 1
    assert len(exclude_flagged(pool, rep)) == 0


def test_near_hit_flagged_and_clean_pool_passes():
    pool = pd.DataFrame([
        {"label": "ham", "subject": "Your order has shipped with tracking included today",
         "body": "", "source": "synthetic"},
        {"label": "ham", "subject": "Library books due Monday",
         "body": "Please return them", "source": "synthetic"},
    ])
    rep = check_pool(pool, _refs(), near_threshold=0.5)
    kinds = {h["pool_idx"]: h["kind"] for h in rep["near_hits"]}
    assert kinds.get(0) == "near"
    assert 1 not in rep["flagged_pool_idx"]
    clean = exclude_flagged(pool, rep)
    assert len(clean) == 1


def test_real_pool_is_clean():
    refs_file = PROJECT_ROOT / "reports" / "metrics_email_v2" / "leakage_report.json"
    if not refs_file.exists():
        import pytest
        pytest.skip("v2 leakage report not generated yet.")
    import json
    rep = json.loads(refs_file.read_text(encoding="utf-8"))
    assert rep["exact_hits"] == [] and rep["near_hits"] == []
