# MODEL_FEATURE_COMPATIBILITY.md

AeroDelay AI — ML Model Feature Compatibility Report
====================================================

Date: 2026-11-08
Model: Logistic Regression (Real BTS), Phase 5.4 Production v1.0
Artifacts: `logistic_regression_new.joblib` + `preprocessor_compatible.joblib`

---

## 1. Complete 654-Feature Schema

The model was trained on BTS On-Time Performance data (Dec 2022, 498,870 samples) with a ColumnTransformer preprocessing pipeline. The 654 features are organized as follows:

| Feature Group | Count | Feature Indices | Naming Pattern |
|--------------|-------|----------------|----------------|
| Carrier One-Hot Encoding | 14 | 0–13 | `cat__Reporting_Airline_{CODE}` |
| Origin Airport One-Hot Encoding | 318 | 14–331 | `cat__Origin_{CODE}` |
| Destination Airport One-Hot Encoding | 318 | 332–649 | `cat__Dest_{CODE}` |
| Month (normalized) | 1 | 650 | `num__Month` |
| Distance | 1 | 651 | `num__Distance` |
| Cancelled | 1 | 652 | `num__Cancelled` |
| Diverted | 1 | 653 | `num__Diverted` |
| **Total** | **654** | **0–653** | |

### 1.1 Supported Carriers (14)

`AA, AS, B6, DL, F9, NK, OH, OO, QX, UA, WN, 9E, YV, YX`

### 1.2 Supported Origin Airports (318)

Full list in `model_metadata.json` feature_schema.feature_names. Includes all US airports in the BTS On-Time Performance dataset (Dec 2022). Major hubs: JFK, LAX, ORD, ATL, DFW, DEN, SFO, SEA, LAS, MCO, EWR, CLT, PHX, MIA, IAH, BOS, MSP, DTW, FLL, SAN, LGA, BWI, DCA, IAD, MDW, HNL, TPA, PDX, STL, BNA, AUS, SLC, RDU, SJC, SNA, SMF, OAK, SJU, ANC, OGG, KOA, LIH, and 288 more.

### 1.3 Supported Destination Airports (318)

Same set as origin airports.

### 1.4 Numerical Features

| Feature | Index | Description | Preprocessing |
|---------|-------|-------------|---------------|
| Month | 650 | Month of flight (1-12), normalized by /12.0 | Median impute + StandardScaler |
| Distance | 651 | Flight distance in miles | Median impute + StandardScaler |
| Cancelled | 652 | Cancellation indicator (0/1) | Median impute + StandardScaler |
| Diverted | 653 | Diversion indicator (0/1) | Median impute + StandardScaler |

---

## 2. Features Obtainable from AviationStack Flight Lookup

The AviationStack `/v1/flights` endpoint returns the following fields. Those that map to model features:

| Model Feature | From Lookup? | Source Field | Notes |
|--------------|-------------|--------------|-------|
| `Reporting_Airline` (carrier) | Partial | `flight.iata` prefix (first 2 chars) | Only if carrier code is in model vocabulary |
| `Origin` | Yes | `departure.iata` | Only if IATA code is in model origin vocabulary |
| `Dest` | Yes | `arrival.iata` | Only if IATA code is in model destination vocabulary |
| `Month` | Yes | `flight_date` (YYYY-MM-DD) | Extracted from date string |
| `Distance` | No | Not provided by AviationStack | Defaults to 0 (handled by imputer) |
| `Cancelled` | No | Not known pre-departure | Defaults to 0 |
| `Diverted` | No | Not known pre-departure | Defaults to 0 |

### Fields NOT obtainable from lookup

| Feature | Reason | Handling |
|---------|--------|----------|
| Distance | AviationStack free tier doesn't provide distance | Defaults to 0; model imputer handles missing |
| Cancelled | Not known before flight operates | Defaults to 0 |
| Diverted | Not known before flight operates | Defaults to 0 |

These defaults are **safe** because:
- The preprocessor was fitted with `SimpleImputer(strategy="median")` for numerical features
- A value of 0 for cancelled/diverted means "not cancelled/diverted" which is the correct pre-departure assumption
- Distance of 0 is imputed by the preprocessor

---

## 3. Feature Availability Report

### 3.1 Compatibility Decision Matrix

| Carrier Supported? | Origin Supported? | Dest Supported? | Date Parsable? | Model Ready? | Prediction Runs? |
|-------------------|-------------------|-----------------|----------------|--------------|------------------|
| ✅ | ✅ | ✅ | ✅ | ✅ | **YES** — real ML inference |
| ❌ | ✅ | ✅ | ✅ | ✅ | **NO** — `unsupported_feature` for carrier |
| ✅ | ❌ | ✅ | ✅ | ✅ | **NO** — `unsupported_feature` for origin |
| ✅ | ✅ | ❌ | ✅ | ✅ | **NO** — `unsupported_feature` for destination |
| ✅ | ✅ | ✅ | ❌ | ✅ | **NO** — date not parsable |
| ✅ | ✅ | ✅ | ✅ | ❌ | **NO** — `model_unavailable` |

### 3.2 Unsupported Feature Response

When prediction cannot run, the API returns:

```json
{
  "flight_info": {
    "found": true,
    "flight_number": "SQ1",
    "airline": "Singapore Airlines",
    "origin": "SIN",
    "destination": "LHR",
    "model_compatible": false,
    "unsupported_features": ["carrier_supported", "origin_supported", "destination_supported"]
  },
  "prediction": null,
  "feature_compatibility": {
    "carrier_supported": false,
    "origin_supported": false,
    "destination_supported": false,
    "date_parsable": true,
    "model_ready": true
  },
  "warnings": [
    "Carrier 'SQ' not in model vocabulary (14 supported)",
    "Origin 'SIN' not in model vocabulary (318 supported)",
    "Destination 'LHR' not in model vocabulary (318 supported)",
    "Route not supported by model - prediction skipped"
  ]
}
```

### 3.3 What Is NOT Done

- ❌ No silent remapping of unsupported carriers to index 0 (AA)
- ❌ No silent remapping of unsupported airports to index 0 (JFK)
- ❌ No heuristic or dummy predictions substituted
- ❌ No fabrication of missing feature values (distance defaults to 0 via imputer, not arbitrary)
- ❌ No claim of worldwide ML prediction support

---

## 4. Category Encoder Behavior

The model uses `OneHotEncoder(handle_unknown="ignore")` for categorical features. This means:

- **In-vocabulary carrier/airport:** The corresponding OHE column is set to 1.0
- **Out-of-vocabulary carrier/airport:** All OHE columns for that category are 0.0 — this is NOT a valid trained category and produces undefined model behavior

The backend explicitly checks vocabulary membership BEFORE building the feature vector. If a carrier or airport is not in the model's training vocabulary, prediction is skipped with a clear error.

---

## 5. Model Performance (from metadata)

| Metric | Value |
|--------|-------|
| Test Accuracy | 0.4961 (49.6%) |
| Precision | 0.3109 (31.1%) |
| Recall | 0.6271 (62.7%) |
| F1 Score | 0.4157 (41.6%) |
| ROC AUC | 0.5547 (55.5%) |
| PR AUC | 0.3256 (32.6%) |
| Training Time | 8.34 seconds |
| Train Samples | 498,870 |
| Test Samples | 58,225 |
| Class Distribution | 373,795 on-time / 125,075 delayed (28.6% delayed) |

**Important:** The model has modest performance (ROC AUC 0.55). Predictions should be treated as statistical estimates, not guarantees. The confusion matrix shows significant false positives and false negatives.

---

## 6. Risk Bands

| Band | Score Range | Interpretation |
|------|-------------|----------------|
| Low | < 0.40 | Low probability of ≥15 min departure delay |
| Medium | 0.40 – 0.70 | Moderate probability of ≥15 min departure delay |
| High | ≥ 0.70 | High probability of ≥15 min departure delay |

Class decision threshold: 0.50 (predicted class = 1 if P(delayed) ≥ 0.50)

---

## 7. Data Distinctions (Critical)

The system clearly distinguishes three types of information:

| Type | Source | What It Means |
|------|--------|---------------|
| **Provider-reported live flight status** | AviationStack API | Actual/estimated/scheduled departure/arrival times, gate, status from the flight data provider. This is real-time operational data. |
| **ML-predicted departure delay risk** | Logistic Regression model | Statistical probability (0–1) of departure delay ≥ 15 minutes, based on historical patterns. This is a prediction, not a guarantee. |
| **Historical flight statistics** | Route analytics endpoint | Aggregated on-time/delayed percentages for specific routes from BTS data. This is historical context, not a prediction for a specific flight. |

---

## 8. Files

- `artifacts/models/model_metadata.json` — Complete feature schema with all 654 feature names
- `artifacts/models/preprocessor_compatible.joblib` — Fitted ColumnTransformer (OneHotEncoder + imputer + scaler)
- `artifacts/models/logistic_regression_new.joblib` — Trained Logistic Regression model
- `app_backend.py` — Backend with feature compatibility checks and `unsupported_feature` responses
- `tests/test_flight_search_overhaul.py` — Tests covering compatibility, unsupported categories, missing features
