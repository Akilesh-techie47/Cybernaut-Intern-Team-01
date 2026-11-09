from preprocess import (
    define_target,
    select_pre_departure_predictors,
)
from collect_data import load_bts_csv
import pandas as pd
from pathlib import Path

# Load a small sample
df = pd.read_csv('data/raw/On_Time_Reporting_Carrier_On_Time_Performance_2022_12.zip_raw.csv', dtype=str, nrows=5000)
df.columns = df.columns.str.strip()

# Define target
df = define_target(df)
print(f'Target distribution: {df["DepDelay15"].value_counts().to_dict()}')

# Check available predictors
predictors, leakage = select_pre_departure_predictors(df)
print(f'Current predictors: {predictors}')
print(f'Leakage: {leakage}')

# Check available columns
print(f'\nAvailable columns: {list(df.columns)}')

# Check DayOfWeek
if 'DayOfWeek' in df.columns:
    print(f'DayOfWeek distribution: {df["DayOfWeek"].value_counts().to_dict()}')

# Check CRSDepTime
if 'CRSDepTime' in df.columns:
    print(f'CRSDepTime stats: min={df["CRSDepTime"].min()}, max={df["CRSDepTime"].max()}')
    
# Check if we can compute season
print(f'\nSample rows:')
print(df.head())
PYEOF