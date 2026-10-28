"""Tests for category coverage audit and the v3 data gate."""

import json
import pathlib
import sys

import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spam_classifier.coverage import categorize, coverage
from spam_classifier.coverage import main as coverage_main


def _pool(rows):
    return pd.DataFrame(rows)


def test_categorize_rules_ordered_and_conservative():
    assert categorize("Payslip for March", "salary credited") == "transactional"
    assert categorize("Team meeting Tuesday", "agenda attached") == "business"
    assert categorize("Campus newsletter", "unsubscribe anytime") == "newsletter"
    assert categorize("Dinner at home Sunday", "bring dessert") == "personal"
    assert categorize("Re: kernel compile log", "gcc output follows") == "uncategorized"
    # Conversational only for short questions; long questions stay uncategorized.
    assert categorize("Quick one", "Can you send the slides?") == "conversational"
    long_q = "Are you free? " + "Some detailed background context. " * 20
    assert categorize("Long thread", long_q) == "uncategorized"


def test_coverage_splits_genuine_vs_synthetic(tmp_path):
    p = tmp_path / "pool.csv"
    _pool([
        {"label": "ham", "subject": "Payslip", "body": "pay here", "source": "spamassassin"},
        {"label": "ham", "subject": "Order shipped", "body": "tracking", "source": "modern_ham"},
        {"label": "ham", "subject": "Invoice", "body": "due", "source": "synthetic"},
        {"label": "spam", "subject": "Win", "body": "prize", "source": "spamassassin"},
    ]).to_csv(p, index=False)
    cov = coverage(p)
    assert cov["modern_ham_rows"] == 1
    assert cov["ham_total"] == 3 and cov["spam_total"] == 1
    tr = cov["ham_by_category_origin"]["transactional"]
    assert tr == {"genuine": 2, "synthetic": 1, "total": 3}


def test_gate_blocks_without_modern_ham_and_passes_with_it(tmp_path):
    pool = tmp_path / "pool.csv"
    _pool([{"label": "ham", "subject": "Hello list", "body": "chatter",
            "source": "spamassassin"}]).to_csv(pool, index=False)
    assert coverage_main(["--pool", str(pool), "--require-modern-ham", "500"]) == 2
    _pool([
        {"label": "ham", "subject": "Hello list", "body": "chatter", "source": "spamassassin"},
        {"label": "ham", "subject": "Payslip", "body": "pay", "source": "modern_ham"},
    ]).to_csv(pool, index=False)
    assert coverage_main(["--pool", str(pool), "--require-modern-ham", "1"]) == 0


def test_gate_report_is_valid_json(tmp_path):
    pool = tmp_path / "pool.csv"
    _pool([{"label": "ham", "subject": "s", "body": "b", "source": "synthetic"}]).to_csv(pool, index=False)
    rep = tmp_path / "cov.json"
    rc = coverage_main(["--pool", str(pool), "--report", str(rep)])
    assert rc == 0
    data = json.loads(rep.read_text(encoding="utf-8"))
    assert data["modern_ham_rows"] == 0 and data["pool_rows"] == 1
