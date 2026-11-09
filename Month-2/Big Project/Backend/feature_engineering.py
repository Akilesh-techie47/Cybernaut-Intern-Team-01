"""
Feature engineering for AeroDelay AI delay-risk prediction.

Adds pre-departure features while ensuring no data leakage across temporal splits.
All features are available before the scheduled departure time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

# Project imports
from src.preprocess import define_target, select_pre_departure_predictors


# ---------------------------------------------------------------------------
# Day-of-week and seasonality (available before departure)
# ---------------------------------------------------------------------------

def add_day_of_week_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add day-of-week features from the BTS dataset.

    The BTS dataset includes a DayOfWeek column (1=Monday, 7=Sunday)
    that is available before departure.

    Returns:
        DataFrame with new day-of-week features.
    """
    df = df.copy()

    if "DayOfWeek" in df.columns:
        # Keep as-is (1=Monday through 7=Sunday)
        df["dow"] = df["DayOfWeek"].astype(int)
    else:
        # Derive from FlightDate if available
        if "FlightDate" in df.columns:
            df["FlightDate"] = pd.to_numeric(df["FlightDate"], errors="coerce")
            # BTS FlightDate format: yyyymmdd
            # This is a rough derivation; DayOfWeek is preferred
            df["dow"] = df["FlightDate"].map(
                lambda x: (x // 10000) % 7 + 1 if pd.notna(x) else 1
            )
            df["dow"] = df["dow"].clip(1, 7).astype(int)
        else:
            df["dow"] = 1  # default

    # One-hot encode day of week (drop first to avoid multicollinearity)
    dow_dummies = pd.get_dummies(df["dow"], prefix="dow", drop_first=True)
    df = pd.concat([df, dow_dummies], axis=1)

    return df


def add_seasonality_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add seasonality features derived from month.

    Season is available before departure and captures seasonal travel patterns.

    Returns:
        DataFrame with new seasonality features.
    """
    df = df.copy()

    if "Month" in df.columns:
        SEASON_MAP = {
            1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
            6: "Summer", 7: "Summer", 8: "Summer", 9: "Fall", 10: "Fall",
            11: "Fall", 12: "Fall"
        }
        df["season"] = df["Month"].map(SEASON_MAP).astype(str)

        # One-hot encode season (drop first)
        season_dummies = pd.get_dummies(df["season"], prefix="season", drop_first=True)
        df = pd.concat([df, season_dummies], axis=1)
    else:
        # Default season features
        df["season_Winter"] = 1
        df["season_Spring"] = 0
        df["season_Summer"] = 0
        df["season_Fall"] = 0

    return df


def add_departure_hour_feature(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add scheduled departure hour feature.

    CRSDepTime is available before departure and captures diurnal delay patterns.

    Returns:
        DataFrame with new departure hour features.
    """
    df = df.copy()

    if "CRSDepTime" in df.columns:
        # Convert to numeric first, then extract hour
        df["CRSDepTime_num"] = pd.to_numeric(df["CRSDepTime"], errors="coerce")
        # Extract hour from CRSDepTime (format hhmm)
        df["dep_hour"] = (df["CRSDepTime_num"] // 100).astype(int)
        df["dep_hour"] = df["dep_hour"].clip(0, 23)
    else:
        df["dep_hour"] = 12  # default

    # One-hot encode departure hour (drop first)
    hour_dummies = pd.get_dummies(df["dep_hour"], prefix="dep_hour", drop_first=True)
    df = pd.concat([df, hour_dummies], axis=1)

    # Drop the intermediate numeric column
    df = df.drop(columns=["CRSDepTime_num"], errors="ignore")

    return df


# ---------------------------------------------------------------------------
# Historical delay rates (computed without leakage)
# ---------------------------------------------------------------------------

def _compute_historical_delay_rates(
    df: pd.DataFrame,
    groupby_cols: list,
    target_col: str = "DepDelay15",
) -> pd.DataFrame:
    """
    Compute historical delay rates for given grouping columns.

    CRITICAL: This function must be called AFTER the temporal split,
    using only training data statistics. The caller is responsible for
    ensuring no future data leakage.

    Returns:
        DataFrame with historical delay rate columns added.
    """
    df = df.copy()

    # Ensure target is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    # Compute delay rate per group
    group_stats = (
        df.groupby(groupby_cols)[target_col]
        .mean()
        .reset_index()
        .rename(columns={target_col: "hist_delay_rate"})
    )

    # Only keep groups with sufficient data (at least 20 flights)
    group_counts = df.groupby(groupby_cols).size().reset_index(name="count")
    group_stats = group_stats.merge(group_counts, on=groupby_cols)
    group_stats = group_stats[group_stats["count"] >= 20]

    # Merge back to original dataframe
    df = df.merge(group_stats, on=groupby_cols, how="left")

    # Fill NaN (groups with insufficient data) with the overall delay rate
    overall_rate = df[target_col].mean()
    df["hist_delay_rate"] = df["hist_delay_rate"].fillna(overall_rate)

    # Drop the original target column to avoid confusion
    df = df.drop(columns=[target_col], errors="ignore")

    return df


def add_carrier_delay_rate(
    df: pd.DataFrame,
    train: Optional[pd.DataFrame] = None,
    target_col: str = "DepDelay15",
) -> pd.DataFrame:
    """
    Add carrier-level historical delay rate.

    CRITICAL: If `train` is provided, the rate is computed from train data only,
    preventing future data leakage. If `train` is None, computed from the full
    dataset (use with caution for temporal splits).

    Returns:
        DataFrame with carrier historical delay rate feature.
    """
    df = df.copy()

    # Ensure target is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    if train is not None:
        carrier_stats = (
            train.groupby("Reporting_Airline")[target_col]
            .mean()
            .reset_index()
            .rename(columns={target_col: "carrier_hist_delay_rate"})
        )
    else:
        carrier_stats = (
            df.groupby("Reporting_Airline")[target_col]
            .mean()
            .reset_index()
            .rename(columns={target_col: "carrier_hist_delay_rate"})
        )

    # Only keep carriers with sufficient data
    if train is not None:
        carrier_counts = train.groupby("Reporting_Airline").size().reset_index(name="count")
    else:
        carrier_counts = df.groupby("Reporting_Airline").size().reset_index(name="count")
    carrier_stats = carrier_stats.merge(carrier_counts, on="Reporting_Airline")
    carrier_stats = carrier_stats[carrier_stats["count"] >= 20]

    df = df.merge(carrier_stats, on="Reporting_Airline", how="left")

    overall_rate = train[target_col].mean() if train is not None else df[target_col].mean()
    df["carrier_hist_delay_rate"] = df["carrier_hist_delay_rate"].fillna(overall_rate)

    # Drop the intermediate target column if it was added
    if "DepDelay15" in df.columns and target_col == "DepDelay15":
        df = df.drop(columns=["DepDelay15"], errors="ignore")

    return df


def add_origin_delay_rate(
    df: pd.DataFrame,
    train: Optional[pd.DataFrame] = None,
    target_col: str = "DepDelay15",
) -> pd.DataFrame:
    """
    Add origin airport historical delay rate.

    CRITICAL: If `train` is provided, the rate is computed from train data only.
    """
    df = df.copy()

    # Ensure target is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    if train is not None:
        origin_stats = (
            train.groupby("Origin")[target_col]
            .mean()
            .reset_index()
            .rename(columns={target_col: "origin_hist_delay_rate"})
        )
    else:
        origin_stats = (
            df.groupby("Origin")[target_col]
            .mean()
            .reset_index()
            .rename(columns={target_col: "origin_hist_delay_rate"})
        )

    # Only keep origins with sufficient data
    if train is not None:
        origin_counts = train.groupby("Origin").size().reset_index(name="count")
    else:
        origin_counts = df.groupby("Origin").size().reset_index(name="count")
    origin_stats = origin_stats.merge(origin_counts, on="Origin")
    origin_stats = origin_stats[origin_stats["count"] >= 20]

    df = df.merge(origin_stats, on="Origin", how="left")

    overall_rate = train[target_col].mean() if train is not None else df[target_col].mean()
    df["origin_hist_delay_rate"] = df["origin_hist_delay_rate"].fillna(overall_rate)

    # Drop the intermediate target column if it was added
    if "DepDelay15" in df.columns and target_col == "DepDelay15":
        df = df.drop(columns=["DepDelay15"], errors="ignore")

    return df


def add_route_delay_rate(
    df: pd.DataFrame,
    train: Optional[pd.DataFrame] = None,
    target_col: str = "DepDelay15",
) -> pd.DataFrame:
    """
    Add route-level (Origin-Destination) historical delay rate.

    CRITICAL: If `train` is provided, the rate is computed from train data only.
    """
    df = df.copy()

    # Ensure target is numeric
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")

    # Create route identifier (sorted to make bidirectional routes equivalent)
    df["route"] = df.apply(
        lambda r: "-".join(sorted([str(r["Origin"]), str(r["Dest"])])),
        axis=1,
    )

    if train is not None:
        route_stats = (
            train.groupby("route")[target_col]
            .mean()
            .reset_index()
            .rename(columns={target_col: "route_hist_delay_rate"})
        )
        route_counts = train.groupby("route").size().reset_index(name="count")
    else:
        route_stats = df.groupby("route")[target_col].mean().reset_index().rename(
            columns={target_col: "route_hist_delay_rate"}
        )
        route_counts = df.groupby("route").size().reset_index(name="count")

    route_stats = route_stats.merge(route_counts, on="route")
    route_stats = route_stats[route_stats["count"] >= 20]

    df = df.merge(route_stats, on="route", how="left")

    # Drop the route column
    df = df.drop(columns=["route"], errors="ignore")

    # Fill NaN with overall delay rate
    overall_rate = train[target_col].mean() if train is not None else df[target_col].mean()
    df["route_hist_delay_rate"] = df["route_hist_delay_rate"].fillna(overall_rate)

    return df


# ---------------------------------------------------------------------------
# Feature engineering pipeline
# ---------------------------------------------------------------------------

def engineer_features(
    df: pd.DataFrame,
    train: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Apply all feature engineering while preventing data leakage.

    CRITICAL: If `train` is provided, all historical statistics are computed
    from train data only. The `df` argument can be train or test data; the
    statistics remain fixed from the training set.

    Returns:
        DataFrame with all engineered features.
    """
    df = df.copy()

    # Ensure target column exists and is numeric
    if "DepDelay15" in df.columns:
        df["DepDelay15"] = pd.to_numeric(df["DepDelay15"], errors="coerce")

    # 1. Day-of-week features (available from BTS data before departure)
    df = add_day_of_week_features(df)

    # 2. Seasonality features (available from month before departure)
    df = add_seasonality_features(df)

    # 4. Historical delay rates (computed from train data only to prevent leakage)
    df = add_carrier_delay_rate(df, train=train)
    df = add_origin_delay_rate(df, train=train)
    df = add_route_delay_rate(df, train=train)

    return df


# ---------------------------------------------------------------------------
# Example usage with temporal split
# ---------------------------------------------------------------------------

def split_and_engineer_features(
    df: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Split data chronologically and engineer features without leakage.

    Returns:
        (X_train, X_test, y_train, y_test) as DataFrames/Series with engineered features.
    """
    import pandas as pd

    # Sort by FlightDate for chronological split
    if "FlightDate" in df.columns:
        df = df.sort_values("FlightDate")
    elif "DayOfWeek" in df.columns:
        df = df.sort_values("DayOfWeek")

    # Split chronologically (earliest 80% train, latest 20% test)
    train = df.iloc[: int(len(df) * (1 - test_size))]
    test = df.iloc[int(len(df) * (1 - test_size)) :]

    # Engineer features using train data statistics only
    train = engineer_features(train, train=train)
    test = engineer_features(df, train=train)  # use train stats for test data

    # Separate features and target
    y_train = train["DepDelay15"]
    y_test = test["DepDelay15"]

    feature_cols = [c for c in train.columns if c != "DepDelay15"]
    X_train = train[feature_cols]
    X_test = test[feature_cols]

    return X_train, X_test, y_train, y_test
