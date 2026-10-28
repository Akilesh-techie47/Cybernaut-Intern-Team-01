"""Category-coverage audit: genuine vs synthetic ham across 7 categories.

Categories: personal, educational, conversational, transactional, business,
newsletter, notification (+ 'uncategorized' when no rule fires — common for
2002-era mailing-list ham, reported honestly rather than force-fit).

Keyword rules are deterministic, applied in fixed order (first match wins),
and documented in CATEGORY_RULES so any count in CATEGORY_COVERAGE.md is
reproducible. Genuine = source spamassassin/modern_ham; synthetic = synthetic.

Also emits the test-ham category map (evaluation metadata only — NEVER
training input) and enforces the v3 data gate: --require-modern-ham N exits
non-zero unless the pool holds N genuine modern_ham rows.

Usage (from project root):
    $env:PYTHONPATH = "src"
    python -m spam_classifier.coverage --pool data/raw/email_train_v2_clean.csv --require-modern-ham 500
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pandas as pd  # noqa: E402

CATEGORIES = ("personal", "educational", "conversational", "transactional",
              "business", "newsletter", "notification", "uncategorized")

# Fixed order, first match wins. Deliberately conservative: money/shipment
# vocabulary dominates because misclassifying those hides the FP problem.
CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("transactional", r"payslip|salary|payroll|order\b|shipped|shipping|deliver|tracking|carrier|invoice|receipt|purchase order|\bpayment\b|billing|statement|refund|reimburs|warranty|premium due|amount due"),
    ("business", r"meeting|interview|leave request|appointment|calendar|invit|support request|code review|\bapi\b|backup|software update|standup|sprint|expense report|travel request|manager|hr\b|offer letter"),
    ("notification", r"reminder|librar|books due|overdue|maintenance|fire alarm|departure|schedule|webinar|webcast|event|workshop|conference|certificate|test results|bill\b|utility|power cut|water supply|road repair|downtime"),
    ("newsletter", r"newsletter|digest|unsubscribe|edition|editorial|top picks|this month at|monthly roundup"),
    ("educational", r"lecture|assignment|timetable|course\b|lab\b|scholarship|assessment|exam\b|grade\b|professor|campus|faculty|student|tutorial|syllabus|capstone|webinar"),
    ("personal", r"dinner|game\b|weekend|photos?\b|trip\b|family|party|birthday|lunch|wedding|vacation|reunion|barbecue|movie night"),
    ("conversational", r"\?"),
)

GENUINE_SOURCES = ("spamassassin", "modern_ham")


def categorize(subject: object, body: object) -> str:
    text = f"{subject or ''}\n{body or ''}".lower()
    short_question = "?" in text and len(text) < 150
    for category, pattern in CATEGORY_RULES:
        if category == "conversational" and not short_question:
            continue
        if re.search(pattern, text):
            return category
    return "uncategorized"


def coverage(pool_csv: str | pathlib.Path,
             manifest_path: str | pathlib.Path | None = None) -> dict:
    pool = pd.read_csv(pool_csv, encoding="utf-8", engine="python")
    for col in ("label", "subject", "body"):
        if col not in pool.columns:
            raise ValueError(f"Pool '{pool_csv}' lacks column '{col}'.")
    source = pool["source"] if "source" in pool.columns else "unknown"
    pool = pool.copy()
    pool["category"] = [categorize(s, b) for s, b in
                        zip(pool["subject"].tolist(), pool["body"].tolist())]
    pool["origin"] = ["genuine" if s in GENUINE_SOURCES else
                      ("synthetic" if s == "synthetic" else f"other:{s}")
                      for s in (source.tolist() if hasattr(source, "tolist") else [source] * len(pool))]
    ham = pool[pool["label"] == "ham"]
    table: dict[str, dict[str, int]] = {}
    for cat in CATEGORIES:
        sub = ham[ham["category"] == cat]
        table[cat] = {"genuine": int((sub["origin"] == "genuine").sum()),
                      "synthetic": int((sub["origin"] == "synthetic").sum()),
                      "total": int(len(sub))}
    modern = int(((pool["source"] == "modern_ham").sum()) if "source" in pool.columns else 0)
    return {
        "pool": str(pool_csv),
        "pool_rows": int(len(pool)),
        "modern_ham_rows": modern,
        "manifest": str(manifest_path) if manifest_path else None,
        "ham_by_category_origin": table,
        "ham_total": int((pool["label"] == "ham").sum()),
        "spam_total": int((pool["label"] == "spam").sum()),
    }


def test_ham_map(test_full_csv: str | pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(test_full_csv, encoding="utf-8", engine="python")
    ham = df[df["label"] == "ham"]
    return pd.DataFrame({
        "row": ham.index.tolist(),
        "subject": ham["subject"].tolist(),
        "category": [categorize(s, b) for s, b in
                     zip(ham["subject"].tolist(), ham["body"].tolist())],
    })


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Audit ham category coverage; enforce the v3 data gate.")
    p.add_argument("--pool", required=True)
    p.add_argument("--manifest", default=None)
    p.add_argument("--report", default=None, help="Write coverage JSON here.")
    p.add_argument("--test-categories-out", default=None,
                   help="Write test-ham category map CSV here (metadata only).")
    p.add_argument("--test-full-csv", default=None)
    p.add_argument("--require-modern-ham", type=int, default=0,
                   help="Exit non-zero unless pool holds >=N genuine modern_ham rows.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    cov = coverage(a.pool, a.manifest)
    print(f"pool={cov['pool_rows']} ham={cov['ham_total']} spam={cov['spam_total']} "
          f"modern_ham={cov['modern_ham_rows']}")
    for cat in CATEGORIES:
        c = cov["ham_by_category_origin"][cat]
        print(f"  {cat:15s} genuine={c['genuine']:5d} synthetic={c['synthetic']:5d} total={c['total']:5d}")
    if a.report:
        rp = pathlib.Path(a.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(cov, f, indent=2)
        print(f"wrote {rp}")
    if a.test_categories_out:
        if not a.test_full_csv:
            raise ValueError("--test-full-csv is required with --test-categories-out.")
        m = test_ham_map(a.test_full_csv)
        mp = pathlib.Path(a.test_categories_out)
        mp.parent.mkdir(parents=True, exist_ok=True)
        m.to_csv(mp, index=False)
        print(f"wrote test-ham map: {mp} ({len(m)} rows)")
        print("test-ham distribution:", m["category"].value_counts().to_dict())
    if a.require_modern_ham and cov["modern_ham_rows"] < a.require_modern_ham:
        print(f"V3 DATA GATE: BLOCKED — pool holds {cov['modern_ham_rows']} genuine "
              f"modern_ham rows, need >={a.require_modern_ham}. No training, no promotion. "
              f"See reports/HAM_COLLECTION_GUIDE.md.")
        return 2
    print("V3 DATA GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
