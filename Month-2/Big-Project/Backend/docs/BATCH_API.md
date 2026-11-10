# Batch Prediction API

`POST/GET/DELETE /api/v1/predict/batch…` — bulk CSV delay-risk scoring served
by the FastAPI backend (`app_backend.py` + `batch_prediction.py`).

- Base URL: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs` (search "Batch Prediction")
- Input schema & limits: [`docs/CSV_TEMPLATE.md`](CSV_TEMPLATE.md)
- No authentication is required for local use. An optional `Authorization`
  header is accepted but not enforced.
- Rate limit: 60 requests/min/IP. **Exempt:** `/health`, `/api/v1/status`,
  and every job-scoped `GET/DELETE /api/v1/predict/batch/{job_id}…`
  (polling must never be throttled). The `POST` create endpoint **is** limited.

## Endpoints at a glance

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/predict/batch` | Upload CSVs, create a job → `202` |
| `GET` | `/api/v1/predict/batch/template` | Download a CSV template |
| `GET` | `/api/v1/predict/batch/{job_id}` | Job status / progress |
| `GET` | `/api/v1/predict/batch/{job_id}/results` | Summary + paged rows + failure ledger |
| `GET` | `/api/v1/predict/batch/{job_id}/download` | Download a result CSV |
| `DELETE` | `/api/v1/predict/batch/{job_id}` | Cancel & delete a job (removes temp files) |

---

## 1. Create a job — `POST /api/v1/predict/batch`

`Content-Type: multipart/form-data`

| Field | Type | Notes |
|---|---|---|
| `files` | file (repeatable) | One part per CSV, up to 200 |
| `mapping` | string (optional) | JSON object mapping canonical field → your column name, applied to **all** files. Example: `{"origin":"From","date":"When"}` |

```powershell
curl -X POST http://localhost:8000/api/v1/predict/batch `
  -F "files=@flights_a.csv" -F "files=@flights_b.csv"
```

**Success → `202 Accepted`** with a `BatchJobStatus` body:

```json
{
  "job_id": "6bf9f2d9303f432a",
  "status": "queued",
  "created_at": 1767950000.0,
  "expires_at": 1767953600.0,
  "model_version": "Phase 2 Ensemble v2.1 (retrained)",
  "limits": { "max_files": 200, "max_file_bytes": 10485760,
              "max_batch_bytes": 104857600, "max_rows_per_file": 50000,
              "max_total_rows": 500000, "chunk_rows": 500,
              "job_ttl_seconds": 3600 },
  "progress": { "files_total": 2, "files_done": 0, "rows_total": 0,
                "rows_processed": 0, "percent": 0.0 },
  "files": [ { "file_id": "f001", "name": "flights_a.csv",
               "size_bytes": 2048, "status": "validated",
               "encoding": "utf-8", "rows_total": 3, "warnings": [],
               "error": null, "stats": null } ],
  "accepted_files": 2,
  "rejected_files": 0,
  "warnings": [],
  "summary": null,
  "error": null
}
```

Poll `GET /{job_id}` every ~700 ms until `status` is terminal.

### File statuses
`pending` → `validated` → `processing` → `completed` | `failed` | `rejected`

### Job statuses
`queued` → `processing` → `completed` | `completed_with_errors` | `failed` | `cancelled`

- `completed_with_errors` = the job finished but some files/rows were rejected
  (this is normal partial-failure behaviour, not an outage).
- Row validation + inference run in a lightweight background worker
  (in-process thread pool + worker thread — **no Redis/Celery**).

### Create errors

| HTTP | `error` | When |
|---|---|---|
| `413` | `too_many_files` | More than 200 files |
| `413` | `batch_too_large` | Body over 100 MB (+5 MB multipart slack, checked from `Content-Length` before buffering) |
| `422` | `no_files` | No file parts in the request |
| `422` | `invalid_mapping` | `mapping` is not valid JSON / unknown field / column not in a file |
| `422` | `all_files_rejected` | Every uploaded file failed validation — body includes `files[]` with each file's `error.code`/`error.detail` so the UI can show exactly why |
| `429` | `rate_limited` | Over 60 req/min |
| `550` | `model_unavailable` | Model/preprocessor cannot run → **no job is created**, no fallback score exists |

> A file that fails validation is rejected **individually**; the others proceed.
> Nothing is ever scored with a heuristic: if the model can't run, the API says so.

---

## 2. Job status — `GET /api/v1/predict/batch/{job_id}`

Returns the same `BatchJobStatus` shape as creation, now with live
`progress`, per-file `status`/`rows_total`/`warnings`, and — once finished —
`summary`.

`summary` (present in terminal states):

```json
{
  "files_uploaded": 2, "files_rejected": 1, "files_succeeded": 2,
  "files_failed": 0,
  "rows_total": 6, "rows_predicted": 5, "rows_rejected": 1, "rows_failed": 0,
  "delayed": 1, "on_time": 4, "average_probability": 0.1834,
  "risk_counts": { "Low": 4, "Medium": 1, "High": 0 },
  "class_threshold": 0.5, "risk_threshold_high": 0.7,
  "risk_threshold_medium": 0.4,
  "model_version": "Phase 2 Ensemble v2.1 (retrained)"
}
```

Errors: `404 job_not_found` (unknown, deleted or expired job).

---

## 3. Results — `GET /api/v1/predict/batch/{job_id}/results`

Query parameters:

| Param | Default | Max | Notes |
|---|---|---|---|
| `page` | 1 | — | 1-based |
| `page_size` | 100 | 500 | |
| `file_id` | — | — | Restrict rows to one input file (e.g. `f001`) |

```json
{
  "job_id": "6bf9f2d9303f432a",
  "status": "completed",
  "summary": { "...": "as above" },
  "files": [ { "...": "BatchFileStatus incl. per-file stats" } ],
  "rows": [
    { "file_id": "f001", "file_name": "flights_a.csv", "row_number": 1,
      "carrier": "AA", "flight_number": "AA1234", "origin": "JFK",
      "destination": "LAX", "date": "2022-12-15",
      "predicted_class": 0, "predicted_label": "On time",
      "probability": 0.0613, "risk_level": "Low",
      "model_version": "Phase 2 Ensemble v2.1 (retrained)" }
  ],
  "rows_total": 5, "page": 1, "page_size": 100, "pages": 1,
  "failures": [
    { "file_id": "f002", "file_name": "mixed.csv", "row_number": 2,
      "column": "carrier", "error_code": "unknown_carrier",
      "error_detail": "Carrier 'XX' is not supported (supported: AA, DL, …)." }
  ],
  "failures_total": 1, "failures_truncated": false
}
```

- Rows preserve **upload order and original row numbers** (`row_number` is the
  1-based line number in the source file).
- The inline `failures[]` list is capped at 500 entries
  (`failures_truncated: true` when more exist) — download the failures CSV for
  the complete ledger.
- Errors: `404 job_not_found`, `404 unknown_file` (bad `file_id`).

---

## 4. Downloads — `GET /api/v1/predict/batch/{job_id}/download?file=…`

| `file=` | Produces | Suggested filename |
|---|---|---|
| `combined` (default) | All predictions, one CSV | `aerodelay_batch_{id8}_combined.csv` |
| `summary` | Per-file counts + totals + thresholds | `aerodelay_batch_{id8}_summary.csv` |
| `failures` | Full row-level failure ledger (original row included) | `aerodelay_batch_{id8}_failures.csv` |
| `f001` … | One input file's predictions | sanitised original file name |

Result CSV columns:
`file_id,file_name,row_number,carrier,flight_number,origin,destination,date,predicted_class,predicted_label,probability,risk_level,model_version`

Failure CSV columns:
`file_id,file_name,row_number,column,error_code,error_detail,original_row`

The filename is returned in the `Content-Disposition` header (CORS
`expose_headers` is configured for it).

Errors: `409 job_not_finished` (still running), `400 invalid_download`,
`404 unknown_file`, `404 no_results`.

> CSV-injection guard: exported cells that would begin with `=`, `+`, `-`, `@`,
> tab or CR are prefixed so spreadsheets treat them as text.

---

## 5. Template — `GET /api/v1/predict/batch/template?style=…`

| `style` | Columns | Filename |
|---|---|---|
| `canonical` (default) | `flight_number,origin,destination,date` | `aerodelay_batch_template.csv` |
| `bts` | `Year,Month,DayOfMonth,Reporting_Airline,Origin,Dest` | `aerodelay_batch_template_bts.csv` |

Errors: `400 invalid_template_style`.

---

## 6. Cancel / delete — `DELETE /api/v1/predict/batch/{job_id}`

Cancels a running job (worker stops at the next chunk boundary) and removes
the job's temp directory immediately. Returns `200` with
`{"job_id": "...", "status": "cancelled"}`; afterwards every read of the job
returns `404 job_not_found`.

---

## 7. Job lifecycle, storage & cleanup

- Jobs live **in memory**; uploads/results live in a per-job temp directory
  `%TEMP%/aerodelay_batch_jobs/job-{uuid}` (created outside the repo, never
  under a web-served path).
- **TTL 1 hour** from creation. Expired jobs are swept lazily (on access) and
  by a periodic sweeper; the temp directory is removed with the job.
- `atexit` cleanup removes remaining job directories on process exit.
- Uploaded file names are sanitised (path components stripped, control chars
  removed) and stored under generated `file_id`s — **path traversal is
  impossible**, and no server path, temp path or credential appears in any
  response (covered by the security test group).
- Processing is chunked: rows are validated and scored in 500-row chunks and
  written incrementally through a byte-offset indexed CSV sink, so memory stays
  bounded regardless of batch size. Inference uses
  `run_batch_predict_proba()` — the **same** model and preprocessor as the
  single-prediction endpoint (parity is asserted by the test suite).

## 8. What the numbers mean (honesty notes)

- `probability` is the raw output of the served classifier
  (`LogisticRegression`, 654 features, model version
  `Phase 2 Ensemble v2.1 (retrained)`). It is an **uncalibrated model output,
  not a measured certainty**, and it does not describe operational reality —
  see `PHASE53_FINAL_VERIFICATION.md` for the model's provenance and accuracy
  caveats.
- `predicted_class = 1` ("Delayed") when `probability ≥ 0.5`
  (`class_threshold`); risk bands are `High ≥ 0.7`, `Medium ≥ 0.4`,
  `Low < 0.4`. These thresholds are echoed in `summary` so clients never have
  to hard-code them.
- Rows rejected during validation were **never scored** — they appear only in
  the failure ledger. There is no fallback, heuristic or dummy prediction path.
