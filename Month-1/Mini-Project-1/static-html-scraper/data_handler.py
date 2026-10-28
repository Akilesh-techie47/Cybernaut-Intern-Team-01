"""
Data Handling — Cleaning + CSV Export.

This module mirrors the Selenium project's data_handler.py so both scrapers
produce **identical CSV schemas**.  The same downstream pipeline (analysis,
dashboards, concatenation) can consume output from either project without
any schema-aware branching.

Key functions:
  • parse_numeric()  — strips $, %, commas, and multiplier suffixes.
  • clean_data()     — builds a DataFrame with raw + cleaned numeric columns
                       and a Timestamp column for historical append-mode logging.
  • apply_filters()  — optional price/top-gainers filtering.
  • save_to_csv()    — append-mode writer that creates dir/header on first run.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─── Numeric Parsing ────────────────────────────────────────────────────────────

def parse_numeric(val: str) -> float:
    """
    Clean currency/percentage strings into float values.

    Handles:
      • Dollar signs, commas, percent signs  ($1,234.56  →  1234.56)
      • Multiplier suffixes: T (trillion), B (billion), M (million), K (thousand)
      • Sign prefixes (+/-) and the string "N/A"
    """
    if not val or val == "N/A" or pd.isna(val):
        return 0.0

    val_str = str(val).strip().replace("$", "").replace(",", "").replace("%", "")

    # Handle multiplier suffixes
    multiplier = 1.0
    if val_str[-1:].upper() == "T":
        multiplier = 1e12
        val_str = val_str[:-1]
    elif val_str[-1:].upper() == "B":
        multiplier = 1e9
        val_str = val_str[:-1]
    elif val_str[-1:].upper() == "M":
        multiplier = 1e6
        val_str = val_str[:-1]
    elif val_str[-1:].upper() == "K":
        multiplier = 1e3
        val_str = val_str[:-1]

    try:
        return float(val_str) * multiplier
    except ValueError:
        logger.warning(f"Could not parse numeric value from '{val}'")
        return 0.0


# ─── Data Cleaning ──────────────────────────────────────────────────────────────

def clean_data(raw_list: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert raw scraped dicts into a clean DataFrame.

    Adds:
      • ``Clean_Price``, ``Clean_24h_Change``, ``Clean_Market_Cap`` — float
        columns derived from the display-string originals.
      • ``Timestamp`` — ISO-ish string for historical logging.

    Column order matches the Selenium project exactly so CSVs from both
    scrapers can be concatenated without transformation.
    """
    if not raw_list:
        logger.warning("Empty raw data list passed to clean_data.")
        return pd.DataFrame()

    df = pd.DataFrame(raw_list)

    # Numeric shadow columns for calculations / filtering
    df["Clean_Price"] = df["Price"].apply(parse_numeric)
    df["Clean_24h_Change"] = df["24h_Change"].apply(parse_numeric)
    df["Clean_Market_Cap"] = df["Market_Cap"].apply(parse_numeric)

    # Execution timestamp for historical append-mode logging
    df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Canonical column order (same as Selenium project)
    columns_order = [
        "Timestamp",
        "Rank",
        "Name",
        "Symbol",
        "Price",
        "Clean_Price",
        "24h_Change",
        "Clean_24h_Change",
        "Market_Cap",
        "Clean_Market_Cap",
    ]
    cols_to_use = [col for col in columns_order if col in df.columns]
    df = df[cols_to_use]

    logger.info("Cleaned and structured scraped data into pandas DataFrame.")
    return df


# ─── Optional Filters ───────────────────────────────────────────────────────────

def apply_filters(
    df: pd.DataFrame,
    threshold: Optional[float] = None,
    top_gainers: bool = False,
) -> pd.DataFrame:
    """Apply optional price-floor and top-gainers-only filters."""
    if df.empty:
        return df

    filtered = df.copy()

    if threshold is not None:
        logger.info(f"Applying price filter: Price >= ${threshold:.2f}")
        filtered = filtered[filtered["Clean_Price"] >= threshold]

    if top_gainers:
        logger.info("Applying top gainers filter: 24h Change > 0%")
        filtered = filtered[filtered["Clean_24h_Change"] > 0]

    logger.info(f"DataFrame filtered down to {len(filtered)} rows.")
    return filtered


# ─── CSV Export ──────────────────────────────────────────────────────────────────

def save_to_csv(df: pd.DataFrame, csv_path: str) -> None:
    """
    Append DataFrame rows to a CSV file.

    • Creates the parent directory if it doesn't exist.
    • Writes a header row only on the first write.
    • Subsequent runs *append* new rows (historical logging), never overwrite.
    """
    if df.empty:
        logger.warning("No data available to save to CSV.")
        return

    dir_name = os.path.dirname(csv_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
        logger.info(f"Created output directory: {dir_name}")

    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0

    df.to_csv(csv_path, mode="a", index=False, header=not file_exists)
    action = "Appended" if file_exists else "Created & saved"
    logger.info(f"{action} {len(df)} records to CSV at: {csv_path}")
