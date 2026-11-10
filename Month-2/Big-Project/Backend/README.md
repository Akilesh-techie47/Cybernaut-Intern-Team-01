# AeroDelay AI - Flight Delay Prediction and Live Tracking

## Overview

Predicts whether a flight will have a departure delay of 15 minutes or more (`DepDelay15`)
using machine learning on BTS On-Time Performance data.

Additionally provides **Live Flight Tracking** from a configured flight-data provider,
with AeroDelay AI prediction where supported.

The project ships three front ends over the same model artifacts:

| Front end | Entry point | Status |
|---|---|---|
| Streamlit app | `app.py` | Original Phase 1-4 app (unchanged) |
| Web app (FastAPI + Next.js) | `start_backend.py` + `C:\aero-frontend` | Phase 5.3 — verified, see `PHASE53_FINAL_VERIFICATION.md` |
| **Batch CSV prediction** | `POST /api/v1/predict/batch` + `/batch` screen | Bulk workflow — see below |

## Project Structure
```text
AeroDelay AI/
├ app.py                  # Streamlit application (Delay Prediction + Live Tracking)
├ src/
│   ├── collect_data.py     # Dataset collection (BTS On-Time Performance)
│   ├── audit_data.py       # Data auditing
│   ├── preprocess.py       # Preprocessing pipeline
│   └── flight_data/        # Flight data providers (Step 2 deliverable)
│       └── _provider.py    # Provider interface + AviationStack adapter
├ artifacts/                # Trained models and preprocessor
│   ├── preprocessor.joblib   # Fitted ColumnTransformer
│   ├── models/               # Trained models
│   │   ├── dummy_classifier.joblib
│   │   ├── logistic_regression.joblib
│   │   └── linearsvc.joblib
│   └── evaluation_results.joblib
├ data/                     # Processed data
│   ├── processed/            # Train/test parquet files
│   └── raw/                  # Raw BTS dataset
├ configs/                  # Dataset configuration
│   ├── dataset_sources.yaml
│   └── dataset_candidates.yaml
├ reports/                  # Generated reports
│   ├── preprocessing_report.md
│   ├── dataset_comparison.md
│   ├── model_evaluation.json
│   ├── model_evaluation.md
│   └── figures/              # Confusion matrix plots
├ tests/                    # Unit and integration tests
│   ├── test_app.py
│   ├── test_collection.py
│   ├── test_preprocess.py
│   ├── test_flight_data.py  # New: provider unit tests
│   ├── test_batch_api.py    # Batch prediction API (83 checks)
│   ├── test_phase53_api.py  # Phase 5.3 API regression (32 checks)
│   └── test_phase53_live.py # Live HTTP suite (21 checks)
├ docs/
│   ├── BATCH_API.md         # Batch prediction API reference
│   └── CSV_TEMPLATE.md      # Batch input schema, aliases, limits
├ templates/
│   └── batch_prediction_template.csv
├ app_backend.py             # FastAPI backend (Phase 5.3 + batch router)
├ batch_prediction.py        # Batch CSV prediction router
├ start_backend.py           # Backend entry point (port 8000)
├ BATCH_PREDICTION_IMPLEMENTATION.md  # Batch sprint report
└ .env                      # Environment variables (never commit!)
```

## Dependencies
```powershell
# Install dependencies via PowerShell
pip install streamlit pandas numpy scikit-learn joblib scipy matplotlib requests
```

## Launch the Application
```powershell
# Navigate to the project directory
cd "D:\Cybernaut intern\Big project (month-2)"

# Launch Streamlit app
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

### Web app (FastAPI backend + Next.js frontend)
```powershell
# Terminal 1 - backend on http://localhost:8000 (docs at /docs)
python start_backend.py

# Terminal 2 - frontend on http://localhost:3000
cd C:\aero-frontend
npx next dev -p 3000
```

The frontend only ever talks to the local backend; the AviationStack API key
stays server-side in `.env` and is never exposed to the browser.

### Required Environment Configuration
Copy `.env` and set your AviationStack API key:
```powershell
# .env file - never commit to source control!
AVIATIONSTACK_ACCESS_KEY=your_aviationstack_access_key_here
```

Get your free key at: https://aviationstack.com/
- Free tier: 250 requests per month (sufficient for development/demo)
- Paid plans available for higher volume

## Features

### Tab 1: Delay Prediction (existing)
Predicts whether a flight will have a departure delay of 15 minutes or more
based on pre-departure information using a pre-trained Logistic Regression model.

**Input features** (pre-departure only):
- Reporting_Airline: Airline carrier code (e.g., AA, DL, UA)
- Origin: Origin airport 3-letter code
- Dest: Destination airport 3-letter code
- Month: Month of flight (1-12)
- Distance: Distance between airports (miles)
- CRSDepTime: Scheduled departure time (local hhmm, 0000-2359)
- Cancelled: 0=No, 1=Yes
- Diverted: 0=No, 1=Yes

**Output**:
- Likely Delayed / Not Likely Delayed badge
- Model confidence/probability (≥15 min delay)
- Clear disclaimer: *This is a prediction based on historical data, not a guarantee.*

### Tab 2: Live Flight Tracking (new)
Allows a user to enter a flight number and travel date, retrieve live flight information
from the configured provider, display the flight's route and status, and provide an
AeroDelay AI prediction where supported.

**Inputs**:
- Flight number (e.g., UA123, DL456)
- Travel date (YYYY-MM-DD)

**Display**:
- Flight status and source timestamp
- Route map concept (coordinates when available)
- Scheduled, estimated, and actual departure/arrival times
- Origin and destination airport details (IATA/ICAO, city, country, timezone)
- Departure delay in minutes when known
- Estimated time remaining until arrival when ETA is available
- Aircraft position, altitude, and speed when available
- Clear loading, error, and unavailable-data states

**Provider**: AviationStack (free tier: 250 requests/month)

**ML Prediction Integration**:
- Uses the existing model only for its validated pre-departure prediction task
- Constructs input features from fields the model expects
- If required features are missing, explains why prediction is unavailable
- Displays model-predicted delay risk separately from provider-confirmed flight status
- Does not claim the model predicts arrival delay or prevents delays

## Batch Prediction (bulk CSV workflow)

Score up to **200 CSV files (500,000 rows)** in one submission from the web
app's **Batch** tab (`http://localhost:3000/batch`) or directly against the API.

**Flow:** drag-and-drop CSVs → per-file pre-checks and validation → optional
column mapping → background job with live progress → results (stat cards,
risk donut, outcome bars, per-file stats, paged rows, failure ledger) →
download individual / combined / summary / failures CSVs.

- **API reference:** [`docs/BATCH_API.md`](docs/BATCH_API.md)
  (`POST /api/v1/predict/batch`, status, results, download, template, delete)
- **Input schema, aliases, supported values, limits:**
  [`docs/CSV_TEMPLATE.md`](docs/CSV_TEMPLATE.md)
- **Template:** [`templates/batch_prediction_template.csv`](templates/batch_prediction_template.csv)
  (or `GET /api/v1/predict/batch/template?style=canonical|bts`)
- **Implementation report + verification results:**
  [`BATCH_PREDICTION_IMPLEMENTATION.md`](BATCH_PREDICTION_IMPLEMENTATION.md)

Design guarantees:

- Valid rows are predicted; invalid rows are **rejected with a column, error
  code and message** and written to a downloadable failure ledger — nothing is
  silently truncated or discarded.
- Every score comes from the loaded ML model (chunked, same pipeline as the
  single-prediction endpoint). If the model cannot run, the API returns
  HTTP `550 model_unavailable` and **no** job or fallback score is produced.
- Label/outcome columns (`DepDelay15`, `ArrDelay`, …) are excluded from the
  model inputs; unknown carriers/airports are rejected, never silently mapped.
- Uploaded filenames are sanitised (no path traversal), job temp files live
  under the system temp dir and are removed on delete/expiry/process exit.
- Limits: 200 files · 10 MB/file · 100 MB/batch · 50k rows/file ·
  500k rows/batch · 500-row inference chunks · 1-hour job retention.

> ⚠ **Honesty note:** probabilities are uncalibrated outputs of the served
> model (`Phase 2 Ensemble v2.1 (retrained)`, trained on synthetic data — see
> `PHASE53_FINAL_VERIFICATION.md` §11). Risk bands (`High ≥ 0.7`,
> `Medium ≥ 0.4`, `Low < 0.4`) and the `0.5` class threshold are model
> conventions, not certainty.

## Model Performance (held-out test set)
- **Accuracy**: 39.90%
- **Precision (Delayed)**: 30.54% — of predicted delayed flights, ~30.5% were actually delayed
- **Recall (Delayed)**: 86.51% — of all actually delayed flights, ~86.5% were predicted delayed
- **F1 (Delayed)**: 45.15% — harmonic mean of precision and recall
- **ROC-AUC**: 0.553 — modest discriminative ability

> ⚠ **Limitations**: These metrics are from a temporal hold-out test set (80/20 chronological split). 
> Performance may vary with real-world data. This tool is for informational purposes only and 
> should not be used for operational decision-making.

## Provider Limitations (AviationStack)
- Free tier: 250 requests per month
- Does not provide live en-route aircraft position (basic plan limitation)
- Flight status and times may not be real-time; delayed by minutes to hours
- Ambiguous flight numbers (same number, different airlines/routes) may require disambiguation
- Airports without latitude/longitude in the response will show position as unavailable
- Rate limits apply; applications should handle 429 responses gracefully
- Requires API key stored in `AVIATIONSTACK_ACCESS_KEY` environment variable
- Terms of service: https://aviationstack.com/terms

## Development
```powershell
# Backend tests (project root)
python tests\test_batch_api.py        # Batch API: 83 checks
python tests\test_phase53_api.py      # Phase 5.3 API regression: 32 checks
python tests\test_phase53_live.py     # Live HTTP + provider: 21 checks (both servers up)
python -m pytest tests/ -q            # Everything pytest collects: 80 tests

# Frontend tests (C:\aero-frontend, both servers up)
npx playwright test                   # Browser E2E: 62 tests
npx tsc --noEmit                      # Types (fails only on 4 legacy files, see below)
```

## Files Changed (Recent)
- `app.py` — New Streamlit application with Live Flight Tracking tab
- `src/flight_data/_provider.py` — Provider interface + AviationStack adapter (Step 2)
- `.env` — Environment variable template for API key (Step 5)
- `.gitignore` — Added `.env` protection (Step 5)
- `README.md` — Updated with setup, PowerShell instructions, and provider limitations
- `batch_prediction.py` + `tests/test_batch_api.py` — Batch prediction API and its 83-check suite (final sprint)
- `app_backend.py` — Shared constants/helpers, batch router wiring, rate-limit + CORS adjustments
- `templates/batch_prediction_template.csv`, `docs/BATCH_API.md`, `docs/CSV_TEMPLATE.md`,
  `BATCH_PREDICTION_IMPLEMENTATION.md` — batch docs and template
- `C:\aero-frontend\app\batch\page.tsx`, `components/batch/*`, `lib/api.ts`,
  `components/navigation.tsx`, `e2e-tests/batch.spec.js` — Batch screen, API client, 6th nav tab, E2E suite

## Tests
- **80 pytest tests** passing (`python -m pytest tests/ -q`)
- **83/83** batch API checks, **32/32** Phase 5.3 API regression,
  **21/21** live suite — all exit 0
- **62/62** Playwright browser tests (incl. 13 batch tests and the `/batch`
  page at 360-1440 px), all exiting 0
- Existing collection/preprocess/provider tests continue passing; provider
  tests use mocked responses (tests never require live API credentials or
  contact AviationStack except where explicitly marked live)
- Known: `npx tsc --noEmit` reports errors in 4 pre-existing legacy
  duplicates (`app/prediction.tsx`, `app/analytics.tsx`, `app/tracking.tsx`,
  `app/ModelsPage.tsx`) — broken JSX from before the Phase 5.3 rewrite,
  unreferenced and not routes; they are excluded from the app and were left
  untouched (details in `BATCH_PREDICTION_IMPLEMENTATION.md` §6)