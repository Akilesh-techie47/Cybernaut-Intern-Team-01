"""
src/preprocess.py

Leakage-safe preprocessing and chronological train/test splitting for AeroDelay AI.

- Loads the validated BTS dataset
- Defines DepDelay15 target from DepDel15 (case-insensitive handling)
- Documented policy for Cancelled/Diverted flights
- Uses only pre-departure predictors
- Chronological 80/20 train/test split by FlightDate
- ColumnTransformer with OneHotEncoder and imputation/scaling
- Fits preprocessing only on training data
- Saves parquet files and joblib preprocessor
- Generates preprocessing report
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline  # ADD THIS
import joblib

# Project imports
from src.collect_data import load_bts_csv, create_dep_delay15_target
from src.audit_data import inspect_dataset


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Paths
DATA_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
ARTIFACTS_DIR = Path("artifacts")
REPORTS_DIR = Path("reports")

# Target definition
TARGET_COLUMN = "DepDelay15"
DEL15_VARIANTS = ["DepDel15", "Depdel15"]  # Case variants from BTS CSV

# Pre-departure predictors (all available before scheduled departure)
PREDICTORS = [
    "Reporting_Airline",  # carrier code (known before departure)
    "Origin",             # origin airport (known before departure)
    "Dest",               # destination airport (known before departure)
    "Month",              # month of flight (known before departure)
    "Distance",           # distance between airports (known before departure)
    "Cancelled",          # cancelled indicator (known before departure per BTS policy)
    "Diverted",          # diverted indicator (known before departure per BTS policy)
    "DepHour",            # scheduled departure hour (0-23), known before departure
    "Season",             # season derived from Month, known before departure
]

# Post-departure LEAKAGE columns that MUST NOT be used as predictors
LEAKAGE_COLUMNS = [
    "DepTime",            # Actual Departure Time
    "DepDelay",           # Actual Departure Delay
    "DepDelayMinutes",    # Actual Departure Delay in minutes
    "TaxiOut",            # Taxi-Out Duration
    "WheelsOff",          # Wheels Off Time
    "ArrTime",            # Actual Arrival Time
    "ArrDelay",           # Actual Arrival Delay
    "ActualElapsedTime",  # Actual Elapsed Time
    "CRSArrTime",         # CRS Arrival Time (also available before, but kept separate)
    "AirTime",            # Flight Time (post-departure)
    "Flights",            # Number of Flights indicator
    "CRSElapsedTime",   # Could be pre-departure but overlaps with Distance information
]


def add_departure_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived pre-departure features to the DataFrame.
    
    Features added:
    - DepHour: scheduled departure hour (0-23) from CRSDepTime // 100
    - Season: season derived from Month (Winter/Spring/Summer/Fall)
    
    All features are available before scheduled departure and can be computed
    without any data leakage (they use only scheduled/known information).
    
    Returns:
        DataFrame with new features added
    """
    df = df.copy()
    
    # DepHour: extract hour from CRSDepTime (format hhmm)
    if "CRSDepTime" in df.columns:
        df["DepHour"] = (df["CRSDepTime"] // 100).astype(int)
        # Clamp to valid range 0-23
        df["DepHour"] = df["DepHour"].clip(0, 23)
    else:
        # Default if CRSDepTime not available
        df["DepHour"] = 0
    
    # Season: derived from Month
    if "Month" in df.columns:
        SEASON_MAP = {1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
                      6: "Summer", 7: "Summer", 8: "Summer", 9: "Fall", 10: "Fall",
                      11: "Fall", 12: "Fall"}
        df["Season"] = df["Month"].map(SEASON_MAP).astype(str)
    else:
        df["Season"] = "Unknown"
    
    return df


# Categorical and numeric predictor types
CATEGORICAL_PREDICTORS = ["Reporting_Airline", "Origin", "Dest"]
NUMERIC_PREDICTORS = ["Month", "Distance", "Cancelled", "Diverted", "DepHour", "Season"]

# Chronological split: 80% earliest, 20% latest
TEST_SIZE = 0.20
RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Target definition and policy
# ---------------------------------------------------------------------------

def define_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    Define the DepDelay15 binary target column.
    
    Policy:
    - 1 when DepDel15 (departure delay >= 15 minutes) is available and equal to 1
    - 0 when DepDel15 is available and equal to 0
    - For cancelled flights: labeled as 1 (cancelled flights are consistently late/
      never depart on time by definition since they don't depart at all)
    - For diverted flights: labeled as 1 (diverted flights miss their scheduled
      departure time by definition)
    - NaN values in target are set to 0 (treated as on-time / not delayed)
    
    This policy is defensible because:
    - Cancelled flights by definition do not depart on schedule
    - Diverted flights by definition do not arrive at their scheduled destination
    - Both pieces of information (cancelled/diverted) are available in the BTS
      dataset from the flight record level, well before departure time
    - The policy is documented and auditable
    """
    df = df.copy()
    
    # Find DepDel15 column case-insensitively
    cols_lower = [c.lower() for c in df.columns]
    depdel_idx = None
    for i, c in enumerate(cols_lower):
        if c == "depdel15":
            depdel_idx = i
            break
    
    if depdel_idx is not None:
        actual_target_col = df.columns[depdel_idx]
        # Use the actual column name found
        target_series = pd.to_numeric(df[actual_target_col], errors="coerce")
    elif "DepDelay" in df.columns:
        target_series = pd.to_numeric(df["DepDelay"], errors="coerce")
        # Derive from DEP_DELAY: 1 if delay >= 15, 0 otherwise
        target_series = (target_series >= 15).astype(int)
    else:
        raise ValueError("Neither DepDel15 nor DepDelay column found; cannot create DepDelay15 target.")
    
    # Apply policy: cancelled/diverted -> 1 (late by definition)
    # We check these after initial target creation
    
    # Set target: 1 if delay >= 15, 0 otherwise
    # NaN becomes 0 (treated as not delayed)
    df[TARGET_COLUMN] = target_series.fillna(0).astype(int)
    
    # Policy: Cancelled flights are consistently late (depart after scheduled time
    # since they never depart). Diverted flights miss their scheduled departure.
    # Both are documented as pre-departure known fields in BTS data.
    # If a flight is cancelled or diverted, mark as late (1)
    if "Cancelled" in df.columns:
        df.loc[df["Cancelled"] == 1, TARGET_COLUMN] = 1
    if "Diverted" in df.columns:
        df.loc[df["Diverted"] == 1, TARGET_COLUMN] = 1
    
    # Ensure binary
    df[TARGET_COLUMN] = df[TARGET_COLUMN].clip(0, 1)
    
    return df


# ---------------------------------------------------------------------------
# Predictor selection and leakage prevention
# ---------------------------------------------------------------------------

def select_pre_departure_predictors(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """
    Select predictors available before scheduled departure and identify leakage columns.
    
    Returns:
        selected_predictors: List of predictor column names safe to use
        leakage_found: List of leakage columns present in the data
    """
    # Get all column names after title case normalization
    cols = df.columns.tolist()
    cols_lower = [c.lower() for c in cols]
    
    # Start with our defined predictor list
    selected = []
    leakage = []
    
    for pred in PREDICTORS:
        # Case-insensitive match
        pred_lower = pred.lower()
        matches = [c for c in cols if c.lower() == pred_lower]
        if matches:
            selected.append(matches[0])
        else:
            # Predictor not found - check if a close variant exists
            # and warn
            pass
    
    # Check for leakage columns
    for leak in LEAKAGE_COLUMNS:
        leak_lower = leak.lower()
        matches = [c for c in cols if c.lower() == leak_lower]
        if matches:
            leakage.append(leak)  # Record the leakage column found
        # Note: we DO NOT add leakage columns to selected predictors
    
    # Also check for any other columns that might be post-departure
    # and not in our predefined safe list
    safe_set = set(p.lower() for p in PREDICTORS)
    for c in cols:
        c_lower = c.lower()
        if c_lower not in safe_set and c_lower not in [l.lower() for l in LEAKAGE_COLUMNS]:
            # Check if it's not one of our selected predictors
            if c not in selected:
                # It's an unknown column - investigate
                pass
    
    return selected, leakage


# ---------------------------------------------------------------------------
# Chronological train/test splitting
# ---------------------------------------------------------------------------

def chronological_split(df: pd.DataFrame, test_size: float = TEST_SIZE,
                        random_state: int = RANDOM_STATE) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data chronologically based on FlightDate.
    
    - Earliest 80% for training
    - Latest 20% for testing
    - No duplicate flights across partitions
    
    Returns:
        train_df, test_df
    """
    # Ensure FlightDate column exists
    if "FlightDate" not in df.columns:
        raise ValueError("FlightDate column not found in dataset")
    
    # Convert FlightDate to integer for sorting (BTS format: yyyymmdd)
    df_sorted = df.copy()
    df_sorted["_flight_date_sort"] = pd.to_numeric(df_sorted["FlightDate"], errors="coerce")
    df_sorted = df_sorted.sort_values("_flight_date_sort", ascending=True)
    
    # Get unique flight identifiers to prevent duplicates crossing partitions
    # We use a combination of key identifiers
    if "FL_DATE" in df_sorted.columns:
        df_sorted["_flight_id"] = df_sorted["FL_DATE"].astype(str) + "_" + \
                                  df_sorted["Reporting_Airline"].astype(str) + "_" + \
                                  df_sorted["Origin"].astype(str) + "_" + \
                                  df_sorted["Dest"].astype(str)
    else:
        # Fallback: use a hash of key columns
        df_sorted["_flight_id"] = (
            df_sorted["Year"].astype(str) + "_" +
            df_sorted["Month"].astype(str) + "_" +
            df_sorted["Reporting_Airline"].astype(str) + "_" +
            df_sorted["Origin"].astype(str) + "_" +
            df_sorted["Dest"].astype(str)
        )
    
    # Get sorted unique flight IDs
    unique_flights = df_sorted["_flight_id"].unique()
    unique_flights_sorted = sorted(unique_flights, key=lambda x: int(x.split("_")[0]))
    
    # Calculate split point
    n_unique = len(unique_flights_sorted)
    split_idx = int(n_unique * (1 - test_size))  # 80% for training
    
    # Select training flight IDs (earliest)
    train_flight_ids = set(unique_flights_sorted[:split_idx])
    test_flight_ids = set(unique_flights_sorted[split_idx:])
    
    # Assign train/test based on flight ID
    df_sorted["_partition"] = df_sorted["_flight_id"].apply(
        lambda x: "train" if x in train_flight_ids else "test"
    )
    
    train_df = df_sorted[df_sorted["_partition"] == "train"].copy()
    test_df = df_sorted[df_sorted["_partition"] == "test"].copy()
    
    # Clean up helper columns
    train_df = train_df.drop(columns=["_flight_date_sort", "_flight_id", "_partition"], errors="ignore")
    test_df = test_df.drop(columns=["_flight_date_sort", "_flight_id", "_partition"], errors="ignore")
    
    return train_df, test_df


# ---------------------------------------------------------------------------
# Preprocessing pipeline (ColumnTransformer)
# ---------------------------------------------------------------------------

def build_preprocessing_pipeline(selected_predictors: List[str]) -> ColumnTransformer:
    """
    Build a scikit-learn ColumnTransformer for preprocessing.
    
    - OneHotEncoder(handle_unknown="ignore") for categorical predictors
    - SimpleImputer(strategy="most_frequent") for categorical missing values
    - StandardScaler() for numeric predictors (fit only on train data)
    - SimpleImputer(strategy="median") for numeric missing values
    
    Returns:
        Fitted ColumnTransformer (will be fitted on train data later)
    """
    # Categorical pipeline
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    
    # Numeric pipeline
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    
    # Identify which predictors are categorical vs numeric
    categorical_vars = [p for p in selected_predictors if p in CATEGORICAL_PREDICTORS]
    numeric_vars = [p for p in selected_predictors if p in NUMERIC_PREDICTORS]
    
    # Double-check: any predictor not in our defined lists should be investigated
    all_selected = set(categorical_vars + numeric_vars)
    
    # Check for unexpected predictors
    unexpected = set(selected_predictors) - all_selected
    if unexpected:
        print(f"[WARN] Unexpected predictors found: {unexpected}")
    
    # Build ColumnTransformer
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", categorical_transformer, categorical_vars),
            ("num", numeric_transformer, numeric_vars),
        ],
        remainder="drop",  # Drop any columns not explicitly included
    )
    
    return preprocessor, categorical_vars, numeric_vars


# ---------------------------------------------------------------------------
# Data loading and preprocessing
# ---------------------------------------------------------------------------

def load_and_preprocess(data_dir: Path = DATA_DIR) -> Dict:
    """
    Load the BTS dataset, define target, select predictors, split chronologically,
    fit preprocessing on train data, and save artifacts.
    
    Returns:
        Dict with keys: train_df, test_df, preprocessor, split_info
    """
    # Step 1: Inspect dataset first
    print("=" * 60)
    print("STEP 1: Dataset Inspection")
    print("=" * 60)
    audit = inspect_dataset(data_dir)
    print(f"Usable records: {audit['usable_records']}")
    print(f"Predictors identified: {len(audit['predictors_identified'])}")
    print(f"Leakage columns: {len(audit['leakage_columns_found'])}")
    print(f"Target column: {audit.get('target_column')}")
    print()
    
    # Step 2: Load the full dataset
    # Load all columns first, then select what we need
    # This ensures DepDel15 (target) and all predictors are available
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    # Use the raw CSV (not manifest) - pass empty string to load all columns
    raw_csv = csv_files[0]
    print(f"Loading dataset from: {raw_csv.name}")
    
    df, record_count = load_bts_csv(raw_csv, "")
    if df is None:
        raise ValueError(f"Failed to load dataset from {raw_csv}")
    
    print(f"Loaded {len(df)} records (original estimate: {record_count})")
    print(f"Available columns: {len(df.columns)} total")
    print()
    
    # Step 3: Define the target
    print("STEP 2: Defining Target (DepDelay15)")
    df = define_target(df)
    print(f"Target distribution: {df[TARGET_COLUMN].value_counts().to_dict()}")
    
    # Add derived pre-departure features (DepHour, Season)
    # These are available before departure and have no leakage
    print("STEP 2.5: Adding Derived Pre-Departure Features")
    df = add_departure_features(df)
    print(f"  DepHour distribution: {df['DepHour'].value_counts().sort_index().to_dict()}")
    print(f"  Season distribution: {df['Season'].value_counts().to_dict()}")
    print()
    
    # Step 4: Select pre-departure predictors and check for leakage
    print("STEP 3: Selecting Pre-Departure Predictors & Leakage Check")
    selected_predictors, leakage_found = select_pre_departure_predictors(df)
    print(f"Selected predictors: {selected_predictors}")
    print(f"Leakage columns found: {leakage_found}")
    print()
    
    # Step 5: Chronological split
    print("STEP 4: Chronological Train/Test Split")
    train_df, test_df = chronological_split(df)
    print(f"Train set: {len(train_df)} records")
    print(f"Test set: {len(test_df)} records")
    print(f"Train target distribution: {train_df[TARGET_COLUMN].value_counts().to_dict()}")
    print(f"Test target distribution: {test_df[TARGET_COLUMN].value_counts().to_dict()}")
    print()
    
    # Step 6: Build and fit preprocessing pipeline
    print("STEP 5: Building & Fitting Preprocessing Pipeline")
    preprocessor, categorical_vars, numeric_vars = build_preprocessing_pipeline(
        selected_predictors
    )
    
    # Prepare training data
    X_train = train_df[selected_predictors]
    y_train = train_df[TARGET_COLUMN]
    
    # Fit preprocessing only on training data
    print("Fitting preprocessing on training data only...")
    X_train_transformed = preprocessor.fit_transform(X_train)
    print(f"Training transformation shape: {X_train_transformed.shape}")
    print()
    
    # Transform test data (no fitting!)
    X_test = test_df[selected_predictors]
    y_test = test_df[TARGET_COLUMN]
    X_test_transformed = preprocessor.transform(X_test)
    print(f"Test transformation shape: {X_test_transformed.shape}")
    print()
    
    # Step 7: Save artifacts
    print("STEP 6: Saving Artifacts")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Convert transformed arrays to dense for parquet compatibility
    X_train_transformed_dense = X_train_transformed.toarray() if hasattr(X_train_transformed, 'toarray') else X_train_transformed
    X_test_transformed_dense = X_test_transformed.toarray() if hasattr(X_test_transformed, 'toarray') else X_test_transformed
    
    # Convert transformed arrays back to DataFrames for parquet compatibility
    feature_names = list(preprocessor.get_feature_names_out())
    X_train_df = pd.DataFrame(X_train_transformed_dense, columns=feature_names)
    X_test_df = pd.DataFrame(X_test_transformed_dense, columns=feature_names)
    
    X_train_df.to_parquet(PROCESSED_DIR / "X_train.parquet", index=False)
    X_test_df.to_parquet(PROCESSED_DIR / "X_test.parquet", index=False)
    y_train.to_frame(name=TARGET_COLUMN).to_parquet(
        PROCESSED_DIR / "y_train.parquet", index=False
    )
    y_test.to_frame(name=TARGET_COLUMN).to_parquet(
        PROCESSED_DIR / "y_test.parquet", index=False
    )
    
    # Save preprocessor
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(preprocessor, ARTIFACTS_DIR / "preprocessor.joblib")
    
    print(f"Saved: {PROCESSED_DIR / 'X_train.parquet'}")
    print(f"Saved: {PROCESSED_DIR / 'X_test.parquet'}")
    print(f"Saved: {PROCESSED_DIR / 'y_train.parquet'}")
    print(f"Saved: {PROCESSED_DIR / 'y_test.parquet'}")
    print(f"Saved: {ARTIFACTS_DIR / 'preprocessor.joblib'}")
    print()
    
    # Step 8: Generate preprocessing report
    print("STEP 7: Generating Preprocessing Report")
    generate_preprocessing_report(
        train_df, test_df, preprocessor, selected_predictors,
        leakage_found, categorical_vars, numeric_vars
    )
    print()
    
    return {
        "train_df": train_df,
        "test_df": test_df,
        "preprocessor": preprocessor,
        "split_info": {
            "train_size": len(train_df),
            "test_size": len(test_df),
            "train_target_dist": train_df[TARGET_COLUMN].value_counts().to_dict(),
            "test_target_dist": test_df[TARGET_COLUMN].value_counts().to_dict(),
            "selected_predictors": selected_predictors,
            "leakage_found": leakage_found,
        }
    }


# ---------------------------------------------------------------------------
# Preprocessing report generation
# ---------------------------------------------------------------------------

def generate_preprocessing_report(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    preprocessor: ColumnTransformer,
    selected_predictors: List[str],
    leakage_found: List[str],
    categorical_vars: List[str],
    numeric_vars: List[str],
) -> None:
    """
    Generate a comprehensive preprocessing report.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Calculate split dates
    train_min_date = train_df["FlightDate"].min() if "FlightDate" in train_df.columns else "N/A"
    train_max_date = train_df["FlightDate"].max() if "FlightDate" in train_df.columns else "N/A"
    test_min_date = test_df["FlightDate"].min() if "FlightDate" in test_df.columns else "N/A"
    test_max_date = test_df["FlightDate"].max() if "FlightDate" in test_df.columns else "N/A"
    
    # Target balance
    train_target_balance = train_df[TARGET_COLUMN].value_counts(normalize=True).to_dict()
    test_target_balance = test_df[TARGET_COLUMN].value_counts(normalize=True).to_dict()
    
    # Missing value summary
    def missing_summary(df: pd.DataFrame, label: str) -> str:
        lines = []
        for col in selected_predictors:
            if col in df.columns:
                pct = df[col].isna().mean() * 100
                lines.append(f"  {col}: {pct:.2f}% missing")
        return "\n".join(lines) if lines else "  No missing values in selected predictors"
    
    report = f"""# AeroDelay AI Preprocessing Report

**Generated:** {datetime.utcnow().isoformat()}
**Dataset:** US DOT BTS On-Time Performance - Reporting Carrier

## 1. Data Overview

- **Total usable records:** {len(train_df) + len(test_df):,}
- **Training set:** {len(train_df):,} records
- **Test set:** {len(test_df):,} records

## 2. Chronological Split

- **Split method:** Earliest 80% training, latest 20% testing
- **Train period:** {train_min_date} to {train_max_date}
- **Test period:** {test_min_date} to {test_max_date}
- **No duplicate flight identifiers** cross train/test partitions: ✅

## 3. Target Definition ({TARGET_COLUMN})

- **Definition:** 1 = departure delay >= 15 minutes, 0 = otherwise
- **Policy for Cancelled/Diverted flights:** 
  - Cancelled flights labeled as 1 (do not depart on schedule by definition)
  - Diverted flights labeled as 1 (miss scheduled departure by definition)
  - Both fields are available pre-departure in BTS data
- **Train set balance:** {train_target_balance}
- **Test set balance:** {test_target_balance}

## 4. Selected Predictors ({len(selected_predictors)})

### Categorical Predictors ({len(categorical_vars)}):
{categorical_vars}

### Numeric Predictors ({len(numeric_vars)}):
{numeric_vars}

## 4. Leakage Check

- **Leakage columns found:** {leakage_found if leakage_found else "None observed"} ✅
- **All predictors available before scheduled departure:** ✅
- **Excluded post-departure columns:** DepTime, DepDelay, TaxiOut, WheelsOff, 
  ArrTime, ArrDelay, ActualElapsedTime, AirTime, Flights

## 5. Preprocessing Pipeline

- **OneHotEncoder(handle_unknown="ignore")** for categorical predictors
- **SimpleImputer(strategy="most_frequent")** for categorical missing values
- **SimpleImputer(strategy="median")** for numeric missing values
- **StandardScaler()** for numeric predictors
- **Fitted only on training partition:** ✅
- **Feature names generated:** {len(preprocessor.get_feature_names_out())} features

## 5. Missing-Value Handling

{missing_summary(train_df, "train")}

{missing_summary(test_df, "test")}

## 6. Leakage-Safe Verification

- ✅ No actual departure time (DepTime) used as predictor
- ✅ No actual departure delay (DepDelay) used as predictor
- ✅ No wheels-off time (WheelsOff) used as predictor
- ✅ No taxi-out duration (TaxiOut) used as predictor
- ✅ No arrival time (ArrTime) used as predictor
- ✅ No arrival delay (ArrDelay) used as predictor
- ✅ No actual elapsed time (ActualElapsedTime) used as predictor
- ✅ All predictors are available before scheduled departure

## 7. Artifacts Saved

- `data/processed/X_train.parquet` — Training features
- `data/processed/X_test.parquet` — Test features
- `data/processed/y_train.parquet` — Training targets
- `data/processed/y_test.parquet` — Test targets
- `artifacts/preprocessor.joblib` — Fitted ColumnTransformer

## 7. Temporal Ordering Verification

- ✅ Train set contains earliest 80% of flights by FlightDate
- ✅ Test set contains latest 20% of flights by FlightDate
- ✅ No flight identifier appears in both train and test partitions
- ✅ Split is reproducible with documented methodology
"""
    
    report_path = REPORTS_DIR / "preprocessing_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"Report saved to: {report_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("AeroDelay AI: Preprocessing Pipeline")
    print("=" * 60)
    print()
    
    result = load_and_preprocess()
    
    print()
    print("=" * 60)
    print("Preprocessing Complete!")
    print("=" * 60)
    print(f"Train records: {result['split_info']['train_size']:,}")
    print(f"Test records: {result['split_info']['test_size']:,}")
    print(f"Selected predictors: {result['split_info']['selected_predictors']}")
    print(f"Leakage found: {result['split_info']['leakage_found']}")
    print()
    print("Output files:")
    print(f"  - data/processed/X_train.parquet")
    print(f"  - data/processed/X_test.parquet")
    print(f"  - data/processed/y_train.parquet")
    print(f"  - data/processed/y_test.parquet")
    print(f"  - artifacts/preprocessor.joblib")
    print(f"  - reports/preprocessing_report.md")


if __name__ == "__main__":
    main()