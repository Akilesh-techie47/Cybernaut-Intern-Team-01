"""Data loading, schema checks, and validation.

Canonical internal schema: DataFrame with exactly two columns:
    - ``text``: message body (non-empty string after stripping)
    - ``label``: normalized to ``spam`` or ``ham``

Supported raw formats:
    1. UCI SMS Spam Collection (tab-separated, no header, 2 cols):
       ``<ham|spam>\\t<message>``  e.g. file ``SMSSpamCollection``.
    2. CSV with header containing a label column and a text column, e.g.
       ``label,message`` or ``v1,v2`` (Kaggle SMS Spam Collection mirror)
       or ``spam/ham,text`` variants. Encoding latin-1 is tried as fallback.

Invalid rows (missing text/label, unknown label, whitespace-only text)
are removed deliberately and reported in the returned report dict.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATHS: List[pathlib.Path] = [
    PROJECT_ROOT / "data" / "raw" / "SMSSpamCollection",
    PROJECT_ROOT / "data" / "raw" / "spam.csv",
    PROJECT_ROOT / "data" / "raw" / "SMSSpamCollection.tsv",
    PROJECT_ROOT / "data" / "raw" / "sms_spam.csv",
]

LABEL_MAP = {
    "spam": "spam",
    "ham": "ham",
    "1": "spam",
    "0": "ham",
    "true": "spam",
    "false": "ham",
    "yes": "spam",
    "no": "ham",
    "spammy": "spam",
}

TEXT_CANDIDATES = ["text", "message", "msg", "sms", "body", "content", "v2", "email"]
LABEL_CANDIDATES = ["label", "class", "target", "category", "v1", "spam"]


class DatasetError(ValueError):
    """Raised when the dataset schema is ambiguous or unusable."""


def normalize_label(value: object) -> Optional[str]:
    """Normalize a raw label to 'spam'/'ham', or None if unknown."""
    if value is None:
        return None
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return None
    except Exception:
        pass
    s = str(value).strip().lower()
    return LABEL_MAP.get(s)


def find_default_dataset() -> Optional[pathlib.Path]:
    for p in DEFAULT_DATA_PATHS:
        if p.exists() and p.is_file():
            return p
    raw_dir = PROJECT_ROOT / "data" / "raw"
    if raw_dir.exists():
        for ext in ("*.csv", "*.tsv", "*.txt"):
            for f in sorted(raw_dir.glob(ext)):
                if f.name.startswith("README"):
                    continue
                return f
    return None


def _read_raw(path: pathlib.Path) -> pd.DataFrame:
    """Read a raw file attempting likely formats. Raises DatasetError if unreadable."""
    import csv
    import re

    errors = []
    # 0. Manual UCI-style parse: lines like "<ham|spam>\\t<message>" (robust to quotes).
    for encoding in ("utf-8", "latin-1"):
        try:
            text = pathlib.Path(path).read_text(encoding=encoding)
            lines = [ln for ln in text.splitlines() if ln.strip() != ""]
            if lines:
                pat = re.compile(r"^(ham|spam)\s*\t\s*(.*)$", re.IGNORECASE)
                matched = [pat.match(ln) for ln in lines]
                frac = sum(1 for m in matched if m) / len(lines)
                if frac >= 0.9:
                    labels, messages = [], []
                    for m in matched:
                        if m:
                            labels.append(m.group(1).strip().lower())
                            messages.append(m.group(2))
                    return pd.DataFrame({"label": labels, "message": messages})
        except Exception as e:  # noqa: BLE001
            errors.append(f"manual-tsv/{encoding}: {e}")
    # 1. Try tab-separated, no header (UCI format) with QUOTE_NONE for stray quotes
    for encoding in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(
                path, sep="\t", header=None, names=["label", "message"],
                encoding=encoding, engine="python", quoting=csv.QUOTE_NONE,
                on_bad_lines="skip",
            )
            if len(df.columns) == 2 and len(df) > 0:
                labels = df["label"].astype(str).str.strip().str.lower()
                frac_known = labels.isin(list(LABEL_MAP.keys())).mean()
                if frac_known >= 0.9:
                    return df
        except Exception as e:  # noqa: BLE001
            errors.append(f"tsv/{encoding}: {e}")
    # 2. Try comma-separated with header
    for encoding in ("utf-8", "latin-1"):
        for sep in (",", ";"):
            try:
                df = pd.read_csv(path, sep=sep, encoding=encoding, engine="python")
                if len(df.columns) >= 2:
                    return df
            except Exception as e:  # noqa: BLE001
                errors.append(f"csv sep={sep}/{encoding}: {e}")
    raise DatasetError(
        f"Could not parse dataset file '{path}'. Tried TSV-no-header and CSV-with-header "
        f"(utf-8/latin-1). Details: {'; '.join(errors[:4])}"
    )


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map arbitrary columns to canonical text/label."""
    cols = list(df.columns)
    lower = {str(c).strip().lower(): c for c in cols}
    # Case A0: email triple (label, subject, body) -> text = subject + body.
    # Stored format per data/README; combined because users paste subject+body.
    if "label" in lower and "subject" in lower and "body" in lower:
        subj = lower["subject"]
        body = lower["body"]
        subj_s = df[subj].where(df[subj].notna(), "").astype(str).str.strip()
        body_s = df[body].where(df[body].notna(), "").astype(str).str.strip()
        combined = (subj_s + "\n\n" + body_s).str.strip()
        return pd.DataFrame({"label": df[lower["label"]], "text": combined})
    # Case A: already canonical-ish (UCI read gives label/message)
    if "label" in lower and "message" in lower:
        out = pd.DataFrame({
            "label": df[lower["label"]],
            "text": df[lower["message"]],
        })
        return out
    if "label" in lower and "text" in lower:
        return pd.DataFrame({"label": df[lower["label"]], "text": df[lower["text"]]})
    # Case B: generic header — find candidates
    label_col = next((lower[c] for c in LABEL_CANDIDATES if c in lower), None)
    text_col = next((lower[c] for c in TEXT_CANDIDATES if c in lower), None)
    if label_col is not None and text_col is not None:
        return pd.DataFrame({"label": df[label_col], "text": df[text_col]})
    # Case C: exactly 2 columns, assume [label, text]
    if len(cols) == 2:
        return pd.DataFrame({"label": df[cols[0]], "text": df[cols[1]]})
    # Case D: >2 columns (e.g. Kaggle spam.csv has Unnamed: 2..4 extras): use first two
    if len(cols) > 2:
        first, second = cols[0], cols[1]
        # Heuristic: label column should have few unique values
        if df[first].nunique(dropna=True) <= 10:
            return pd.DataFrame({"label": df[first], "text": df[second]})
        raise DatasetError(
            f"Ambiguous dataset schema: columns={cols}. Could not identify which "
            f"column is the label and which is the message text. Expected a label "
            f"column like {LABEL_CANDIDATES} and a text column like {TEXT_CANDIDATES}."
        )
    raise DatasetError(
        f"Ambiguous dataset schema: columns={cols}. Need a label column and a text column."
    )


def load_dataset(path: Optional[str | pathlib.Path] = None) -> Tuple[pd.DataFrame, Dict]:
    """Load and validate dataset into canonical schema.

    Returns (clean_df, report) where clean_df has columns [text, label]
    with labels in {'spam','ham'}, and report documents row counts,
    missing values, duplicates, label counts, and removed rows.
    """
    if path is None:
        found = find_default_dataset()
        if found is None:
            raise FileNotFoundError(
                "No dataset found. Place the UCI SMS Spam Collection file named "
                "'SMSSpamCollection' (tab-separated, no header) in data/raw/. "
                "See data/README.md for download instructions. "
                f"Searched: {[str(p) for p in DEFAULT_DATA_PATHS]}"
            )
        path = found
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {path}. See data/README.md for setup instructions."
        )

    raw = _read_raw(path)
    total_rows = len(raw)
    mapped = _map_columns(raw)

    missing_label = mapped["label"].isna().sum()
    missing_text = mapped["text"].isna().sum()

    # Normalize labels
    mapped["label_norm"] = mapped["label"].apply(normalize_label)
    unknown_label = mapped["label_norm"].isna().sum()
    if total_rows > 0 and unknown_label / total_rows >= 0.5:
        raise DatasetError(
            f"Ambiguous dataset schema: {unknown_label}/{total_rows} label values "
            f"could not be mapped to spam/ham (sample: "
            f"{mapped['label'].astype(str).unique()[:5].tolist()}). Expected a label "
            f"column like {LABEL_CANDIDATES} with values spam/ham."
        )

    # Normalize text: coerce to str, strip
    mapped["text_norm"] = mapped["text"].astype(str)
    # pandas turns NaN into 'nan' string; restore empties
    was_na = mapped["text"].isna()
    mapped.loc[was_na, "text_norm"] = ""
    mapped["text_norm"] = mapped["text_norm"].str.strip()
    # Remove literal 'nan' artifacts from None coercion edge cases
    empty_text = (mapped["text_norm"] == "").sum()

    # Duplicates on (label_norm, text_norm)
    dup_mask = mapped.duplicated(subset=["label_norm", "text_norm"], keep="first")
    duplicates = int(dup_mask.sum())

    clean = mapped.loc[
        mapped["label_norm"].notna() & (mapped["text_norm"] != ""),
        ["label_norm", "text_norm"],
    ].copy()
    clean = clean.drop_duplicates(subset=["label_norm", "text_norm"], keep="first")
    clean = clean.rename(columns={"label_norm": "label", "text_norm": "text"})
    clean = clean[["text", "label"]].reset_index(drop=True)

    removed = total_rows - len(clean)
    label_counts = clean["label"].value_counts().to_dict()
    report: Dict = {
        "source_path": str(path),
        "total_rows": int(total_rows),
        "missing_label": int(missing_label),
        "missing_text": int(missing_text),
        "unknown_label": int(unknown_label),
        "empty_text": int(empty_text),
        "duplicates": int(duplicates),
        "removed_rows": int(removed),
        "kept_rows": int(len(clean)),
        "label_counts": {str(k): int(v) for k, v in label_counts.items()},
    }
    if len(clean) == 0:
        raise DatasetError(
            f"Dataset '{path}' yielded 0 usable rows after validation. "
            f"Report: {report}. Check columns/labels per data/README.md."
        )
    if set(label_counts.keys()) - {"spam", "ham"}:
        raise DatasetError(f"Unexpected labels after normalization: {label_counts}")
    return clean, report


def dataset_stats(df: pd.DataFrame) -> Dict:
    """Quick stats for an already-canonical DataFrame."""
    return {
        "rows": int(len(df)),
        "missing_text": int(df["text"].isna().sum()),
        "missing_label": int(df["label"].isna().sum()),
        "duplicates": int(df.duplicated(subset=["text", "label"]).sum()),
        "label_counts": {str(k): int(v) for k, v in df["label"].value_counts().to_dict().items()},
    }
