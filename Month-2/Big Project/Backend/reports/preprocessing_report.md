# AeroDelay AI Preprocessing Report

**Generated:** 2026-11-03T14:57:55.903127
**Dataset:** US DOT BTS On-Time Performance - Reporting Carrier

## 1. Data Overview

- **Total usable records:** 557,095
- **Training set:** 498,870 records
- **Test set:** 58,225 records

## 2. Chronological Split

- **Split method:** Earliest 80% training, latest 20% testing
- **Train period:** 2022-12-01 to 2022-12-31
- **Test period:** 2022-12-01 to 2022-12-31
- **No duplicate flight identifiers** cross train/test partitions: ✅

## 3. Target Definition (DepDelay15)

- **Definition:** 1 = departure delay >= 15 minutes, 0 = otherwise
- **Policy for Cancelled/Diverted flights:** 
  - Cancelled flights labeled as 1 (do not depart on schedule by definition)
  - Diverted flights labeled as 1 (miss scheduled departure by definition)
  - Both fields are available pre-departure in BTS data
- **Train set balance:** {0: 0.7492833804397939, 1: 0.2507166195602061}
- **Test set balance:** {0: 0.714143409188493, 1: 0.2858565908115071}

## 4. Selected Predictors (7)

### Categorical Predictors (3):
['Reporting_Airline', 'Origin', 'Dest']

### Numeric Predictors (4):
['Month', 'Distance', 'Cancelled', 'Diverted']

## 4. Leakage Check

- **Leakage columns found:** ['DepTime', 'DepDelay', 'DepDelayMinutes', 'TaxiOut', 'WheelsOff', 'ArrTime', 'ArrDelay', 'ActualElapsedTime', 'CRSArrTime', 'AirTime', 'Flights', 'CRSElapsedTime'] ✅
- **All predictors available before scheduled departure:** ✅
- **Excluded post-departure columns:** DepTime, DepDelay, TaxiOut, WheelsOff, 
  ArrTime, ArrDelay, ActualElapsedTime, AirTime, Flights

## 5. Preprocessing Pipeline

- **OneHotEncoder(handle_unknown="ignore")** for categorical predictors
- **SimpleImputer(strategy="most_frequent")** for categorical missing values
- **SimpleImputer(strategy="median")** for numeric missing values
- **StandardScaler()** for numeric predictors
- **Fitted only on training partition:** ✅
- **Feature names generated:** 654 features

## 5. Missing-Value Handling

  Reporting_Airline: 0.00% missing
  Origin: 0.00% missing
  Dest: 0.00% missing
  Month: 0.00% missing
  Distance: 0.00% missing
  Cancelled: 0.00% missing
  Diverted: 0.00% missing

  Reporting_Airline: 0.00% missing
  Origin: 0.00% missing
  Dest: 0.00% missing
  Month: 0.00% missing
  Distance: 0.00% missing
  Cancelled: 0.00% missing
  Diverted: 0.00% missing

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
