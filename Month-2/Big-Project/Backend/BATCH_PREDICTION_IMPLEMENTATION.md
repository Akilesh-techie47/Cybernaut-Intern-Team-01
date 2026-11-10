# Batch Prediction — Implementation Report

Final 2-hour sprint deliverable: a production-oriented **bulk CSV flight-delay
prediction workflow** added to the existing AeroDelay AI app (FastAPI backend +
Next.js frontend) **without rebuilding or breaking anything**.

- Screen: `http://localhost:3000/batch` (6th nav tab, "Batch")
- API: `POST/GET/DELETE /api/v1/predict/batch…` (see [`docs/BATCH_API.md`](docs/BATCH_API.md))
- Input schema, columns, aliases, limits: [`docs/CSV_TEMPLATE.md`](docs/CSV_TEMPLATE.md)
- Template file: [`templates/batch_prediction_template.csv`](templates/batch_prediction_template.csv)

Everything below was verified by running the suites on 2026-11-08; actual
outputs are quoted in §5. No claim in this document is made without a test
behind it.

---

## 1. What was built

### Backend (project root)

| File | Change | Purpose |
|---|---|---|
| `batch_prediction.py` | **new** (~2,050 lines) | Batch router: upload/validation, job store, background processing, chunked inference, CSV sinks, downloads, template |
| `app_backend.py` | modified | Shared constants (`CARRIER_MAP`, `AIRPORT_MAP`, `RISK_*_THRESHOLD`, `MODEL_CLASS_THRESHOLD`), `transform_feature_matrix()` / `run_batch_predict_proba()` / `get_model_version()` / `is_model_ready()`, router include, rate-limit exemption for job-scoped batch routes, CORS `expose_headers=["Content-Disposition"]` |
| `tests/test_batch_api.py` | **new** | 83-check verification suite (standalone + pytest) |
| `templates/batch_prediction_template.csv` | **new** | Canonical template checked into the repo |
| `docs/BATCH_API.md`, `docs/CSV_TEMPLATE.md` | **new** | API reference + input-schema documentation |

Single-prediction behaviour is unchanged: `run_prediction()` was split into
`build_feature_vector()` + `transform_features()` + `run_prediction()` so the
batch path reuses the exact same pipeline (parity asserted by tests).

### Frontend (`C:\aero-frontend`)

| File | Change | Purpose |
|---|---|---|
| `app/batch/page.tsx` | **new** | Screen orchestrator: phase machine (`idle → uploading → running → done`), serialized queue adds, 700 ms status polling, cancel/delete, column mapping, template downloads, limits section |
| `components/batch/BatchQueue.tsx` | **new** | Drag-and-drop dropzone, file queue with per-file name/size/status/remove, fast client pre-checks (extension, empty, per-file/batch size, UTF-16 BOM, duplicate hint), header reader |
| `components/batch/BatchResults.tsx` | **new** | Stat cards, inline-SVG risk donut + outcome bars, per-file stats table (with rejection reason), paged prediction rows, failure ledger, download controls, honesty notes |
| `lib/api.ts` | modified | Typed batch models + `batchCreate/batchStatus/batchResults/batchDelete/batchDownload/batchTemplate` (FormData/blob paths bypass the JSON `request()` helper) |
| `components/navigation.tsx` | modified | 6th `Batch` tab (`Files` icon); wordmark hidden between `md` and `lg` so 6 tabs fit at 768 px; bottom-nav labels wrap without overflow |
| `e2e-tests/batch.spec.js` | **new** | 13 browser tests (real backend + simulated failure states) |
| `e2e-tests/responsive.spec.js` | modified | `/batch` added to the 6-viewport matrix |
| `e2e-tests/aero-delay.spec.js` | modified | Mobile nav asserts the 6th tab and navigates to `/batch` |

Deliberately **untouched**: Streamlit `app.py`, model artifacts, experiment
reports, and the 4 legacy `app/*.tsx` duplicates (`prediction`, `analytics`,
`tracking`, `ModelsPage`) — they are broken-syntax, unreferenced, non-route
files from before the Phase 5.3 rewrite (see §6).

---

## 2. Endpoints

| Method | Path | Success | Notes |
|---|---|---|---|
| `POST` | `/api/v1/predict/batch` | `202` `BatchJobStatus` | multipart `files[]` + optional `mapping` JSON; background processing starts immediately |
| `GET` | `/api/v1/predict/batch/template?style=canonical\|bts` | `200` CSV | `Content-Disposition` attachment |
| `GET` | `/api/v1/predict/batch/{job_id}` | `200` `BatchJobStatus` | status, progress, per-file states, final `summary` |
| `GET` | `/api/v1/predict/batch/{job_id}/results?page&page_size&file_id` | `200` `BatchResults` | paged rows + failure ledger (inline cap 500) |
| `GET` | `/api/v1/predict/batch/{job_id}/download?file=combined\|summary\|failures\|f001` | `200` CSV | sanitized filename in `Content-Disposition` |
| `DELETE` | `/api/v1/predict/batch/{job_id}` | `200` cancelled | cancels worker + removes temp dir |

Create errors: `422 no_files` / `422 invalid_mapping` /
`413 too_many_files` / `413 batch_too_large` / `422 all_files_rejected`
(with per-file reasons) / `429 rate_limited` / `550 model_unavailable`
(no job created). Reads: `404 job_not_found`, `404 unknown_file`,
`409 job_not_finished`, `400 invalid_download`, `400 invalid_template_style`.

Rate limiting: 60 req/min/IP, with `/health`, `/api/v1/status` and all
job-scoped `GET/DELETE /api/v1/predict/batch/…` exempt (polling must never
429); the batch `POST` itself stays limited.

---

## 3. Limits (server-side, echoed in every `limits` object)

| Limit | Value |
|---|---|
| Files per batch | 200 |
| Per file | 10 MB |
| Per batch | 100 MB (+5 MB multipart slack, rejected from `Content-Length` before buffering) |
| Rows per file | 50,000 |
| Rows per batch | 500,000 |
| Inference chunk | 500 rows |
| Results page | default 100 / max 500 |
| Failure ledger in API | first 500 (full list in failures CSV) |
| Job TTL | 1 hour (lazy + periodic sweep, `atexit` cleanup) |

## 4. Schema, validation & safety

- **Canonical inputs:** `flight_number` (optional if `carrier` present),
  `carrier` (optional if `flight_number` present), `origin`, `destination`,
  `date`. Aliases auto-resolved per file; BTS `Year+Month+DayOfMonth` and
  `Reporting_Airline+Flight_Number_Reporting_Airline` constructed when needed;
  optional one global manual mapping.
- **Label/outcome columns excluded** (`DepDelay15`, `ArrDelay`, `Cancelled`,
  `label`, `target`, …) with a warning — never fed to the model.
- **Vocabulary:** carriers `AA DL UA B6 WN F9 AS`, airports `JFK LAX SFO ORD
  SEA`. Unknown values are rejected **row-by-row with a reason** — never
  remapped to index 0 (unlike the legacy single-predict path).
- **Partial validation (chosen design):** valid rows are predicted, invalid
  rows are rejected with `column + error_code + detail`, everything lands in a
  downloadable failure ledger. Rows/files are never silently truncated or
  discarded; duplicate files and duplicate rows are detected, reported and
  kept.
- **Error codes — file level:** `missing_filename`, `unsupported_extension`,
  `empty_file`, `unreadable_file`, `unreadable_csv`, `invalid_headers`,
  `duplicate_headers`, `missing_required_columns`, `too_many_rows`,
  `file_too_large`, `batch_too_large`, `encoding_error`, `binary_content`,
  `upload_failed`, `model_unavailable`.
- **Error codes — row level:** `missing_value`, `unknown_carrier`,
  `unknown_airport`, `invalid_flight_number`, `flight_number_mismatch`,
  `invalid_date`, `formula_input`.
- **Safety:** in-memory job store + per-job temp dir under
  `%TEMP%/aerodelay_batch_jobs` (outside the repo); filenames sanitized
  (path components stripped) and stored under generated ids → no path
  traversal; no server path/credential in any response; CSV-injection guard on
  export; background processing is an in-process thread pool — **no Redis,
  no Celery**; inference is chunked (500 rows) through a byte-offset indexed
  sink → bounded memory.
- **Honesty:** if the model can't run → `550 model_unavailable`, no job, no
  score. Probabilities are raw, uncalibrated model outputs; risk bands
  (`High ≥ 0.7`, `Medium ≥ 0.4`, `Low < 0.4`) and the `0.5` class threshold
  are echoed in `summary` and labelled as model output, not certainty.

---

## 5. Test results (actual output, 2026-11-08)

| Suite | Command | Result |
|---|---|---|
| Batch API | `python tests\test_batch_api.py` | **83/83 checks passed**, exit 0 — incl. 105-file batch, duplicates kept, traversal stripped, TTL sweep, rate-limit split, model parity vs `run_prediction`, CSV-injection neutralisation, model-unavailable → 550 |
| Phase 5.3 API regression | `python tests\test_phase53_api.py` | **32/32 PASSED, 0 FAILED**, exit 0 (run again after batch wiring — no regressions) |
| Phase 5.3 live (real HTTP + provider) | `python tests\test_phase53_live.py` | **21/21 PASSED, 0 FAILED**, exit 0 |
| Full pytest | `python -m pytest tests/ -q` | **80 passed**, exit 0 (69 pre-existing + 11 batch groups via a pytest bridge fixture added to the standalone suite) |
| Full Playwright | `npx playwright test` | **62 passed, 0 failed** (2.4 min) = 43 pre-existing + 13 new batch tests + 6 responsive viewport checks for `/batch` |
| TypeScript | `npx tsc --noEmit` | Fails **only** on the 4 pre-existing legacy files (§6) — all new/active files type-check clean (verified with a scoped `tsc` run: no output) |

New batch E2E coverage (13): initial state & disabled run, template
downloads, queue add/remove/clear with counts, client pre-checks (non-CSV,
empty), duplicate flag-but-kept, column-mapping round-trip to a real
prediction, clean batch (6 rows, charts, model version, downloads, reset),
partial failure (5 rows → 2 predicted / 3 rejected with codes), schema-breaking
file rejected while the rest scores (error code surfaced in the results
table), SIMULATED `all_files_rejected` 422, SIMULATED `model_unavailable` 550
(no fabricated results), SIMULATED backend-down, and mobile 390 px layout
(no horizontal overflow). The `/batch` page is additionally covered at
360/390/430/768/1024/1440 px by `responsive.spec.js`.

External providers are mocked or absent from every batch test — no live
AviationStack calls are made by the batch feature.

---

## 6. Known limitations (honest list)

1. **Model provenance** — the served model is the Phase 5.1 compatibility
   artifact (`LogisticRegression`, 654 features,
   `Phase 2 Ensemble v2.1 (retrained)`, metadata accuracy 0.4961 vs the
   original Phase 2 0.7132, trained on **synthetic** data). Batch predictions
   are real outputs of that model, not production-meaningful risk estimates.
   See `PHASE53_FINAL_VERIFICATION.md` §11 (R2).
2. **Restricted vocabulary** — only 7 carriers and 5 airports are accepted.
   Real-world CSVs with other values will have those rows rejected (by design:
   better a reason than a silent wrong answer).
3. **`tsc --noEmit` fails on 4 legacy files** — `app/prediction.tsx`,
   `app/analytics.tsx`, `app/tracking.tsx`, `app/ModelsPage.tsx` contain
   broken JSX from before the Phase 5.3 rewrite. They are unreferenced (no
   import, not routes — routes use the `*/page.tsx` variants) and were left
   untouched to avoid overwriting user work. They predate this sprint and are
   excluded from the app.
4. **`npm audit`: 2 vulnerabilities** (`next` critical, `postcss` high) — left
   unfixed to keep the pinned Next 14.2.4 build verified (R1).
5. **In-memory job store** — jobs do not survive a backend restart and are
   not shared across worker processes; single-process deployment assumed.
6. **1-hour TTL** — downloads expire an hour after creation (by design).
7. **Batch `POST` shares the 60 req/min/IP limiter** — uploading >60 batches
   from one IP within a minute returns 429 (individual job polling is exempt).
8. **Scale verified to 105 files / 213 rows in tests** — the 200-file,
   100 MB, 500k-row limits are enforced by code and unit-tested at the limit
   boundaries, but a full 500k-row batch was not run end-to-end in this
   environment (would take minutes of inference; not attempted).
9. Known open defects R3–R6 (AviationStack quota, external health monitor,
   offline fonts, no automated visual/aesthetic review) are unchanged — see
   `PHASE53_FINAL_VERIFICATION.md` §11.

---

## 7. How to run

```powershell
# Backend (port 8000) — from the project root
python start_backend.py

# Frontend (port 3000) — from C:\aero-frontend
npx next dev -p 3000

# Backend tests
python tests\test_batch_api.py        # 83 checks (also pytest-compatible)
python tests\test_phase53_api.py      # 32 checks
python tests\test_phase53_live.py     # 21 checks (needs both servers)
python -m pytest tests/ -q            # 80 tests

# Frontend tests (both servers running)
npx playwright test                   # 62 tests
npx tsc --noEmit                      # fails only on the 4 legacy files (§6.3)
```
