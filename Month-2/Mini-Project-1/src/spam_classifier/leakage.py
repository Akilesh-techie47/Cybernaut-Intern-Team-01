"""Leakage screening: keep the 200 external test messages out of training.

Checks a training pool (label,subject,body[,source]) against BOTH external
test files in every input form the site accepts:
  - short CSV: `text` as-is
  - full-email CSV: `subject + body` AND `full_email`

Two match levels on normalized text (lowercased, whitespace-collapsed):
  - EXACT: normalized strings identical -> always excluded from training.
  - NEAR: token-set Jaccard >= threshold (default 0.90) -> reported for human
    review and excluded by default (fail-safe: test integrity beats pool size).

Usage (from project root):
    $env:PYTHONPATH = "src"
    python -m spam_classifier.leakage --pool data/raw/email_train_v2.csv \\
        --clean-pool data/raw/email_train_v2_clean.csv --report reports/metrics_email_v2/leakage_report.json
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

TEST_SHORT = pathlib.Path(r"C:\Users\ELCOT\Downloads\email_spam_classifier_100_test_messages.csv")
TEST_FULL = pathlib.Path(r"C:\Users\ELCOT\Downloads\100_full_email_spam_ham_test_dataset.csv")

WS = re.compile(r"\s+")
NEAR_THRESHOLD = 0.90


def normalize(text: object) -> str:
    return WS.sub(" ", str(text or "").lower()).strip()


def token_set(text: str) -> frozenset:
    return frozenset(text.split())


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_test_texts() -> list[dict]:
    """All test-message forms. Raises FileNotFoundError if a test CSV is absent."""
    refs: list[dict] = []
    if not TEST_SHORT.exists():
        raise FileNotFoundError(f"External test file missing: {TEST_SHORT}")
    short = pd.read_csv(TEST_SHORT, encoding="utf-8", engine="python")
    for i, t in enumerate(short["text"].astype(str).tolist()):
        refs.append({"dataset": "short", "row": i, "form": "text", "norm": normalize(t)})
    if not TEST_FULL.exists():
        raise FileNotFoundError(f"External test file missing: {TEST_FULL}")
    full = pd.read_csv(TEST_FULL, encoding="utf-8", engine="python")
    for i, r in full.iterrows():
        refs.append({"dataset": "full", "row": int(i), "form": "subject_body",
                     "norm": normalize(str(r["subject"]) + "\n\n" + str(r["body"]))})
        refs.append({"dataset": "full", "row": int(i), "form": "full_email",
                     "norm": normalize(str(r["full_email"]))})
    return refs


def pool_texts(pool: pd.DataFrame) -> list[str]:
    subj = pool["subject"].where(pool["subject"].notna(), "").astype(str)
    body = pool["body"].where(pool["body"].notna(), "").astype(str)
    return [normalize(s + "\n\n" + b) for s, b in zip(subj.tolist(), body.tolist())]


def check_pool(pool: pd.DataFrame, test_refs: list[dict] | None = None,
               near_threshold: float = NEAR_THRESHOLD) -> dict:
    test_refs = test_refs if test_refs is not None else load_test_texts()
    exact_index: dict[str, dict] = {}
    for r in test_refs:
        exact_index.setdefault(r["norm"], r)
    test_tokens = [(r, token_set(r["norm"])) for r in test_refs]
    texts = pool_texts(pool)
    exact_hits, near_hits = [], []
    for idx, text in enumerate(texts):
        if text in exact_index:
            t = exact_index[text]
            exact_hits.append({"pool_idx": idx, "dataset": t["dataset"],
                               "row": t["row"], "form": t["form"], "kind": "exact"})
            continue
        toks = token_set(text)
        best: dict | None = None
        for t, ttoks in test_tokens:
            # Cheap length pre-filter before set ops.
            if not ttoks or abs(len(toks) - len(ttoks)) > max(len(toks), len(ttoks)) * 0.5:
                continue
            score = jaccard(toks, ttoks)
            if score >= near_threshold and (best is None or score > best["jaccard"]):
                best = {"pool_idx": idx, "dataset": t["dataset"], "row": t["row"],
                        "form": t["form"], "kind": "near", "jaccard": round(score, 3)}
        if best:
            near_hits.append(best)
    flagged = {h["pool_idx"] for h in exact_hits + near_hits}
    return {
        "n_pool": int(len(pool)), "n_test_refs": len(test_refs),
        "near_threshold": near_threshold,
        "exact_hits": exact_hits, "near_hits": near_hits,
        "flagged_pool_idx": sorted(flagged),
        "n_excluded": len(flagged),
    }


def exclude_flagged(pool: pd.DataFrame, report: dict) -> pd.DataFrame:
    drop = set(report["flagged_pool_idx"])
    return pool.loc[~pool.index.isin(drop)].reset_index(drop=True)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Screen a training pool against the 200 external test messages.")
    p.add_argument("--pool", required=True)
    p.add_argument("--clean-pool", default=None)
    p.add_argument("--report", default=None)
    p.add_argument("--near-threshold", type=float, default=NEAR_THRESHOLD)
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    pool = pd.read_csv(a.pool, encoding="utf-8", engine="python")
    report = check_pool(pool, near_threshold=a.near_threshold)
    print(f"pool={report['n_pool']} exact={len(report['exact_hits'])} "
          f"near(>={a.near_threshold})={len(report['near_hits'])} "
          f"excluded={report['n_excluded']}")
    for h in report["exact_hits"][:10] + report["near_hits"][:10]:
        print(f"  {h['kind']}: pool_idx={h['pool_idx']} test={h['dataset']}[{h['row']}]/{h['form']}"
              + (f" j={h['jaccard']}" if h["kind"] == "near" else ""))
    if a.report:
        rp = pathlib.Path(a.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    if a.clean_pool:
        clean = exclude_flagged(pool, report)
        cp = pathlib.Path(a.clean_pool)
        cp.parent.mkdir(parents=True, exist_ok=True)
        clean.to_csv(cp, index=False)
        print(f"wrote clean pool: {cp} ({len(clean)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
