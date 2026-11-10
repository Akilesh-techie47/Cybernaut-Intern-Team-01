"""
AeroDelay AI — Batch CSV delay-risk prediction (bulk workflow).

Endpoints
    POST   /api/v1/predict/batch                 upload CSVs -> job id (202)
    GET    /api/v1/predict/batch/{job_id}        status + progress + per-file state
    GET    /api/v1/predict/batch/{job_id}/results  summary + rows + failures (paged)
    GET    /api/v1/predict/batch/{job_id}/download CSV download (combined/summary/failures/per-file)
    GET    /api/v1/predict/batch/template        canonical or BTS-style CSV template
    DELETE /api/v1/predict/batch/{job_id}        cancel + delete temp files

Design
  * Real model only. Every accepted row goes through
    build_feature_vector -> transform_feature_matrix -> predict_proba.
    If inference cannot run the job (or the file) fails with
    model_unavailable; no heuristic/dummy score is ever produced.
  * Job state lives in a module dict guarded by a lock; row output lives in
    per-job temp files with a byte-offset index, so a 500k-row batch is
    never held in RAM and pages are served by seeking, not scanning.
  * Uploads are validated file-by-file (extension, size, encoding, headers,
    columns, exact row count) so the client gets per-file validation in the
    202 response; row-level validation + inference run in a background thread.
  * Filenames never reach the filesystem as given: stored names are
    f001.csv ... inside a per-job temp dir, downloads are served only from
    an allow-list of names, and no server path is ever echoed to a client.
"""

from __future__ import annotations

import asyncio
import atexit
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

# NOTE: no top-level `import app_backend` — app_backend imports this module at
# the end of its own module body. Resolve it lazily through _be() so the
# import order never matters (app_backend first or batch_prediction first).

router = APIRouter(tags=["Batch Prediction"])


def _be():
    """Late-bound reference to app_backend (avoids the circular import)."""
    import app_backend

    return app_backend


# ─── Limits (enforced server-side, echoed to the client) ─────────────────

LIMITS: Dict[str, int] = {
    "max_files": 200,
    "max_file_bytes": 10 * 1024 * 1024,        # 10 MB per file
    "max_batch_bytes": 100 * 1024 * 1024,      # 100 MB per batch
    "max_rows_per_file": 50_000,
    "max_total_rows": 500_000,
    "chunk_rows": 500,
    "job_ttl_seconds": 3600,
    "max_page_size": 500,
    "default_page_size": 100,
    "max_failures_returned": 500,
}

# Multipart overhead allowance for the early Content-Length guard.
_CONTENT_LENGTH_SLACK = 5 * 1024 * 1024

OFFSET_EVERY = 1000          # row -> byte-offset index granularity
_TERMINAL_STATUSES = {"completed", "completed_with_errors", "failed", "cancelled"}

# ─── Column vocabulary ───────────────────────────────────────────────────

# Accepted inputs. `carrier` is optional when `flight_number` is present
# (the carrier is then read from the flight-number prefix) and vice versa:
# a BTS extract has Reporting_Airline but no flight number, which is fine.
CANONICAL_COLUMNS = ("flight_number", "carrier", "origin", "destination", "date")
REQUIRED_COLUMNS = ("flight_number", "origin", "destination", "date")
OPTIONAL_COLUMNS = ("carrier",)

_ALIAS_BASE: Dict[str, set] = {
    "flight_number": {
        "flightnumber", "flightno", "flightnum", "flightid", "flight",
        "flightnumberreportingairline", "flightnumberreportingcarrier",
        "reportingflightnumber", "iataflightnumber",
    },
    "carrier": {
        "carrier", "airline", "airlinecode", "iatacode", "operatingairline",
        "marketingairline", "reportingairline",
    },
    "origin": {
        "origin", "originiata", "originairport", "departureairport",
        "departingairport", "from", "orig",
    },
    "destination": {
        "destination", "dest", "destiata", "destinationairport",
        "arrivalairport", "arrivingairport", "to",
    },
    "date": {
        "date", "flightdate", "depdate", "departuredate", "caldate",
        "flightday", "scheduledate", "scheduledflightdate",
    },
}

# Label / outcome columns are recognised so they can be EXCLUDED from the
# prediction inputs (they are never fed to the model).
LABEL_COLUMNS = {
    "depdelay15", "depdel15", "delay15", "delayed15", "isdelayed",
    "depdelay", "depdelayminutes", "depdelaygroup",
    "arrdelay", "arrdelayminutes", "arrdel15", "arrdelay15",
    "cancelled", "diverted",
    "label", "target", "y",
}

# BTS multi-column construction rules (only used when the single column is
# absent). year + month + dayofmonth -> date;
# Reporting_Airline + Flight_Number_Reporting_Airline -> flight_number.
_DATE_PART_KEYS = (("year", "month", "dayofmonth"), ("year", "month", "day"))
_FLIGHT_PART_KEYS = (("reportingairline", "flightnumberreportingairline"),)

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d %H:%M")

RESULT_COLUMNS = [
    "file_id", "file_name", "row_number", "carrier", "flight_number",
    "origin", "destination", "date", "predicted_class", "predicted_label",
    "probability", "risk_level", "model_version",
]
FAILURE_COLUMNS = [
    "file_id", "file_name", "row_number", "column", "error_code",
    "error_detail", "original_row",
]
SUMMARY_COLUMNS = [
    "job_id", "status", "model_version", "file_id", "file_name",
    "file_status", "rows_total", "rows_predicted", "rows_rejected",
    "delayed", "on_time", "average_probability", "risk_low", "risk_medium",
    "risk_high",
]

TEMPLATE_COLUMNS = ["flight_number", "origin", "destination", "date"]
TEMPLATE_ROWS = [
    ["AA1234", "JFK", "LAX", "2022-12-15"],
    ["DL456", "SFO", "SEA", "2022-12-16"],
    ["UA789", "ORD", "JFK", "2022-12-17"],
]
BTS_TEMPLATE_COLUMNS = [
    "Year", "Month", "DayOfMonth", "Reporting_Airline", "Origin", "Dest",
]
BTS_TEMPLATE_ROWS = [
    ["2022", "12", "15", "AA", "JFK", "LAX"],
    ["2022", "12", "16", "DL", "SFO", "SEA"],
    ["2022", "12", "17", "UA", "ORD", "JFK"],
]


# ─── Response models ─────────────────────────────────────────────────────

class BatchFileError(BaseModel):
    code: str
    detail: str


class BatchRiskCounts(BaseModel):
    Low: int = 0
    Medium: int = 0
    High: int = 0


class BatchFileStats(BaseModel):
    rows_predicted: int = 0
    rows_rejected: int = 0
    delayed: int = 0
    on_time: int = 0
    average_probability: Optional[float] = None
    risk_counts: BatchRiskCounts = Field(default_factory=BatchRiskCounts)


class BatchFileStatus(BaseModel):
    file_id: str
    name: str
    size_bytes: int
    status: str
    encoding: Optional[str] = None
    rows_total: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[BatchFileError] = None
    stats: Optional[BatchFileStats] = None


class BatchProgress(BaseModel):
    files_total: int = 0
    files_done: int = 0
    rows_total: int = 0
    rows_processed: int = 0
    percent: float = 0.0


class BatchLimits(BaseModel):
    max_files: int
    max_file_bytes: int
    max_batch_bytes: int
    max_rows_per_file: int
    max_total_rows: int
    chunk_rows: int
    job_ttl_seconds: int


class BatchSummary(BaseModel):
    files_uploaded: int = 0
    files_rejected: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    rows_total: int = 0
    rows_predicted: int = 0
    rows_rejected: int = 0
    rows_failed: int = 0
    delayed: int = 0
    on_time: int = 0
    average_probability: Optional[float] = None
    risk_counts: BatchRiskCounts = Field(default_factory=BatchRiskCounts)
    class_threshold: float
    risk_threshold_high: float
    risk_threshold_medium: float
    model_version: str


class BatchJobStatus(BaseModel):
    job_id: str
    status: str
    created_at: float
    expires_at: float
    model_version: str
    limits: BatchLimits
    progress: BatchProgress
    files: List[BatchFileStatus]
    accepted_files: int = 0
    rejected_files: int = 0
    warnings: List[str] = Field(default_factory=list)
    summary: Optional[BatchSummary] = None
    error: Optional[BatchFileError] = None


class BatchRow(BaseModel):
    file_id: str
    file_name: str
    row_number: int
    carrier: str
    flight_number: str
    origin: str
    destination: str
    date: str
    predicted_class: int
    predicted_label: str
    probability: float
    risk_level: str
    model_version: str


class BatchFailure(BaseModel):
    file_id: str
    file_name: str
    row_number: int
    column: str
    error_code: str
    error_detail: str


class BatchResults(BaseModel):
    job_id: str
    status: str
    summary: BatchSummary
    files: List[BatchFileStatus]
    rows: List[BatchRow]
    rows_total: int
    page: int
    page_size: int
    pages: int
    failures: List[BatchFailure]
    failures_total: int
    failures_truncated: bool


# ─── Job store ───────────────────────────────────────────────────────────

_JOBS_ROOT = Path(tempfile.gettempdir()) / "aerodelay_batch_jobs"
_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.RLock()
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="batch-validate")


class BatchFileFailure(Exception):
    """File-level validation failure carrying an API error code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _prepare_root() -> None:
    """Create the job root and prune job dirs left behind by dead processes."""
    try:
        _JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    cutoff = time.time() - 24 * 3600
    try:
        for path in _JOBS_ROOT.glob("job-*"):
            try:
                if path.stat().st_mtime < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                continue
    except OSError:
        pass


def _cleanup_on_exit() -> None:
    with _JOBS_LOCK:
        jobs = list(_JOBS.values())
        _JOBS.clear()
    for job in jobs:
        _remove_job_dir(job)


def _remove_job_dir(job: Dict[str, Any]) -> None:
    path = job.get("dir")
    if not path:
        return
    for _ in range(3):
        try:
            shutil.rmtree(path, ignore_errors=False)
            return
        except OSError:
            time.sleep(0.1)
    shutil.rmtree(path, ignore_errors=True)


def _new_job() -> Dict[str, Any]:
    job_id = uuid.uuid4().hex
    job_dir = _JOBS_ROOT / f"job-{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    job: Dict[str, Any] = {
        "job_id": job_id,
        "dir": str(job_dir),
        "status": "queued",
        "created_at": now,
        "expires_at": now + LIMITS["job_ttl_seconds"],
        "model_version": _be().get_model_version(),
        "files": [],
        "warnings": [],
        "error": None,
        "total_bytes": 0,
        "progress": {
            "files_total": 0,
            "files_done": 0,
            "rows_total": 0,
            "rows_processed": 0,
            "percent": 0.0,
        },
        "io_lock": threading.RLock(),
        "result_sink": None,
        "failure_sink": None,
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    return job


def _sweep_expired() -> None:
    now = time.time()
    with _JOBS_LOCK:
        expired = [jid for jid, j in _JOBS.items() if j["expires_at"] <= now]
        jobs = [_JOBS.pop(jid) for jid in expired]
    for job in jobs:
        job["status"] = "cancelled"
        _remove_job_dir(job)


def _require_job(job_id: str) -> Dict[str, Any]:
    _sweep_expired()
    if not job_id or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(
            status_code=404,
            detail={
                "error": "job_not_found",
                "detail": "Batch job not found or expired.",
            },
        )
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "job_not_found",
                "detail": "Batch job not found or expired.",
            },
        )
    return job


def _find_file(job: Dict[str, Any], file_id: str) -> Optional[Dict[str, Any]]:
    for entry in job["files"]:
        if entry["file_id"] == file_id:
            return entry
    return None


# ─── Small helpers ───────────────────────────────────────────────────────

def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _sanitize_filename(name: str) -> str:
    """Strip any path component and unsafe characters (path-traversal guard)."""
    name = (name or "").replace("\x00", "")
    name = name.replace("\\", "/").split("/")[-1]      # drop directories
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if not name:
        return "file.csv"
    if len(name) > 150:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 5:
            name = stem[:150 - len(ext) - 1] + "." + ext
        else:
            name = name[:150]
    return name


def _csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formula injection in exported CSV cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _decode_csv(data: bytes) -> Tuple[str, str]:
    """Decode a CSV. Returns (text, encoding) or raises BatchFileFailure."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        raise BatchFileFailure(
            "encoding_error",
            "File is UTF-16 encoded. Save it as UTF-8 (or CP1252) CSV and retry.",
        )
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise BatchFileFailure(
        "encoding_error",
        "File is not valid UTF-8 or CP1252 text.",
    )


def _normalize_date(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            from datetime import datetime

            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _risk_level(probability: float) -> str:
    be = _be()
    if probability >= be.RISK_HIGH_THRESHOLD:
        return "High"
    if probability >= be.RISK_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


# ─── CSV sinks with a byte-offset index (bounded-memory pagination) ─────

class _CsvSink:
    """Append-only CSV file + offsets of every OFFSET_EVERY-th data row."""

    def __init__(self, path: Path, columns: List[str], mode: str = "w"):
        self.path = path
        self.columns = columns
        self.handle = open(path, mode, newline="", encoding="utf-8")
        self.writer = csv.writer(self.handle, lineterminator="\n")
        if mode == "w":
            self.writer.writerow([_csv_safe(c) for c in columns])
        self.offsets: List[int] = [self.handle.tell()]
        self.count = 0

    def write(self, row: List[Any]) -> None:
        self.writer.writerow([_csv_safe(v) for v in row])
        self.count += 1
        if self.count % OFFSET_EVERY == 0:
            self.offsets.append(self.handle.tell())

    def append_file(self, other: Path) -> None:
        """Append every data row of another CSV (per-file -> combined)."""
        with open(other, "r", newline="", encoding="utf-8") as src:
            reader = csv.reader(src)
            next(reader, None)  # skip header
            for row in reader:
                self.writer.writerow(row)
                self.count += 1
                if self.count % OFFSET_EVERY == 0:
                    self.offsets.append(self.handle.tell())

    def flush(self) -> None:
        try:
            self.handle.flush()
        except (OSError, ValueError):
            pass

    def close(self) -> None:
        try:
            self.handle.flush()
            self.handle.close()
        except (OSError, ValueError):
            pass

    def snapshot(self) -> Dict[str, Any]:
        self.flush()
        return {
            "path": str(self.path),
            "offsets": list(self.offsets),
            "count": self.count,
        }


def _sink_view(sink: Any) -> Optional[Dict[str, Any]]:
    """Accept either a live _CsvSink or an already-frozen snapshot dict."""
    if sink is None:
        return None
    if isinstance(sink, _CsvSink):
        return sink.snapshot()
    if isinstance(sink, dict):
        return sink
    return None


def _sink_count(sink: Any) -> int:
    view = _sink_view(sink)
    return int(view["count"]) if view else 0


def _read_page(
    sink: Any, start: int, limit: int
) -> List[List[str]]:
    view = _sink_view(sink)
    if not view or start < 0 or limit <= 0:
        return []
    offsets = view.get("offsets") or []
    if not offsets:
        return []
    idx = min(start // OFFSET_EVERY, len(offsets) - 1)
    out: List[List[str]] = []
    try:
        with open(view["path"], "r", newline="", encoding="utf-8") as handle:
            handle.seek(offsets[idx])
            for _ in range(start - idx * OFFSET_EVERY):
                if not handle.readline():
                    return []
            reader = csv.reader(handle)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                out.append(row)
    except (OSError, ValueError, IndexError):
        return []
    return out


# ─── Phase A: upload + file-level validation ─────────────────────────────

def _resolve_columns(
    columns: List[str], mapping: Optional[Dict[str, str]]
) -> Dict[str, Any]:
    """Map raw CSV headers onto the model's canonical inputs."""
    norms: Dict[str, str] = {}
    for col in columns:
        key = _norm(col)
        if key and key not in norms:
            norms[key] = col

    resolved: Dict[str, Any] = {}
    mapping = mapping or {}

    for canon in CANONICAL_COLUMNS:
        if canon in mapping:
            src = mapping[canon]
            resolved[canon] = (
                {"kind": "column", "column": src} if src in columns else None
            )
            continue
        hit = next((norms[a] for a in _ALIAS_BASE[canon] if a in norms), None)
        resolved[canon] = {"kind": "column", "column": hit} if hit else None

    # Multi-column construction (BTS style) when the single column is absent.
    if not resolved.get("date"):
        for keys in _DATE_PART_KEYS:
            parts = [norms.get(k) for k in keys]
            if all(parts):
                resolved["date"] = {"kind": "parts", "columns": parts}
                break
    if not resolved.get("flight_number"):
        for keys in _FLIGHT_PART_KEYS:
            parts = [norms.get(k) for k in keys]
            if all(parts):
                resolved["flight_number"] = {"kind": "parts", "columns": parts}
                break

    used = set()
    for spec in resolved.values():
        if not spec:
            continue
        if spec["kind"] == "column":
            used.add(spec["column"])
        else:
            used.update(spec["columns"])

    labels = [c for c in columns if _norm(c) in LABEL_COLUMNS and c not in used]
    extras = [c for c in columns if c not in used and c not in labels]

    missing = [
        c for c in REQUIRED_COLUMNS
        if not resolved.get(c)
        and not (c == "flight_number" and resolved.get("carrier"))
    ]

    return {
        "resolved": resolved,
        "missing": missing,
        "labels": labels,
        "extras": extras,
    }


def _validate_stored_file(entry: Dict[str, Any], mapping: Optional[Dict[str, str]]) -> None:
    """Decode, parse, resolve columns, count rows. Runs in a worker thread."""
    path = Path(entry["path"])
    try:
        data = path.read_bytes()
    except OSError:
        entry["status"] = "rejected"
        entry["error"] = {
            "code": "unreadable_file",
            "detail": "Stored upload could not be read.",
        }
        return

    try:
        text, encoding = _decode_csv(data)
        if not text.strip():
            raise BatchFileFailure("empty_file", "File contains no data.")

        # Raw header line (pandas renames duplicates, so read it ourselves).
        first_line = text.split("\n", 1)[0].rstrip("\r")
        try:
            raw_headers = next(csv.reader([first_line]))
        except Exception:
            raise BatchFileFailure("unreadable_csv", "CSV header could not be parsed.")
        stripped = [h.strip() for h in raw_headers]
        if any(not h for h in stripped):
            raise BatchFileFailure(
                "invalid_headers", "CSV header contains an empty column name."
            )
        if len(set(stripped)) != len(stripped):
            dupes = sorted({h for h in stripped if stripped.count(h) > 1})
            raise BatchFileFailure(
                "duplicate_headers",
                "Duplicate column name(s): " + ", ".join(dupes) + ".",
            )

        try:
            header_df = pd.read_csv(
                io.StringIO(text), nrows=0, dtype=str, keep_default_na=False
            )
        except pd.errors.EmptyDataError:
            raise BatchFileFailure("empty_file", "File contains no data.")
        except pd.errors.ParserError as exc:
            raise BatchFileFailure(
                "unreadable_csv", f"Malformed CSV header ({exc})."
            )

        columns = [str(c) for c in header_df.columns]
        resolution = _resolve_columns(columns, mapping)
        if resolution["missing"]:
            raise BatchFileFailure(
                "missing_required_columns",
                "Missing required column(s): "
                + ", ".join(resolution["missing"])
                + ". Download the CSV template for the accepted schema.",
            )

        rows = 0
        try:
            reader = pd.read_csv(
                io.StringIO(text),
                dtype=str,
                keep_default_na=False,
                chunksize=5000,
                on_bad_lines="error",
            )
            for chunk in reader:
                rows += len(chunk)
                if rows > LIMITS["max_rows_per_file"]:
                    raise BatchFileFailure(
                        "too_many_rows",
                        f"File exceeds the {LIMITS['max_rows_per_file']:,} row limit.",
                    )
        except pd.errors.EmptyDataError:
            raise BatchFileFailure("empty_file", "File contains no data.")
        except pd.errors.ParserError as exc:
            raise BatchFileFailure(
                "unreadable_csv",
                f"Malformed CSV data near line {getattr(exc, 'line_number', '?')}.",
            )

        if rows == 0:
            raise BatchFileFailure(
                "empty_file", "File has a header but no data rows."
            )
    except BatchFileFailure as exc:
        entry["status"] = "rejected"
        entry["error"] = {"code": exc.code, "detail": exc.detail}
        return
    except MemoryError:
        entry["status"] = "rejected"
        entry["error"] = {
            "code": "unreadable_csv",
            "detail": "File is too large to parse safely.",
        }
        return
    except Exception:
        entry["status"] = "rejected"
        entry["error"] = {
            "code": "unreadable_csv",
            "detail": "File could not be parsed as CSV.",
        }
        return

    entry["status"] = "validated"
    entry["encoding"] = encoding
    entry["rows_total"] = rows
    entry["resolution"] = resolution
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    del data  # release the raw bytes before the next file is validated

    warnings: List[str] = []
    if resolution["labels"]:
        warnings.append(
            "Excluded label/outcome column(s) from prediction inputs: "
            + ", ".join(resolution["labels"])
        )
    if resolution["extras"]:
        shown = resolution["extras"][:10]
        more = len(resolution["extras"]) - len(shown)
        suffix = f" (+{more} more)" if more > 0 else ""
        warnings.append(
            "Ignored column(s) not used by the model: "
            + ", ".join(shown)
            + suffix
        )
    date_spec = resolution["resolved"].get("date")
    if date_spec and date_spec["kind"] == "parts":
        warnings.append(
            "Built date from " + " + ".join(date_spec["columns"])
        )
    flight_spec = resolution["resolved"].get("flight_number")
    if flight_spec and flight_spec["kind"] == "parts":
        warnings.append(
            "Built flight_number from " + " + ".join(flight_spec["columns"])
        )
    entry["warnings"] = warnings


async def _store_upload(job: Dict[str, Any], file: UploadFile, seq: int) -> Dict[str, Any]:
    """Stream one uploaded file to the job dir, enforcing size/extension limits."""
    entry: Dict[str, Any] = {
        "file_id": f"f{seq:03d}",
        "name": "",
        "size_bytes": 0,
        "status": "pending",
        "encoding": None,
        "rows_total": None,
        "warnings": [],
        "error": None,
        "stats": None,
        "path": None,
        "resolution": None,
        "sha256": None,
        "result_sink": None,
        "failure_sink": None,
    }

    def reject(code: str, detail: str) -> Dict[str, Any]:
        entry["status"] = "rejected"
        entry["error"] = {"code": code, "detail": detail}
        return entry

    raw_name = file.filename or ""
    if not raw_name:
        await file.close()
        return reject("missing_filename", "A file without a filename was uploaded.")

    safe_name = _sanitize_filename(raw_name)
    entry["name"] = safe_name

    if not safe_name.lower().endswith(".csv"):
        await file.close()
        return reject(
            "unsupported_extension",
            f"'{safe_name}' is not a .csv file. Only CSV uploads are accepted.",
        )

    dest = Path(job["dir"]) / f"{entry['file_id']}.csv"
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > LIMITS["max_file_bytes"]:
                    raise BatchFileFailure(
                        "file_too_large",
                        f"'{safe_name}' exceeds the "
                        f"{LIMITS['max_file_bytes'] // (1024 * 1024)} MB per-file limit.",
                    )
                if job["total_bytes"] + size > LIMITS["max_batch_bytes"]:
                    raise BatchFileFailure(
                        "batch_too_large",
                        "This file would push the batch over the "
                        f"{LIMITS['max_batch_bytes'] // (1024 * 1024)} MB total limit.",
                    )
                out.write(chunk)
    except BatchFileFailure as exc:
        dest.unlink(missing_ok=True)
        await file.close()
        return reject(exc.code, exc.detail)
    except Exception:
        dest.unlink(missing_ok=True)
        await file.close()
        return reject(
            "upload_failed", f"'{safe_name}' could not be uploaded."
        )
    finally:
        try:
            await file.close()
        except Exception:
            pass

    if size == 0:
        dest.unlink(missing_ok=True)
        return reject("empty_file", f"'{safe_name}' is empty.")

    # Binary / wrong-content guard before any parsing.
    try:
        with open(dest, "rb") as handle:
            head = handle.read(8192)
    except OSError:
        dest.unlink(missing_ok=True)
        return reject("unreadable_file", f"'{safe_name}' could not be read.")

    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        # UTF-16 contains NUL bytes, so check it before the binary guard and
        # give the user an actionable message instead of "binary file".
        dest.unlink(missing_ok=True)
        return reject(
            "encoding_error",
            f"'{safe_name}' is UTF-16 encoded. Save it as UTF-8 (or CP1252) "
            "CSV and retry.",
        )

    if b"\x00" in head:
        dest.unlink(missing_ok=True)
        return reject(
            "binary_content",
            f"'{safe_name}' looks like a binary file, not a CSV.",
        )

    job["total_bytes"] += size
    entry["size_bytes"] = size
    entry["path"] = str(dest)
    return entry


# ─── Phase B: row validation + real inference ────────────────────────────

def _prepare_frame(
    chunk: pd.DataFrame, resolution: Dict[str, Any]
) -> Tuple[List[Optional[str]], List[str], List[str], List[str], List[str]]:
    """Return parallel lists: flight, carrier, origin, dest, date per row."""
    resolved = resolution["resolved"]

    def column_for(key: str, default: str = "") -> List[str]:
        spec = resolved.get(key)
        if not spec:
            return [default] * len(chunk)
        if spec["kind"] == "column":
            return [str(v) for v in chunk[spec["column"]].tolist()]
        parts = [
            [str(v).strip() for v in chunk[c].tolist()] for c in spec["columns"]
        ]
        if key == "date":
            year, month, day = parts
            return [
                f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                for y, m, d in zip(year, month, day)
            ]
        airline, number = parts
        return [
            re.sub(r"\s+", "", f"{a}{n}") for a, n in zip(airline, number)
        ]

    flights = column_for("flight_number")
    carriers = column_for("carrier")
    origins = column_for("origin")
    dests = column_for("destination")
    dates = column_for("date")
    return flights, carriers, origins, dests, dates


def _check_row(
    flight: str, carrier: str, origin: str, dest: str, date: str
) -> Tuple[Optional[Dict[str, str]], Optional[Tuple[str, str, str]]]:
    """
    Validate one row.

    Returns (values, None) on success or (None, (column, code, detail)) on
    failure. Never coerces an unsupported value into a supported one.
    """
    be = _be()
    fn = (flight or "").strip().upper()
    cr = (carrier or "").strip().upper()
    og = (origin or "").strip().upper()
    dt = (dest or "").strip().upper()
    raw_date = (date or "").strip()

    if not fn and not cr:
        return None, ("flight_number", "missing_value", "flight_number is empty.")

    prefix = fn[:2] if len(fn) >= 2 else ""
    if cr:
        carrier_code = cr
        if prefix and prefix != carrier_code:
            return None, (
                "flight_number",
                "flight_number_mismatch",
                f"flight_number '{fn}' starts with {prefix} but carrier is {carrier_code}.",
            )
    else:
        carrier_code = prefix

    if carrier_code not in be.CARRIER_MAP:
        supported = ", ".join(be.SUPPORTED_CARRIERS)
        return None, (
            "carrier",
            "unknown_carrier",
            f"Carrier '{carrier_code or fn}' is not supported "
            f"(supported: {supported}).",
        )

    if fn:
        if len(fn) > 10:
            return None, (
                "flight_number",
                "invalid_flight_number",
                f"flight_number '{fn}' is longer than 10 characters.",
            )
        rest = fn[2:].strip()
        if not rest:
            return None, (
                "flight_number",
                "invalid_flight_number",
                f"flight_number '{fn}' has no flight number after the airline code.",
            )
        if not rest.isdigit():
            return None, (
                "flight_number",
                "invalid_flight_number",
                f"flight_number '{fn}' must be an airline code followed by digits.",
            )

    if not og:
        return None, ("origin", "missing_value", "origin is empty.")
    if og not in be.AIRPORT_MAP:
        supported = ", ".join(be.SUPPORTED_AIRPORTS)
        return None, (
            "origin",
            "unknown_airport",
            f"Origin '{og}' is not supported (supported: {supported}).",
        )

    if not dt:
        return None, ("destination", "missing_value", "destination is empty.")
    if dt not in be.AIRPORT_MAP:
        supported = ", ".join(be.SUPPORTED_AIRPORTS)
        return None, (
            "destination",
            "unknown_airport",
            f"Destination '{dt}' is not supported (supported: {supported}).",
        )

    iso = _normalize_date(raw_date)
    if iso is None:
        return None, (
            "date",
            "invalid_date",
            f"date '{raw_date}' is not a recognised date (use YYYY-MM-DD).",
        )

    return {
        "carrier": carrier_code,
        "flight_number": fn,
        "origin": og,
        "destination": dt,
        "date": iso,
    }, None


def _process_file(
    job: Dict[str, Any], entry: Dict[str, Any], model_version: str
) -> None:
    """Validate rows chunk-by-chunk and run real model inference."""
    be = _be()
    path = Path(entry["path"])
    resolution = entry["resolution"]
    file_id = entry["file_id"]
    file_name = entry["name"]
    job_dir = Path(job["dir"])

    data = path.read_bytes()
    text, _encoding = _decode_csv(data)
    del data
    if not text.strip():
        raise BatchFileFailure("empty_file", "File contains no data.")

    result_sink = _CsvSink(job_dir / f"results_{file_id}.csv", RESULT_COLUMNS)
    failure_sink = _CsvSink(job_dir / f"failures_{file_id}.csv", FAILURE_COLUMNS)
    entry["result_sink_path"] = str(result_sink.path)
    entry["failure_sink_path"] = str(failure_sink.path)

    stats = {
        "rows_predicted": 0,
        "rows_rejected": 0,
        "delayed": 0,
        "on_time": 0,
        "prob_sum": 0.0,
        "risk_counts": {"Low": 0, "Medium": 0, "High": 0},
    }
    entry["stats"] = stats

    seen: set = set()
    duplicate_rows = 0
    rows_seen = 0

    try:
        reader = pd.read_csv(
            io.StringIO(text),
            dtype=str,
            keep_default_na=False,
            chunksize=LIMITS["chunk_rows"],
            on_bad_lines="error",
        )
        for chunk in reader:
            if job["status"] == "cancelled":
                raise BatchFileFailure("cancelled", "Job was cancelled.")

            flights, carriers, origins, dests, dates = _prepare_frame(
                chunk, resolution
            )
            n_rows = len(chunk)

            valid_values: List[Dict[str, str]] = []
            valid_positions: List[int] = []
            failure_rows: List[List[Any]] = []

            for pos in range(n_rows):
                row_number = rows_seen + pos + 1
                values, error = _check_row(
                    flights[pos], carriers[pos], origins[pos],
                    dests[pos], dates[pos],
                )
                if error is not None:
                    column, code, detail = error
                    failure_rows.append(
                        [
                            file_id,
                            file_name,
                            row_number,
                            column,
                            code,
                            detail,
                            json.dumps(
                                {
                                    "flight_number": flights[pos],
                                    "carrier": carriers[pos],
                                    "origin": origins[pos],
                                    "destination": dests[pos],
                                    "date": dates[pos],
                                },
                                ensure_ascii=False,
                            ),
                        ]
                    )
                    continue

                key = (
                    values["carrier"],
                    values["flight_number"],
                    values["origin"],
                    values["destination"],
                    values["date"],
                )
                if key in seen:
                    duplicate_rows += 1
                else:
                    seen.add(key)

                valid_values.append(values)
                valid_positions.append(pos)

            rows_seen += n_rows

            # Row-level failure ledger (never silently dropped).
            with job["io_lock"]:
                for row in failure_rows:
                    failure_sink.write(row)
                failure_sink.flush()
            stats["rows_rejected"] += len(failure_rows)

            if valid_values:
                raw_rows = []
                for values in valid_values:
                    info = be.FlightInfo(
                        # Only the first two characters feed the model, so a
                        # BTS row without a flight number uses the carrier.
                        flight_number=values["flight_number"] or values["carrier"],
                        origin=values["origin"],
                        destination=values["destination"],
                        date=values["date"],
                    )
                    raw_rows.append(be.build_feature_vector(info))
                raw_matrix = np.vstack(raw_rows)
                transformed = be.transform_feature_matrix(raw_matrix)
                probabilities = be.run_batch_predict_proba(transformed)
                if probabilities is None:
                    raise BatchFileFailure(
                        "model_unavailable",
                        "ML model inference cannot run - no predictions were "
                        "produced for this file (no fallback score is used).",
                    )

                base_row = rows_seen - n_rows
                with job["io_lock"]:
                    for values, position, probability in zip(
                        valid_values, valid_positions, probabilities
                    ):
                        p = float(probability)
                        level = _risk_level(p)
                        predicted_class = int(p >= be.MODEL_CLASS_THRESHOLD)
                        stats["rows_predicted"] += 1
                        stats["prob_sum"] += p
                        stats["risk_counts"][level] += 1
                        if predicted_class == 1:
                            stats["delayed"] += 1
                        else:
                            stats["on_time"] += 1
                        result_sink.write(
                            [
                                file_id,
                                file_name,
                                base_row + position + 1,
                                values["carrier"],
                                values["flight_number"],
                                values["origin"],
                                values["destination"],
                                values["date"],
                                predicted_class,
                                "Delayed" if predicted_class == 1 else "On time",
                                f"{p:.4f}",
                                level,
                                model_version,
                            ]
                        )
                    result_sink.flush()

            with job["io_lock"]:
                job["progress"]["rows_processed"] += n_rows
                total_rows = job["progress"]["rows_total"] or rows_seen
                job["progress"]["percent"] = round(
                    min(
                        100.0,
                        (job["progress"]["rows_processed"] / total_rows) * 100.0,
                    ),
                    1,
                )

            if rows_seen > LIMITS["max_rows_per_file"]:
                raise BatchFileFailure(
                    "too_many_rows",
                    f"File exceeds the {LIMITS['max_rows_per_file']:,} row limit.",
                )

        if rows_seen == 0:
            raise BatchFileFailure(
                "empty_file", "File has a header but no data rows."
            )
    finally:
        result_sink.close()
        failure_sink.close()

    if duplicate_rows:
        entry["warnings"].append(
            f"{duplicate_rows} exact duplicate row(s) detected; all rows were "
            "still predicted in input order."
        )


def _publish_file(job: Dict[str, Any], entry: Dict[str, Any]) -> None:
    """Append a successfully processed file's rows to the combined ledgers."""
    job_dir = Path(job["dir"])
    result_path = job_dir / f"results_{entry['file_id']}.csv"
    failure_path = job_dir / f"failures_{entry['file_id']}.csv"

    with job["io_lock"]:
        if job["result_sink"] is None:
            job["result_sink"] = _CsvSink(
                job_dir / "results.csv", RESULT_COLUMNS
            )
        if job["failure_sink"] is None:
            job["failure_sink"] = _CsvSink(
                job_dir / "failures.csv", FAILURE_COLUMNS
            )
        if result_path.exists():
            job["result_sink"].append_file(result_path)
            job["result_sink"].flush()
        if failure_path.exists():
            job["failure_sink"].append_file(failure_path)
            job["failure_sink"].flush()

    entry["result_sink"] = _sink_snapshot(result_path)
    entry["failure_sink"] = _sink_snapshot(failure_path)


def _sink_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    """Build an offset index for an already-written CSV by re-reading it."""
    if not path.exists():
        return None
    offsets: List[int] = []
    count = 0
    try:
        with open(path, "rb") as handle:
            header_end = handle.readline()
            offsets.append(handle.tell())
            for line in handle:
                count += 1
                if count % OFFSET_EVERY == 0:
                    offsets.append(handle.tell())
    except OSError:
        return None
    return {"path": str(path), "offsets": offsets, "count": count}


def _process_job(job_id: str) -> None:
    """Background worker: validate rows and run inference for every file."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        return
    with job["io_lock"]:
        if job["status"] == "cancelled":
            return
        job["status"] = "processing"

    be = _be()
    if not be.is_model_ready():
        with job["io_lock"]:
            job["status"] = "failed"
            job["error"] = {
                "code": "model_unavailable",
                "detail": "ML model inference cannot run. No fallback or "
                          "heuristic predictions were produced.",
            }
            job["progress"]["percent"] = 100.0
        return

    model_version = job["model_version"]
    for entry in job["files"]:
        if entry["status"] != "validated":
            continue
        if job["status"] == "cancelled":
            break
        with job["io_lock"]:
            entry["status"] = "processing"
        try:
            _process_file(job, entry, model_version)
        except BatchFileFailure as exc:
            if exc.code == "cancelled":
                return
            entry["status"] = "failed"
            entry["error"] = {"code": exc.code, "detail": exc.detail}
            entry["stats"] = None
            for suffix in (f"results_{entry['file_id']}.csv",
                           f"failures_{entry['file_id']}.csv"):
                try:
                    (Path(job["dir"]) / suffix).unlink(missing_ok=True)
                except OSError:
                    pass
            entry["result_sink"] = None
            entry["failure_sink"] = None
        except FileNotFoundError:
            if job["status"] == "cancelled":
                return
            entry["status"] = "failed"
            entry["error"] = {
                "code": "upload_failed",
                "detail": "The uploaded file could not be read again.",
            }
            entry["stats"] = None
        except Exception:
            if job["status"] == "cancelled":
                return
            entry["status"] = "failed"
            entry["error"] = {
                "code": "processing_error",
                "detail": "Unexpected error while processing this file.",
            }
            entry["stats"] = None
        else:
            entry["status"] = "completed"
            _publish_file(job, entry)
        finally:
            with job["io_lock"]:
                job["progress"]["files_done"] += 1

    _finalize(job)


def _build_summary(job: Dict[str, Any]) -> Dict[str, Any]:
    be = _be()
    files = job["files"]
    accepted = [f for f in files if f["status"] != "rejected"]
    succeeded = [f for f in files if f["status"] == "completed"]
    failed = [f for f in files if f["status"] == "failed"]
    rejected = [f for f in files if f["status"] == "rejected"]

    rows_total = sum(f.get("rows_total") or 0 for f in accepted)
    rows_predicted = 0
    rows_rejected = 0
    delayed = 0
    on_time = 0
    prob_sum = 0.0
    risk_counts = {"Low": 0, "Medium": 0, "High": 0}

    for entry in succeeded:
        stats = entry.get("stats") or {}
        rows_predicted += stats.get("rows_predicted", 0)
        rows_rejected += stats.get("rows_rejected", 0)
        delayed += stats.get("delayed", 0)
        on_time += stats.get("on_time", 0)
        prob_sum += stats.get("prob_sum", 0.0)
        counts = stats.get("risk_counts") or {}
        for level in risk_counts:
            risk_counts[level] += counts.get(level, 0)

    rows_failed = sum(f.get("rows_total") or 0 for f in failed)

    return {
        "files_uploaded": len(files),
        "files_rejected": len(rejected),
        "files_succeeded": len(succeeded),
        "files_failed": len(failed),
        "rows_total": rows_total,
        "rows_predicted": rows_predicted,
        "rows_rejected": rows_rejected,
        "rows_failed": rows_failed,
        "delayed": delayed,
        "on_time": on_time,
        "average_probability": (
            round(prob_sum / rows_predicted, 4) if rows_predicted else None
        ),
        "risk_counts": risk_counts,
        "class_threshold": be.MODEL_CLASS_THRESHOLD,
        "risk_threshold_high": be.RISK_HIGH_THRESHOLD,
        "risk_threshold_medium": be.RISK_MEDIUM_THRESHOLD,
        "model_version": job["model_version"],
    }


def _write_summary_csv(job: Dict[str, Any], summary: Dict[str, Any]) -> None:
    path = Path(job["dir"]) / "summary.csv"
    try:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(SUMMARY_COLUMNS)

            def row_for(file_id: str, name: str, status: str,
                        stats: Dict[str, Any], rows_total: Any) -> List[Any]:
                counts = (stats or {}).get("risk_counts") or {}
                avg = (stats or {}).get("average_probability")
                return [
                    job["job_id"],
                    job["status"],
                    job["model_version"],
                    file_id,
                    name,
                    status,
                    rows_total,
                    (stats or {}).get("rows_predicted", 0),
                    (stats or {}).get("rows_rejected", 0),
                    (stats or {}).get("delayed", 0),
                    (stats or {}).get("on_time", 0),
                    "" if avg is None else f"{avg:.4f}",
                    counts.get("Low", 0),
                    counts.get("Medium", 0),
                    counts.get("High", 0),
                ]

            for entry in job["files"]:
                stats = entry.get("stats")
                if stats is not None and "average_probability" not in stats:
                    predicted = stats.get("rows_predicted") or 0
                    stats["average_probability"] = (
                        round(stats.get("prob_sum", 0.0) / predicted, 4)
                        if predicted
                        else None
                    )
                writer.writerow(
                    row_for(
                        entry["file_id"],
                        entry["name"],
                        entry["status"],
                        stats if stats is not None else {},
                        entry.get("rows_total") or 0,
                    )
                )

            writer.writerow(
                row_for(
                    "TOTAL",
                    "(all files)",
                    job["status"],
                    {
                        "rows_predicted": summary["rows_predicted"],
                        "rows_rejected": summary["rows_rejected"],
                        "delayed": summary["delayed"],
                        "on_time": summary["on_time"],
                        "average_probability": summary["average_probability"],
                        "risk_counts": summary["risk_counts"],
                    },
                    summary["rows_total"],
                )
            )
    except OSError:
        pass


def _finalize(job: Dict[str, Any]) -> None:
    with job["io_lock"]:
        # Always release the combined sinks first, even for a cancelled job.
        for sink_key in ("result_sink", "failure_sink"):
            sink = job.get(sink_key)
            if isinstance(sink, _CsvSink):
                sink.close()
                job[sink_key] = sink.snapshot()

        if job["status"] == "cancelled":
            return

        summary = _build_summary(job)
        job["summary_cache"] = summary

        if summary["files_succeeded"] == 0:
            job["status"] = "failed"
            if job["error"] is None:
                job["error"] = {
                    "code": "all_files_failed",
                    "detail": "No file could be processed. See per-file errors.",
                }
        elif summary["files_failed"] > 0 or summary["rows_rejected"] > 0:
            job["status"] = "completed_with_errors"
        else:
            job["status"] = "completed"

        _write_summary_csv(job, summary)

        job["progress"]["percent"] = 100.0
        job["progress"]["files_done"] = job["progress"]["files_total"]


# ─── Payload builders ────────────────────────────────────────────────────

def _stats_payload(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    stats = entry.get("stats")
    if stats is None:
        return None
    predicted = stats.get("rows_predicted") or 0
    return {
        "rows_predicted": predicted,
        "rows_rejected": stats.get("rows_rejected", 0),
        "delayed": stats.get("delayed", 0),
        "on_time": stats.get("on_time", 0),
        "average_probability": (
            round(stats.get("prob_sum", 0.0) / predicted, 4) if predicted else None
        ),
        "risk_counts": dict(stats.get("risk_counts") or {}),
    }


def _file_payload(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "file_id": entry["file_id"],
        "name": entry["name"],
        "size_bytes": entry.get("size_bytes", 0),
        "status": entry["status"],
        "encoding": entry.get("encoding"),
        "rows_total": entry.get("rows_total"),
        "warnings": list(entry.get("warnings") or []),
        "error": entry.get("error"),
        "stats": _stats_payload(entry),
    }


def _status_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    be = _be()
    with job["io_lock"]:
        files = [_file_payload(f) for f in job["files"]]
        progress = dict(job["progress"])
        summary = job.get("summary_cache") or _build_summary(job)
        terminal = job["status"] in _TERMINAL_STATUSES
        payload = {
            "job_id": job["job_id"],
            "status": job["status"],
            "created_at": job["created_at"],
            "expires_at": job["expires_at"],
            "model_version": job["model_version"],
            "limits": dict(LIMITS),
            "progress": progress,
            "files": files,
            "accepted_files": sum(
                1 for f in job["files"] if f["status"] != "rejected"
            ),
            "rejected_files": sum(
                1 for f in job["files"] if f["status"] == "rejected"
            ),
            "warnings": list(job.get("warnings") or []),
            "summary": summary if terminal else None,
            "error": job.get("error"),
        }
    return payload


def _row_payload(raw: List[str]) -> Optional[Dict[str, Any]]:
    if len(raw) < len(RESULT_COLUMNS):
        return None
    data = dict(zip(RESULT_COLUMNS, raw))
    try:
        return {
            "file_id": data["file_id"],
            "file_name": data["file_name"],
            "row_number": int(data["row_number"]),
            "carrier": data["carrier"],
            "flight_number": data["flight_number"],
            "origin": data["origin"],
            "destination": data["destination"],
            "date": data["date"],
            "predicted_class": int(data["predicted_class"]),
            "predicted_label": data["predicted_label"],
            "probability": float(data["probability"]),
            "risk_level": data["risk_level"],
            "model_version": data["model_version"],
        }
    except (TypeError, ValueError):
        return None


def _failure_payload(raw: List[str]) -> Optional[Dict[str, Any]]:
    if len(raw) < len(FAILURE_COLUMNS):
        return None
    data = dict(zip(FAILURE_COLUMNS, raw))
    try:
        return {
            "file_id": data["file_id"],
            "file_name": data["file_name"],
            "row_number": int(data["row_number"]),
            "column": data["column"],
            "error_code": data["error_code"],
            "error_detail": data["error_detail"],
        }
    except (TypeError, ValueError):
        return None


# ─── Endpoints ───────────────────────────────────────────────────────────

def _all_rejected_response(entries: List[Dict[str, Any]]) -> JSONResponse:
    """
    422 for a batch where nothing passed validation.

    Returned as a raw JSONResponse (not HTTPException) because the app's
    global handler flattens dict details and would drop the per-file list,
    which is exactly what the client needs to fix its CSVs.
    """
    return JSONResponse(
        status_code=422,
        content={
            "error": "all_files_rejected",
            "detail": "Every uploaded file failed validation.",
            "timestamp": time.time(),
            "files": [
                {
                    "file_id": entry["file_id"],
                    "name": entry["name"],
                    "status": entry["status"],
                    "error": entry["error"],
                }
                for entry in entries
            ],
        },
    )


def _parse_mapping(raw: Optional[str]) -> Optional[Dict[str, str]]:
    if raw is None or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_mapping",
                "detail": "Column mapping must be a JSON object.",
            },
        )
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_mapping",
                "detail": "Column mapping must be a JSON object.",
            },
        )
    allowed = ", ".join(CANONICAL_COLUMNS)
    out: Dict[str, str] = {}
    for key, value in data.items():
        if key not in CANONICAL_COLUMNS:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_mapping",
                    "detail": f"Unknown mapping key '{key}'. Allowed: {allowed}.",
                },
            )
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_mapping",
                    "detail": f"Mapping for '{key}' must be a column name.",
                },
            )
        out[key] = value.strip()
    return out or None


@router.post(
    "/api/v1/predict/batch",
    response_model=BatchJobStatus,
    status_code=202,
    summary="Create a batch prediction job",
    description=(
        "Upload one or more CSV files. Files are validated individually "
        "(extension, size, encoding, headers, columns, exact row count) and "
        "the response reports per-file validation results. Row-level "
        "validation and model inference run in the background."
    ),
)
async def create_batch_job(
    request: Request,
    files: Optional[List[UploadFile]] = File(default=None),
    mapping: Optional[str] = Form(default=None),
) -> Dict[str, Any]:
    be = _be()

    # Refuse oversized bodies before Starlette buffers them to disk.
    content_length = request.headers.get("content-length") or ""
    if content_length.isdigit():
        limit = LIMITS["max_batch_bytes"] + _CONTENT_LENGTH_SLACK
        if int(content_length) > limit:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "batch_too_large",
                    "detail": "Upload exceeds the "
                              f"{LIMITS['max_batch_bytes'] // (1024 * 1024)} MB "
                              "total batch limit.",
                    "timestamp": time.time(),
                },
            )

    if not be.is_model_ready():
        raise HTTPException(
            status_code=550,
            detail={
                "error": "model_unavailable",
                "detail": "ML model inference cannot run, so no batch job was "
                          "created. This is not a fallback heuristic.",
                "timestamp": time.time(),
            },
        )

    mapping_dict = _parse_mapping(mapping)
    uploads = files or []

    if not uploads:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "no_files",
                "detail": "No CSV files were uploaded.",
            },
        )
    if len(uploads) > LIMITS["max_files"]:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "too_many_files",
                "detail": f"A batch accepts at most {LIMITS['max_files']} files "
                          f"(received {len(uploads)}).",
            },
        )

    job = _new_job()
    try:
        entries: List[Dict[str, Any]] = []
        for index, upload in enumerate(uploads, start=1):
            entries.append(await _store_upload(job, upload, index))
        job["files"] = entries

        pending = [e for e in entries if e["status"] == "pending"]
        if not pending:
            _remove_job_dir(job)
            with _JOBS_LOCK:
                _JOBS.pop(job["job_id"], None)
            return _all_rejected_response(entries)

        loop = asyncio.get_running_loop()
        await asyncio.gather(
            *[
                loop.run_in_executor(
                    _EXECUTOR, _validate_stored_file, entry, mapping_dict
                )
                for entry in pending
            ]
        )

        # Sequential pass: exact cumulative row limit + duplicate detection.
        total_rows = 0
        seen_hashes: Dict[str, str] = {}
        for entry in entries:
            if entry["status"] != "validated":
                continue
            rows = entry.get("rows_total") or 0
            if total_rows + rows > LIMITS["max_total_rows"]:
                entry["status"] = "rejected"
                entry["error"] = {
                    "code": "batch_row_limit_exceeded",
                    "detail": "Adding this file would exceed the "
                              f"{LIMITS['max_total_rows']:,} row batch limit.",
                }
                entry["resolution"] = None
                continue
            total_rows += rows
            digest = entry.get("sha256")
            if digest:
                if digest in seen_hashes:
                    entry["warnings"].append(
                        f"Duplicate file content (identical to "
                        f"'{seen_hashes[digest]}'); both files were kept."
                    )
                else:
                    seen_hashes[digest] = entry["name"]

        validated = [e for e in entries if e["status"] == "validated"]
        if not validated:
            _remove_job_dir(job)
            with _JOBS_LOCK:
                _JOBS.pop(job["job_id"], None)
            return _all_rejected_response(entries)

        job["progress"]["files_total"] = len(validated)
        job["progress"]["rows_total"] = total_rows
        job["warnings"].append(
            "Predictions come from the loaded ML model only; no heuristic or "
            "dummy scores are produced. Probabilities are model outputs, "
            "not guarantees."
        )

        worker = threading.Thread(
            target=_process_job, args=(job["job_id"],), daemon=True
        )
        worker.start()
        return _status_payload(job)
    except HTTPException:
        raise
    except Exception:
        _remove_job_dir(job)
        with _JOBS_LOCK:
            _JOBS.pop(job["job_id"], None)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "batch_create_failed",
                "detail": "The batch job could not be created.",
            },
        )


@router.get(
    "/api/v1/predict/batch/template",
    summary="CSV template",
    description=(
        "Download a ready-to-fill CSV template: `canonical` "
        "(flight_number, origin, destination, date) or `bts` "
        "(Year, Month, DayOfMonth, Reporting_Airline, Origin, Dest)."
    ),
)
async def download_template(style: str = Query("canonical")) -> Response:
    if style == "canonical":
        columns, rows = TEMPLATE_COLUMNS, TEMPLATE_ROWS
        name = "aerodelay_batch_template.csv"
    elif style == "bts":
        columns, rows = BTS_TEMPLATE_COLUMNS, BTS_TEMPLATE_ROWS
        name = "aerodelay_batch_template_bts.csv"
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_template_style",
                "detail": "style must be 'canonical' or 'bts'.",
            },
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get(
    "/api/v1/predict/batch/{job_id}",
    response_model=BatchJobStatus,
    summary="Batch job status",
    description="Progress, per-file state and (when finished) the summary.",
)
async def get_batch_status(job_id: str) -> Dict[str, Any]:
    return _status_payload(_require_job(job_id))


@router.get(
    "/api/v1/predict/batch/{job_id}/results",
    response_model=BatchResults,
    summary="Batch job results",
    description=(
        "Summary, per-file statistics, one page of prediction rows and the "
        "row-level failure ledger (capped at 500 entries; download the "
        "failures CSV for the full list)."
    ),
)
async def get_batch_results(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(LIMITS["default_page_size"], ge=1),
    file_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    job = _require_job(job_id)
    page_size = min(page_size, LIMITS["max_page_size"])

    sink = job.get("result_sink")
    if file_id is not None:
        entry = _find_file(job, file_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown_file",
                    "detail": "No such file in this batch job.",
                },
            )
        sink = entry.get("result_sink")

    start = (page - 1) * page_size
    with job["io_lock"]:
        raw_rows = _read_page(sink, start, page_size)
        failure_sink = job.get("failure_sink")
        raw_failures = _read_page(failure_sink, 0, LIMITS["max_failures_returned"])
        failures_total = _sink_count(failure_sink)
        summary = job.get("summary_cache") or _build_summary(job)
        files = [_file_payload(f) for f in job["files"]]
        status = job["status"]

    rows = [r for r in (_row_payload(raw) for raw in raw_rows) if r]
    failures = [
        r for r in (_failure_payload(raw) for raw in raw_failures) if r
    ]
    rows_total = _sink_count(sink)

    return {
        "job_id": job_id,
        "status": status,
        "summary": summary,
        "files": files,
        "rows": rows,
        "rows_total": rows_total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-rows_total // page_size)),
        "failures": failures,
        "failures_total": failures_total,
        "failures_truncated": failures_total > len(failures),
    }


@router.get(
    "/api/v1/predict/batch/{job_id}/download",
    summary="Download batch CSVs",
    description=(
        "`file` = `combined` (all predictions), `summary`, `failures` "
        "(row-level validation errors) or a file id such as `f001` for a "
        "single input file's predictions."
    ),
)
async def download_batch_file(
    job_id: str, file: str = Query("combined")
) -> FileResponse:
    job = _require_job(job_id)

    if job["status"] not in _TERMINAL_STATUSES or job["status"] == "cancelled":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "job_not_finished",
                "detail": "The batch job is still running; downloads are "
                          "available once it finishes.",
            },
        )

    kind = (file or "").strip()
    job_dir = Path(job["dir"])
    if kind in ("combined", "summary", "failures"):
        filename = {
            "combined": "results.csv",
            "summary": "summary.csv",
            "failures": "failures.csv",
        }[kind]
        path = job_dir / filename
        download_name = f"aerodelay_batch_{job_id[:8]}_{kind}.csv"
    elif re.fullmatch(r"f\d{3}", kind):
        entry = _find_file(job, kind)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown_file",
                    "detail": "No such file in this batch job.",
                },
            )
        path = job_dir / f"results_{kind}.csv"
        download_name = _sanitize_filename(entry["name"])
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_download",
                "detail": "file must be combined, summary, failures or a "
                          "file id such as f001.",
            },
        )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no_results",
                "detail": "No downloadable results exist for that selection.",
            },
        )

    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename=download_name,
    )


@router.delete(
    "/api/v1/predict/batch/{job_id}",
    summary="Cancel and delete a batch job",
    description="Stops processing and removes all temporary files for the job.",
)
async def delete_batch_job(job_id: str) -> Dict[str, Any]:
    job = _require_job(job_id)
    with job["io_lock"]:
        job["status"] = "cancelled"
    with _JOBS_LOCK:
        _JOBS.pop(job_id, None)

    def _cleanup() -> None:
        time.sleep(0.3)  # let a running worker notice the cancel flag
        _remove_job_dir(job)

    threading.Thread(target=_cleanup, daemon=True).start()
    return {"job_id": job_id, "status": "cancelled"}


atexit.register(_cleanup_on_exit)
_prepare_root()
