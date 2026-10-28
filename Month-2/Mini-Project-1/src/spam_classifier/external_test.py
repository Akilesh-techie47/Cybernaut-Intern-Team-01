"""Bulk-test the DEPLOYED pipeline on external labeled CSVs.

Uses the exact same code path as the Streamlit site (predict_spam_ham ->
models/spam_classifier_pipeline.joblib). Never retrains.

Test protocol per dataset is explicit about what text is fed in:
  - short messages CSV: the `text` column as-is (what a user pastes).
  - full-email CSV: `subject + blank line + body` (what a user would paste;
    sender from_name/from_email are EXCLUDED because the site only accepts
    message text and claims no sender-behavior analysis).

Usage (from project root):
    $env:PYTHONPATH = "src"
    python -m spam_classifier.external_test --name short_messages --csv <path> --mode text
    python -m spam_classifier.external_test --name full_emails --csv <path> --mode subject_body
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

from spam_classifier.data import normalize_label  # noqa: E402
from spam_classifier.evaluate import compute_metrics  # noqa: E402
from spam_classifier.predict import load_artifact, validate_text  # noqa: E402


def build_inputs(df: pd.DataFrame, mode: str) -> pd.Series:
    if mode == "text":
        if "text" not in df.columns:
            raise ValueError(f"mode=text needs a 'text' column, got {list(df.columns)}")
        return df["text"].astype(str)
    if mode == "subject_body":
        for c in ("subject", "body"):
            if c not in df.columns:
                raise ValueError(f"mode=subject_body needs 'subject'/'body', got {list(df.columns)}")
        return df["subject"].astype(str) + "\n\n" + df["body"].astype(str)
    raise ValueError(f"unknown mode: {mode}")


def external_test(name: str, csv_path: str | pathlib.Path,
                  mode: str, out_dir: pathlib.Path | None = None,
                  artifact: str | pathlib.Path | None = None) -> dict:
    out_dir = pathlib.Path(out_dir or PROJECT_ROOT / "reports" / "metrics")
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path, encoding="utf-8", engine="python")

    labels = df["label"].apply(normalize_label)
    bad = int(labels.isna().sum())
    if bad:
        raise ValueError(f"{bad}/{len(df)} labels unrecognized: "
                         f"{df.loc[labels.isna(), 'label'].unique().tolist()}")
    inputs = build_inputs(df, mode)

    model = load_artifact(pathlib.Path(artifact) if artifact else None)
    rows, skipped = [], 0
    for i, (true, raw) in enumerate(zip(labels.tolist(), inputs.tolist())):
        try:
            clean = validate_text(raw)  # same validation the site applies
        except ValueError:
            skipped += 1
            continue
        pred = str(model.predict([clean])[0])
        rows.append({"row": i, "true_label": true, "pred_label": pred,
                     "correct": bool(pred == true), "chars": len(clean)})

    result_df = pd.DataFrame(rows)
    metrics = compute_metrics(result_df["true_label"].tolist(),
                              result_df["pred_label"].tolist())
    summary = {
        "dataset": name, "source": str(csv_path), "mode": mode,
        "n_rows": int(len(df)), "n_evaluated": int(len(result_df)),
        "n_skipped_by_site_validation": int(skipped),
        "metrics": metrics,
    }
    with open(out_dir / f"external_test_{name}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    result_df.to_csv(out_dir / f"external_test_{name}_predictions.csv", index=False)

    m = metrics
    print(f"[{name}] n={len(result_df)} (skipped={skipped}) "
          f"acc={m['accuracy']:.4f} prec={m['spam_precision']:.4f} "
          f"rec={m['spam_recall']:.4f} f1={m['spam_f1']:.4f} cm={m['confusion_matrix']}")
    errors = result_df[~result_df["correct"]]
    if len(errors):
        print(f"[{name}] misclassified rows: {errors['row'].tolist()}")
    return summary


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Bulk-test deployed pipeline on a labeled CSV.")
    p.add_argument("--name", required=True)
    p.add_argument("--csv", required=True)
    p.add_argument("--mode", required=True, choices=["text", "subject_body"])
    p.add_argument("--out-dir", default=str(PROJECT_ROOT / "reports" / "metrics"))
    p.add_argument("--artifact", default=None,
                   help="Model artifact to test (default: deployed models/spam_classifier_pipeline.joblib).")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    external_test(a.name, a.csv, a.mode, pathlib.Path(a.out_dir), a.artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
