import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def parse_numeric(val: str) -> float:
    """Helper function to clean currency/percentage strings into float values."""
    if not val or val == "N/A" or pd.isna(val):
        return 0.0

    # Ensure string type
    val_str = str(val).strip().replace("$", "").replace(",", "").replace("%", "")

    # Handle multipliers if present (T for trillion, B for billion, M for million, K for thousand)
    multiplier = 1.0
    if val_str.endswith("T") or val_str.endswith("t"):
        multiplier = 1e12
        val_str = val_str[:-1]
    elif val_str.endswith("B") or val_str.endswith("b"):
        multiplier = 1e9
        val_str = val_str[:-1]
    elif val_str.endswith("M") or val_str.endswith("m"):
        multiplier = 1e6
        val_str = val_str[:-1]
    elif val_str.endswith("K") or val_str.endswith("k"):
        multiplier = 1e3
        val_str = val_str[:-1]

    try:
        return float(val_str) * multiplier
    except ValueError:
        logger.warning(f"Could not parse numeric value from '{val}'")
        return 0.0


def clean_data(raw_list: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Strips symbols ($, ,, %), converts values to proper numeric types,
    and adds an execution Timestamp column.
    """
    if not raw_list:
        logger.warning("Empty raw data list passed to clean_data.")
        return pd.DataFrame()

    df = pd.DataFrame(raw_list)

    # Preserve raw display strings while adding numeric columns for calculations/filtering
    df["Clean_Price"] = df["Price"].apply(parse_numeric)
    df["Clean_24h_Change"] = df["24h_Change"].apply(parse_numeric)
    df["Clean_Market_Cap"] = df["Market_Cap"].apply(parse_numeric)

    # Standard Timestamp for historical logging
    df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Reorder columns cleanly
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
    
    # Keep only existing columns
    cols_to_use = [col for col in columns_order if col in df.columns]
    df = df[cols_to_use]

    logger.info("Successfully cleaned and structured scraped data into pandas DataFrame.")
    return df


def apply_filters(
    df: pd.DataFrame,
    threshold: Optional[float] = None,
    top_gainers: bool = False
) -> pd.DataFrame:
    """Applies optional filtering logic on the DataFrame."""
    if df.empty:
        return df

    filtered_df = df.copy()

    if threshold is not None:
        logger.info(f"Applying price filter: Price >= ${threshold:.2f}")
        filtered_df = filtered_df[filtered_df["Clean_Price"] >= threshold]

    if top_gainers:
        logger.info("Applying top gainers filter: 24h Change > 0%")
        filtered_df = filtered_df[filtered_df["Clean_24h_Change"] > 0]

    logger.info(f"DataFrame filtered down to {len(filtered_df)} rows.")
    return filtered_df


def save_to_csv(df: pd.DataFrame, csv_path: str) -> None:
    """
    Appends DataFrame rows with a timestamp column;
    creates target directory and CSV header if the file does not exist yet.
    """
    if df.empty:
        logger.warning("No data available to save to CSV.")
        return

    # Ensure parent directory exists
    dir_name = os.path.dirname(csv_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
        logger.info(f"Created output directory: {dir_name}")

    # Check if CSV file already exists and is non-empty
    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0

    # Write in append mode
    df.to_csv(csv_path, mode="a", index=False, header=not file_exists)
    action = "Appended" if file_exists else "Created & saved"
    logger.info(f"{action} {len(df)} records to CSV at: {csv_path}")
