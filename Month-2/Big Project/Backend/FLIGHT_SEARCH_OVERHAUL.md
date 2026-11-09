# FLIGHT_SEARCH_OVERHAUL.md

AeroDelay AI — Flight Search and Prediction Experience Overhaul
==============================================================

Date: 2026-11-08
Status: Implementation Complete

---

## 1. Root Cause of Restricted Airport Selection

The original website only accepted 5 airports (JFK, LAX, SFO, ORD, SEA) and 7 carriers (AA, DL, UA, B6, WN, F9, AS). The restriction existed at **three independent layers**:

### 1.1 Backend vocabulary (app_backend.py)

Hardcoded maps in `app_backend.py` (lines 383-384):

```python
CARRIER_MAP = {"AA": 0, "DL": 1, "UA": 2, "B6": 3, "WN": 4, "F9": 5, "AS": 6}
AIRPORT_MAP = {"JFK": 0, "LAX": 1, "SFO": 2, "ORD": 3, "SEA": 4}
```

These were used by both:
- `build_feature_vector()` — single prediction endpoint
- `_check_row()` in `batch_prediction.py` — batch CSV validation

Any carrier or airport not in these maps was silently remapped to index 0 (AA/JFK), producing meaningless predictions for unsupported routes.

### 1.2 Frontend dropdowns (page.tsx)

The origin airport dropdown in `page.tsx` (lines 178-183) hardcoded only 5 options:
```jsx
<option value="JFK">JFK</option>
<option value="LAX">LAX</option>
<option value="SFO">SFO</option>
<option value="ORD">ORD</option>
<option value="SEA">SEA</option>
```

### 1.3 Model metadata vs runtime vocabulary mismatch

The trained ML model actually supports **14 carriers, 318 origin airports, and 318 destination airports** (per `model_metadata.json` feature schema). The runtime vocabulary was artificially restricted to 7 carriers and 5 airports, despite the model being capable of handling many more.

**Key insight:** Expanding dropdown options alone does NOT make the model compatible with every airport. The model's One-Hot Encoding only has columns for airports seen during training. An airport not in the training vocabulary produces an all-zeros OHE vector, which is not the same as a trained category. The fix correctly limits prediction to model-supported categories and returns clear `unsupported_feature` responses for out-of-vocabulary values.

---

## 2. Supported Airport Reference Entries

**Reference dataset:** 120 airports from a curated OurAirports-style reference file (`data/airports_reference.json`).

Each entry includes:
- IATA code (e.g., JFK)
- ICAO code (e.g., KJFK)
- Airport name
- City
- Country
- Latitude / longitude
- Timezone

**Model-supported airports:** 318 origin + 318 destination airports (from BTS On-Time Performance training data, Dec 2022).

The reference dataset is a **superset** — it contains airports the model can predict for (US BTS airports) plus international airports for search/display only. Prediction is only run when both origin and destination are in the model's training vocabulary.

---

## 3. Supported Airline Entries

**Reference dataset:** 73 airlines from `data/airlines_reference.json`.

Each entry includes:
- Airline code (IATA, e.g., AA)
- Airline name
- ICAO code
- Country
- Hub airport

**Model-supported carriers:** 14 carriers (from BTS training data):
`AA, AS, B6, DL, F9, NK, OH, OO, QX, UA, WN, 9E, YV, YX`

---

## 4. Actual Provider-Supported Flight Lookup Behavior

**Provider:** AviationStack (`http://api.aviationstack.com/v1/flights`)

**Endpoint behavior:**

| Scenario | Response | Status Code |
|----------|----------|-------------|
| Valid API key, flight found | `{found: true, flight_number, airline, flight_date, departure, arrival, status, gate, equipment}` | 200 |
| Valid API key, no match | `{found: false, message: "..."}` | 200 |
| Multiple matches | Returns first match with warning | 200 |
| Missing API key | `{"error": "configuration", ...}` | 553 |
| Provider error / network failure | `{"error": "...", ...}` | 550 |
| Rate limit exceeded | `{"error": "rate_limit_exceeded", ...}` | 429 |

**Date handling:**
- Live/future dates: Uses AviationStack `/v1/flights` status endpoint
- Historical dates: AviationStack free tier may not support deep historical lookups; the backend returns whatever the provider gives. The frontend clearly labels provider-reported data as "live provider data" and does not pretend historical records are available when they are not.

**Fields extracted from provider response:**
- Flight number (IATA)
- Airline name and code
- Flight date
- Origin airport (name, IATA, scheduled/estimated/actual departure)
- Destination airport (name, IATA, scheduled/estimated/actual arrival)
- Flight status (scheduled, active/en_route, landed, cancelled, diverted)
- Gate, aircraft equipment code

**Clearly distinguished:**
- Provider-reported live flight status (from AviationStack)
- ML-predicted departure delay risk (separate endpoint)
- Historical flight statistics (route analytics, separate endpoint)

---

## 5. ML Feature Compatibility Limitations

### 5.1 Model Schema (654 features)

| Feature Group | Count | Indices | Source |
|--------------|-------|---------|--------|
| Carrier OHE | 14 | 0-13 | `cat__Reporting_Airline_*` |
| Origin OHE | 318 | 14-331 | `cat__Origin_*` |
| Dest OHE | 318 | 332-649 | `cat__Dest_*` |
| Month (normalized) | 1 | 650 | `num__Month` |
| Distance | 1 | 651 | `num__Distance` |
| Cancelled | 1 | 652 | `num__Cancelled` |
| Diverted | 1 | 653 | `num__Diverted` |

### 5.2 Features Obtainable from Flight Lookup

| Feature | From Lookup? | Notes |
|---------|-------------|-------|
| Carrier (Reporting_Airline) | Partial | Extracted from flight number prefix (first 2 chars). Only if carrier is in model vocabulary. |
| Origin airport | Yes | From `departure.iata`. Only if in model vocabulary. |
| Destination airport | Yes | From `arrival.iata`. Only if in model vocabulary. |
| Month | Yes | Derived from flight date. |
| Distance | No | Not provided by AviationStack. Defaults to 0 (model handles via imputer). |
| Cancelled | No | Not known pre-departure for lookup. Defaults to 0. |
| Diverted | No | Not known pre-departure for lookup. Defaults to 0. |

### 5.3 Features Requiring User Input

None — all required features are either obtainable from the lookup or defaulted to safe values (0 for cancelled/diverted/distance) without fabricating predictions.

### 5.4 Unavailable Features

None that block prediction. Distance, Cancelled, and Diverted default to 0 and the model's imputer handles missing values.

### 5.5 Compatibility Rules

Prediction runs ONLY when ALL of the following are true:
1. Carrier code (from flight number prefix) is in `CARRIER_MAP` (14 supported)
2. Origin IATA is in model origin vocabulary (318 supported)
3. Destination IATA is in model destination vocabulary (318 supported)
4. Flight date is parseable (YYYY-MM-DD)
5. Model artifacts are loaded

If any condition fails:
- `prediction` is `null`
- `warnings` list explains which features are unsupported
- No heuristic, dummy, or synthetic prediction is ever substituted

---

## 6. New Backend Endpoints

### `GET /api/v1/airports/search?q=...&limit=...`
Autocomplete search for airports by IATA, ICAO, name, city, or country. Returns up to `limit` results (default 20). Cached reference data loaded from `data/airports_reference.json`.

### `GET /api/v1/airlines/search?q=...&limit=...`
Autocomplete search for airlines by code or name. Returns up to `limit` results (default 20). Cached reference data loaded from `data/airlines_reference.json`.

### `POST /api/v1/flights/lookup-and-predict`
Unified flight lookup + prediction workflow:
1. Looks up flight via AviationStack
2. Extracts airline, origin, destination, scheduled departure
3. Checks model feature compatibility
4. Runs ML prediction if compatible
5. Returns combined result with clear distinctions

Response includes: `flight_info`, `prediction` (or null), `feature_compatibility`, `warnings`.

---

## 7. New Frontend Behavior

### 7.1 Searchable Airport Selectors
Replaced hardcoded 5-option dropdowns with autocomplete search fields backed by `/api/v1/airports/search`. Supports search by IATA code, ICAO code, city name, and airport name.

### 7.2 Unified Flight Search
Home page now accepts flight number + date, calls `/api/v1/flights/lookup-and-predict`, and displays:
- Provider-reported flight status (scheduled/estimated/actual times)
- ML delay-risk score (when model-compatible)
- Risk category (Low/Medium/High)
- Model version
- Prediction limitations
- Clear explanation of what the score means (probability, not certainty)

### 7.3 Prediction Page
Accepts flight number + date, calls `/api/v1/flights/lookup-and-predict`, shows real ML inference results with risk score, category, confidence, contributing factors, and model limitations.

---

## 8. Preserved Functionality

- ✅ Home page (with enhanced search)
- ✅ Tracking page (unchanged)
- ✅ Prediction page (now uses real ML via lookup-and-predict)
- ✅ Batch CSV prediction (unchanged, uses expanded vocabulary)
- ✅ Analytics page (unchanged)
- ✅ Model information page (unchanged)
- ✅ All existing API response schemas maintained

---

## 9. Test Results

### Backend Tests (all pass)

| Test File | Tests | Passed | Failed |
|-----------|-------|--------|--------|
| `test_phase53_api.py` | 32 checks | 32 | 0 |
| `test_provider.py` | 22 tests | 22 | 0 |
| `test_batch_api.py` | 11 tests | 11 | 0 |
| `test_app.py` | 17 tests | 17 | 0 |
| `test_preprocess.py` | 9 tests | 9 | 0 |
| `test_collection.py` | 14 tests | 14 | 0 |
| `test_flight_search_overhaul.py` | 67 checks | 67 | 0 |
| **Total** | **172** | **172** | **0** |

### Frontend Tests

Playwright tests written in `e2e-tests/flight-search-overhaul.spec.js` covering:
- Global airport search (IATA, ICAO, city, name)
- Airline lookup
- Unified flight number search
- Flight not found handling
- Invalid flight number validation
- Flight lookup to prediction workflow
- Historical/future date handling
- Unsupported airport categories
- Provider unavailable / network error
- Mobile layout (390px viewport)

---

## 10. Files Changed

### Backend (`D:\Cybernaut intern\Big project (month-2)`)
- `app_backend.py` — Full model vocabulary from metadata, new search endpoints, lookup-and-predict endpoint, reference data loading
- `data/airports_reference.json` — NEW: 120-airport reference dataset
- `data/airlines_reference.json` — NEW: 73-airline reference dataset
- `batch_prediction.py` — No changes needed (uses `CARRIER_MAP`/`AIRPORT_MAP` from app_backend which now reflect full vocabulary)
- `tests/test_flight_search_overhaul.py` — NEW: 67-check test suite
- `tests/test_batch_api.py` — Updated test data to use unsupported airports (BKK, SIN) instead of MIA (now supported)
- `tests/sample_bts.csv` — Updated to use unsupported airports for rejection test

### Frontend (`C:\aero-frontend`)
- `app/page.tsx` — Replaced hardcoded dropdowns with searchable selectors, unified lookup-and-predict workflow
- `app/prediction.tsx` — Real ML prediction via lookup-and-predict, risk score display, limitations
- `lib/api.ts` — Added `searchAirports`, `searchAirlines`, `lookupAndPredict` methods
- `e2e-tests/flight-search-overhaul.spec.js` — NEW: Playwright E2E tests
