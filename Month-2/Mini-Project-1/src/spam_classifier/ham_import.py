"""Validated importer for additional labeled email CSVs + provenance-tracked pooling.

Expected import format: label,subject,body (the email-site format).
Nothing is silently relabeled: unknown label values FAIL the import loudly.

Each imported row is stamped with a `source` value so SpamAssassin history,
newly sourced ham, and synthetic examples stay identifiable end to end:
  - 'spamassassin' : historical corpus rows (reserved, stamped by email_data)
  - 'modern_ham'   : newly sourced genuine ham supplied by the user/curator
  - 'synthetic'    : template-generated dev-aid rows (never genuine mail)

Validation per file (all reported, never hidden):
  - required columns label/subject/body present (extra columns dropped, noted)
  - encoding utf-8, latin-1 fallback (encoding recorded)
  - labels normalize to spam/ham; ANY unknown label value aborts the import
  - rows with empty subject AND body are dropped and counted
  - exact (label, subject, body) duplicates within the file are dropped/counted

Usage (from project root):
    $env:PYTHONPATH = "src"
    python -m spam_classifier.ham_import --csv new_ham.csv --source modern_ham --pool data/raw/email_train_v2.csv
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

import pandas as pd  # noqa: E402

from spam_classifier.data import DatasetError, normalize_label  # noqa: E402

RESERVED_SOURCES = ("spamassassin", "modern_ham", "synthetic")
REQUIRED_COLUMNS = ("label", "subject", "body")


def read_csv_with_encoding(path: pathlib.Path) -> tuple[pd.DataFrame, str]:
    for encoding in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding, engine="python"), encoding
        except UnicodeDecodeError:
            continue
    raise DatasetError(f"Could not decode '{path}' as utf-8 or latin-1.")


def validate_ham_csv(path: str | pathlib.Path, source: str) -> tuple[pd.DataFrame, dict]:
    """Validate one CSV and stamp provenance. Raises DatasetError on any label problem."""
    if source not in RESERVED_SOURCES:
        raise DatasetError(f"source must be one of {RESERVED_SOURCES}, got {source!r}.")
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Import file not found: {path}")
    df, encoding = read_csv_with_encoding(path)
    total = len(df)
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise DatasetError(f"'{path}' missing required columns {missing_cols}; "
                           f"has {list(df.columns)}. Expected label,subject,body.")
    extra = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    work = pd.DataFrame({
        "label_raw": df["label"],
        "subject": df["subject"].where(df["subject"].notna(), "").astype(str).str.strip(),
        "body": df["body"].where(df["body"].notna(), "").astype(str).str.strip(),
    })
    work["label"] = work["label_raw"].apply(normalize_label)
    bad_mask = work["label"].isna()
    if int(bad_mask.sum()):
        bad_vals = sorted({str(v) for v in work.loc[bad_mask, "label_raw"].unique()})[:10]
        raise DatasetError(
            f"'{path}': {int(bad_mask.sum())}/{total} rows have unrecognized labels "
            f"(e.g. {bad_vals}). Import aborted — fix labels to spam/ham variants; "
            f"nothing was relabeled or imported."
        )
    empty_mask = (work["subject"] == "") & (work["body"] == "")
    n_empty = int(empty_mask.sum())
    work = work.loc[~empty_mask].copy()
    before = len(work)
    work = work.drop_duplicates(subset=["label", "subject", "body"], keep="first")
    n_dupes = before - len(work)
    work["source"] = source
    report = {
        "file": str(path), "source": source, "encoding": encoding,
        "total_rows": int(total), "extra_columns_dropped": extra,
        "empty_dropped": n_empty, "exact_duplicates_dropped": int(n_dupes),
        "kept_rows": int(len(work)),
        "label_counts": {str(k): int(v) for k, v in work["label"].value_counts().to_dict().items()},
    }
    return work[["label", "subject", "body", "source"]], report


def build_pool(inputs: list[tuple[str | pathlib.Path, str]],
               out_csv: str | pathlib.Path,
               provenance_json: str | pathlib.Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Combine validated sources into one provenance-tracked pool CSV."""
    frames, file_reports = [], []
    for csv_path, source in inputs:
        frame, rep = validate_ham_csv(csv_path, source)
        frames.append(frame)
        file_reports.append(rep)
    pool = pd.concat(frames, ignore_index=True)
    before = len(pool)
    pool = pool.drop_duplicates(subset=["label", "subject", "body"], keep="first").reset_index(drop=True)
    out_csv = pathlib.Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pool.to_csv(out_csv, index=False)
    by_source_label = {f"{s}/{lb}": int(n) for (s, lb), n in
                         pool.groupby(["source", "label"]).size().items()}
    provenance = {
        "pool_csv": str(out_csv),
        "inputs": file_reports,
        "cross_source_duplicates_removed": int(before - len(pool)),
        "pool_rows": int(len(pool)),
        "by_source_label": by_source_label,
    }
    if provenance_json:
        provenance_json = pathlib.Path(provenance_json)
        provenance_json.parent.mkdir(parents=True, exist_ok=True)
        with open(provenance_json, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2)
    print(f"pool={len(pool)} rows (cross-source dupes removed: {before - len(pool)})")
    print(f"by source/label: {provenance['by_source_label']}")
    return pool, provenance


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Validate label,subject,body CSVs and add them to a pool.")
    p.add_argument("--input", action="append", default=[],
                   help="Repeatable 'CSV_PATH:SOURCE', e.g. --input new_ham.csv:modern_ham")
    p.add_argument("--csv", default=None, help="Single input CSV (shorthand for one --input).")
    p.add_argument("--source", default=None, choices=list(RESERVED_SOURCES))
    p.add_argument("--pool", required=True, help="Output pool CSV path.")
    p.add_argument("--provenance", default=None)
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    inputs: list[tuple[str, str]] = []
    for item in a.input:
        if ":" not in item:
            raise DatasetError(f"--input must be 'CSV_PATH:SOURCE', got {item!r}.")
        csv_path, source = item.rsplit(":", 1)
        inputs.append((csv_path, source))
    if a.csv:
        if not a.source:
            raise DatasetError("--source is required with --csv.")
        inputs.append((a.csv, a.source))
    if not inputs:
        raise DatasetError("No inputs given. Use --input CSV:SOURCE (repeatable) or --csv/--source.")
    build_pool(inputs, a.pool, a.provenance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
