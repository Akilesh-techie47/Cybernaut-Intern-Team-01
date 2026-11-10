"""
Batch CSV prediction - backend verification suite.

Runs against the real FastAPI app in-process (TestClient) with the REAL ML
artifacts loaded (logistic_regression_new.joblib + preprocessor_compatible.joblib).
No external provider is contacted; AviationStack is never called here.

Run:  python tests/test_batch_api.py
Exit code 0 = all checks passed.
"""

import io
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from fastapi.testclient import TestClient  # noqa: E402
import app_backend  # noqa: E402
import batch_prediction  # noqa: E402

RESULTS = []

CANONICAL_HEADER = "flight_number,origin,destination,date\n"
SAMPLE_ROWS = (
    "AA1234,JFK,LAX,2022-12-15\n"
    "DL456,SFO,SEA,2022-12-16\n"
    "UA789,ORD,JFK,2022-12-17\n"
)


def check(section, name, ok, detail=""):
    RESULTS.append((section, name, bool(ok), detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {section} :: {name}" + (f" -- {detail}" if detail else ""))


def rate_limit_reset(app):
    try:
        app.state.rate_limit.clear()
    except Exception:
        pass


def csv_bytes(text: str, encoding: str = "utf-8"):
    return io.BytesIO(text.encode(encoding))


def upload(client, files, mapping=None):
    payload = []
    for item in files:
        if len(item) == 3:
            name, data, content_type = item
        else:
            name, data = item
            content_type = "text/csv"
        payload.append(("files", (name, data, content_type)))
    data = {}
    if mapping is not None:
        data["mapping"] = json.dumps(mapping)
    return client.post("/api/v1/predict/batch", files=payload, data=data)


def wait_terminal(client, job_id, timeout=90):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/predict/batch/{job_id}")
        if response.status_code != 200:
            return None
        last = response.json()
        if last["status"] in (
            "completed",
            "completed_with_errors",
            "failed",
        ):
            return last
        time.sleep(0.05)
    return last


def run_job(client, files, mapping=None, timeout=90):
    """Upload, wait for completion, return (status_payload, results_payload)."""
    response = upload(client, files, mapping)
    if response.status_code != 202:
        return None, response
    job_id = response.json()["job_id"]
    status = wait_terminal(client, job_id, timeout)
    if status is None:
        return None, response
    results = client.get(
        f"/api/v1/predict/batch/{job_id}/results?page_size=500"
    )
    return status, results


def results_for_file(results_json, file_id):
    return [r for r in results_json["rows"] if r["file_id"] == file_id]


# ─── pytest bridge ───────────────────────────────────────────────────────
# The suite is authored as a standalone script (main() drives every group).
# This fixture lets the SAME test functions run under `python -m pytest`
# without duplicating them: each test gets a fresh TestClient and fails if
# any check() it recorded came back false.

try:
    import pytest  # noqa: E402

    @pytest.fixture()
    def client():
        with TestClient(app_backend.app) as c:
            rate_limit_reset(c.app)
            start = len(RESULTS)
            yield c
            failed = [
                (s, n, d) for s, n, ok, d in RESULTS[start:] if not ok
            ]
            assert not failed, f"failed checks: {failed}"

except ImportError:  # standalone environments without pytest
    pass


# ─── Test groups ─────────────────────────────────────────────────────────

def test_templates(client):
    section = "template"
    rate_limit_reset(client.app)

    response = client.get("/api/v1/predict/batch/template")
    body = response.text.splitlines()
    ok = response.status_code == 200 and body[0] == (
        "flight_number,origin,destination,date"
    ) and "attachment" in response.headers.get("content-disposition", "")
    check(section, "canonical template", ok, body[0] if body else "")

    response = client.get("/api/v1/predict/batch/template?style=bts")
    body = response.text.splitlines()
    ok = response.status_code == 200 and body[0] == (
        "Year,Month,DayOfMonth,Reporting_Airline,Origin,Dest"
    )
    check(section, "bts template", ok, body[0] if body else "")

    response = client.get("/api/v1/predict/batch/template?style=xml")
    check(
        section,
        "invalid template style rejected",
        response.status_code == 400
        and response.json()["error"] == "invalid_template_style",
        str(response.status_code),
    )


def test_upload_validation(client):
    section = "upload-validation"
    rate_limit_reset(client.app)

    files = [
        ("notes.txt", csv_bytes("hello"), "text/plain"),
        ("empty.csv", csv_bytes(""), "text/csv"),
        ("header_only.csv", csv_bytes(CANONICAL_HEADER), "text/csv"),
        ("binary.csv", io.BytesIO(b"\x00\x01\x02\x03PK\x03\x04"), "text/csv"),
        ("utf16.csv", io.BytesIO(CANONICAL_HEADER.encode("utf-16")), "text/csv"),
        (
            "dup_headers.csv",
            csv_bytes("flight_number,flight_number,origin,destination,date\n"),
            "text/csv",
        ),
        (
            "missing_col.csv",
            csv_bytes("flight_number,origin,date\nAA1234,JFK,2022-12-15\n"),
            "text/csv",
        ),
        (
            "bad_csv.csv",
            csv_bytes('flight_number,origin,destination,date\n"unbalanced,JFK,LAX,2022-12-15\n'),
            "text/csv",
        ),
    ]
    response = upload(client, files)
    check(
        section,
        "batch with only invalid files returns 422",
        response.status_code == 422
        and response.json()["error"] == "all_files_rejected",
        str(response.status_code),
    )

    # Mixed batch: good files are accepted, bad ones reported individually.
    response = upload(
        client,
        [
            ("good.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv"),
            ("notes.txt", csv_bytes("x"), "text/plain"),
            ("empty.csv", csv_bytes(""), "text/csv"),
            ("binary.csv", io.BytesIO(b"\x00\x01"), "text/csv"),
            (
                "missing_col.csv",
                csv_bytes("flight_number,origin,date\n"),
                "text/csv",
            ),
        ],
    )
    ok = response.status_code == 202
    check(section, "mixed batch accepted", ok, str(response.status_code))
    if not ok:
        return
    payload = response.json()
    by_name = {f["name"]: f for f in payload["files"]}
    check(
        section,
        "unsupported extension rejected",
        by_name["notes.txt"]["status"] == "rejected"
        and by_name["notes.txt"]["error"]["code"] == "unsupported_extension",
        str(by_name.get("notes.txt")),
    )
    check(
        section,
        "empty file rejected",
        by_name["empty.csv"]["status"] == "rejected"
        and by_name["empty.csv"]["error"]["code"] == "empty_file",
        str(by_name.get("empty.csv")),
    )
    check(
        section,
        "binary file rejected",
        by_name["binary.csv"]["status"] == "rejected"
        and by_name["binary.csv"]["error"]["code"] == "binary_content",
        str(by_name.get("binary.csv")),
    )
    missing_file = by_name.get("missing_col.csv") or {}
    missing_error = missing_file.get("error") or {}
    check(
        section,
        "missing column rejected with named column",
        missing_file.get("status") == "rejected"
        and missing_error.get("code") == "missing_required_columns"
        and "destination" in missing_error.get("detail", ""),
        str(missing_error),
    )
    good_file = by_name.get("good.csv") or {}
    check(
        section,
        "valid file validated with exact row count",
        good_file.get("status") in (
            "validated",
            "processing",
            "completed",
            "completed_with_errors",
        )
        and good_file.get("rows_total") == 3,
        str(good_file),
    )
    check(
        section,
        "accepted_files / rejected_files counts",
        payload["accepted_files"] == 1 and payload["rejected_files"] == 4,
        f"accepted={payload['accepted_files']} rejected={payload['rejected_files']}",
    )

    job_id = payload["job_id"]
    status = wait_terminal(client, job_id)
    check(
        section,
        "job completes with per-file outcomes",
        status is not None and status["status"] in (
            "completed",
            "completed_with_errors",
        ),
        str(status and status["status"]),
    )
    client.delete(f"/api/v1/predict/batch/{job_id}")


def test_encodings(client):
    section = "encodings"
    rate_limit_reset(client.app)

    # UTF-8 with BOM
    bom_text = "\ufeff" + CANONICAL_HEADER + SAMPLE_ROWS
    # CP1252: contains 0xE9 which is invalid UTF-8
    cp_text = "flight_number,origin,destination,date,Notes\nAA1234,JFK,LAX,2022-12-15,Café\n"
    # UTF-16 must be rejected
    response = upload(
        client,
        [
            ("bom.csv", csv_bytes(bom_text), "text/csv"),
            ("cp1252.csv", csv_bytes(cp_text, "cp1252"), "text/csv"),
            ("utf16.csv", io.BytesIO(CANONICAL_HEADER.encode("utf-16")), "text/csv"),
        ],
    )
    ok = response.status_code == 202
    check(section, "encoding batch accepted", ok, str(response.status_code))
    if not ok:
        return
    payload = response.json()
    by_name = {f["name"]: f for f in payload["files"]}
    bom_file = by_name.get("bom.csv") or {}
    check(
        section,
        "utf-8 BOM accepted",
        bom_file.get("status") in (
            "validated",
            "processing",
            "completed",
            "completed_with_errors",
        )
        and bom_file.get("rows_total") == 3
        and bom_file.get("encoding") == "utf-8-sig",
        str(bom_file),
    )
    check(
        section,
        "cp1252 accepted and reported",
        by_name["cp1252.csv"]["status"] == "validated"
        and by_name["cp1252.csv"]["encoding"] == "cp1252",
        str(by_name.get("cp1252.csv")),
    )
    utf16_file = by_name.get("utf16.csv") or {}
    utf16_error = utf16_file.get("error") or {}
    check(
        section,
        "utf-16 rejected with a useful message",
        utf16_file.get("status") == "rejected"
        and utf16_error.get("code") == "encoding_error"
        and "UTF-16" in utf16_error.get("detail", ""),
        str(utf16_error),
    )
    wait_terminal(client, payload["job_id"])
    client.delete(f"/api/v1/predict/batch/{payload['job_id']}")


def test_limits(client):
    section = "limits"
    rate_limit_reset(client.app)

    original = dict(batch_prediction.LIMITS)

    # Too many files
    try:
        batch_prediction.LIMITS["max_files"] = 3
        files = [
            (f"f{i}.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")
            for i in range(4)
        ]
        response = upload(client, files)
        check(
            section,
            "too many files -> 413",
            response.status_code == 413
            and response.json()["error"] == "too_many_files",
            str(response.status_code),
        )
    finally:
        batch_prediction.LIMITS.update(original)

    # Per-file size
    try:
        batch_prediction.LIMITS["max_file_bytes"] = 64
        response = upload(
            client,
            [("big.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")],
        )
        rejected = response.json()["files"][0]
        check(
            section,
            "oversized file rejected",
            rejected["status"] == "rejected"
            and rejected["error"]["code"] == "file_too_large",
            str(rejected.get("error")),
        )
        if response.status_code == 202:
            client.delete(f"/api/v1/predict/batch/{response.json()['job_id']}")
    finally:
        batch_prediction.LIMITS.update(original)

    # Total batch size
    try:
        batch_prediction.LIMITS["max_batch_bytes"] = 250
        one = csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS)
        response = upload(
            client,
            [
                ("a.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv"),
                ("b.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv"),
                ("c.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv"),
            ],
        )
        if response.status_code == 202:
            payload = response.json()
            codes = [f["error"]["code"] for f in payload["files"] if f["error"]]
            check(
                section,
                "total batch size enforced",
                "batch_too_large" in codes,
                str(codes),
            )
            client.delete(f"/api/v1/predict/batch/{payload['job_id']}")
        else:
            check(
                section,
                "total batch size enforced",
                response.status_code in (413, 422),
                f"status={response.status_code} {response.text[:120]}",
            )
    finally:
        batch_prediction.LIMITS.update(original)

    # Rows per file
    try:
        batch_prediction.LIMITS["max_rows_per_file"] = 2
        response = upload(
            client,
            [("rows.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")],
        )
        rejected = response.json()["files"][0]
        check(
            section,
            "row limit per file enforced (never truncated)",
            rejected["status"] == "rejected"
            and rejected["error"]["code"] == "too_many_rows",
            str(rejected.get("error")),
        )
        if response.status_code == 202:
            client.delete(f"/api/v1/predict/batch/{response.json()['job_id']}")
    finally:
        batch_prediction.LIMITS.update(original)

    # Cumulative rows
    try:
        batch_prediction.LIMITS["max_total_rows"] = 4
        response = upload(
            client,
            [
                ("a.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv"),
                ("b.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv"),
            ],
        )
        if response.status_code == 202:
            payload = response.json()
            codes = [
                (f["name"], f["error"]["code"])
                for f in payload["files"]
                if f["error"]
            ]
            check(
                section,
                "cumulative row limit enforced",
                any(c == "batch_row_limit_exceeded" for _, c in codes),
                str(codes),
            )
            client.delete(f"/api/v1/predict/batch/{payload['job_id']}")
        else:
            check(
                section,
                "cumulative row limit enforced",
                response.status_code == 422,
                str(response.status_code),
            )
    finally:
        batch_prediction.LIMITS.update(original)


def test_row_validation_and_partial_failure(client):
    section = "row-validation"
    rate_limit_reset(client.app)

    text = (
        CANONICAL_HEADER
        + "AA1234,JFK,LAX,2022-12-15\n"      # valid
        + "XX111,JFK,LAX,2022-12-15\n"        # unknown carrier
        + "AA1234,SIN,LAX,2022-12-15\n"       # unknown origin (SIN not in BTS vocab)
        + "AA1234,JFK,BKK,2022-12-15\n"       # unknown destination (BKK not in BTS vocab)
        + "AA1234,JFK,LAX,not-a-date\n"       # invalid date
        + ",JFK,LAX,2022-12-15\n"             # missing flight number/carrier
        + "DL456,SFO,SEA,2022-12-16\n"        # valid
        + "AA1234,JFK,LAX,2022-12-15\n"       # valid, exact duplicate of row 1
    )
    status, results = run_job(
        client, [("partial.csv", csv_bytes(text), "text/csv")]
    )
    check(section, "job runs", status is not None, str(status and status["status"]))
    if status is None:
        return
    check(
        section,
        "status reflects row failures",
        status["status"] == "completed_with_errors",
        str(status["status"]),
    )
    payload = results.json()
    rows = results_for_file(payload, "f001")
    check(
        section,
        "valid rows predicted, invalid rows excluded",
        len(rows) == 3 and payload["summary"]["rows_rejected"] == 5,
        f"predicted={len(rows)} rejected={payload['summary']['rows_rejected']}",
    )
    codes = sorted({f["error_code"] for f in payload["failures"]})
    check(
        section,
        "failure ledger names every error type",
        codes
        == sorted(
            [
                "invalid_date",
                "missing_value",
                "unknown_airport",
                "unknown_carrier",
            ]
        ),
        str(codes),
    )
    check(
        section,
        "row numbers preserved for valid rows",
        [r["row_number"] for r in rows] == [1, 7, 8],
        str([r["row_number"] for r in rows]),
    )
    check(
        section,
        "duplicate input rows still predicted (no silent drop)",
        len(rows) == 3,
        str(len(rows)),
    )
    warnings = " ".join(
        w for f in status["files"] for w in (f.get("warnings") or [])
    ) + " " + " ".join(status["warnings"])
    check(
        section,
        "duplicate rows reported as a warning",
        "duplicate row" in warnings,
        warnings[:200],
    )
    check(
        section,
        "failure rows link to the source file",
        all(f["file_id"] == "f001" for f in payload["failures"]),
        "",
    )
    client.delete(f"/api/v1/predict/batch/{status['job_id']}")


def test_schema_aliases_and_labels(client):
    section = "schema"
    rate_limit_reset(client.app)

    # Alias-style headers
    aliased = (
        "FlightNumber,Origin,Dest,FlightDate\n"
        "AA1234,JFK,LAX,2022-12-15\n"
    )
    status, results = run_job(client, [("aliased.csv", csv_bytes(aliased), "text/csv")])
    check(
        section,
        "alias headers accepted",
        status is not None and status["status"] == "completed",
        str(status and status["status"]),
    )
    if status:
        rows = results.json()["rows"]
        check(
            section,
            "alias values mapped to canonical fields",
            rows
            and rows[0]["flight_number"] == "AA1234"
            and rows[0]["origin"] == "JFK"
            and rows[0]["destination"] == "LAX"
            and rows[0]["date"] == "2022-12-15",
            str(rows[:1]),
        )
        client.delete(f"/api/v1/predict/batch/{status['job_id']}")

    # BTS-style file with a label column and unsupported airport
    bts_path = Path(__file__).resolve().parent / "sample_bts.csv"
    bts_bytes = io.BytesIO(bts_path.read_bytes())
    status, results = run_job(client, [("sample_bts.csv", bts_bytes, "text/csv")])
    check(
        section,
        "bts-style file accepted",
        status is not None and status["status"] == "completed_with_errors",
        str(status and status["status"]),
    )
    if status:
        payload = results.json()
        warnings = " ".join(
            w for f in status["files"] for w in (f.get("warnings") or [])
        )
        check(
            section,
            "label column excluded from inputs",
            "Depdel15" in warnings and "Excluded label" in warnings,
            warnings[:220],
        )
        check(
            section,
            "unused columns reported, not silently dropped",
            "Ignored column" in warnings and "Distance" in warnings,
            warnings[:300],
        )
        check(
            section,
            "date built from Year/Month/DayOfMonth",
            "Built date from" in warnings,
            warnings[:220],
        )
        check(
            section,
            "carrier taken from Reporting_Airline (no flight number)",
            all(r["carrier"] in app_backend.SUPPORTED_CARRIERS for r in payload["rows"]),
            str([r["carrier"] for r in payload["rows"]]),
        )
        check(
            section,
            "unsupported airport rows rejected individually",
            payload["summary"]["rows_predicted"] == 2
            and payload["summary"]["rows_rejected"] == 2,
            str(payload["summary"]),
        )
        client.delete(f"/api/v1/predict/batch/{status['job_id']}")

    # Global column mapping
    remapped = "FLT,From,To,When\nAA1234,JFK,LAX,2022-12-15\n"
    status, results = run_job(
        client,
        [("remap.csv", csv_bytes(remapped), "text/csv")],
        mapping={
            "flight_number": "FLT",
            "origin": "From",
            "destination": "To",
            "date": "When",
        },
    )
    check(
        section,
        "global column mapping applied",
        status is not None and status["status"] == "completed",
        str(status and status["status"]),
    )
    if status:
        rows = results.json()["rows"]
        check(
            section,
            "mapped row predicted",
            len(rows) == 1 and rows[0]["origin"] == "JFK",
            str(rows[:1]),
        )
        client.delete(f"/api/v1/predict/batch/{status['job_id']}")

    # Invalid mapping key
    response = upload(
        client,
        [("x.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")],
        mapping={"nonsense": "col"},
    )
    check(
        section,
        "unknown mapping key -> 422",
        response.status_code == 422
        and response.json()["error"] == "invalid_mapping",
        str(response.status_code),
    )

    # Mapping pointing at a column that does not exist in this file
    response = upload(
        client,
        [("x.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")],
        mapping={"origin": "NotAColumn"},
    )
    if response.status_code == 202:
        payload = response.json()
        rejected = [f for f in payload["files"] if f["status"] == "rejected"]
        check(
            section,
            "mapping to a missing column rejects that file",
            len(rejected) == 1
            and rejected[0]["error"]["code"] == "missing_required_columns",
            str(rejected),
        )
        client.delete(f"/api/v1/predict/batch/{payload['job_id']}")
    else:
        check(
            section,
            "mapping to a missing column rejects that file",
            response.status_code == 422,
            str(response.status_code),
        )


def test_model_parity_and_thresholds(client):
    section = "model-parity"
    rate_limit_reset(client.app)

    cases = [
        ("AA1234", "JFK", "LAX", "2022-12-15"),
        ("DL456", "SFO", "SEA", "2022-12-16"),
        ("UA789", "ORD", "JFK", "2022-12-17"),
        ("B6100", "JFK", "ORD", "2022-12-18"),
        ("WN200", "SEA", "LAX", "2022-01-05"),
    ]
    text = CANONICAL_HEADER + "".join(
        f"{fn},{og},{dt},{day}\n" for fn, og, dt, day in cases
    )
    status, results = run_job(client, [("parity.csv", csv_bytes(text), "text/csv")])
    check(section, "parity batch runs", status is not None, str(status and status["status"]))
    if status is None:
        return
    rows = results.json()["rows"]
    check(
        section,
        "every input row predicted",
        len(rows) == len(cases),
        f"{len(rows)}/{len(cases)}",
    )

    mismatches = []
    for row, (fn, og, dt, day) in zip(rows, cases):
        info = app_backend.FlightInfo(
            flight_number=fn, origin=og, destination=dt, date=day
        )
        expected = app_backend.run_prediction(info)
        if expected is None:
            mismatches.append((fn, "single predict returned None"))
            continue
        if round(expected.risk_score, 4) != round(row["probability"], 4):
            mismatches.append(
                (fn, f"{row['probability']} != {expected.risk_score}")
            )
        if expected.risk_level.value != row["risk_level"]:
            mismatches.append((fn, f"level {row['risk_level']}"))
    check(
        section,
        "batch probability == single /api/v1/predict",
        not mismatches,
        str(mismatches[:3]),
    )

    # Risk band thresholds are applied exactly as documented.
    be = app_backend
    band_errors = []
    for row in rows:
        p = row["probability"]
        expected = (
            "High"
            if p >= be.RISK_HIGH_THRESHOLD
            else "Medium"
            if p >= be.RISK_MEDIUM_THRESHOLD
            else "Low"
        )
        if row["risk_level"] != expected:
            band_errors.append((p, row["risk_level"], expected))
        if row["predicted_class"] != int(p >= be.MODEL_CLASS_THRESHOLD):
            band_errors.append((p, "class mismatch"))
    check(
        section,
        "risk bands and class threshold applied",
        not band_errors,
        str(band_errors[:3]),
    )

    check(
        section,
        "model version reported on every row",
        all(r["model_version"] == status["model_version"] for r in rows),
        rows[0]["model_version"] if rows else "",
    )

    # Summary arithmetic
    summary = results.json()["summary"]
    check(
        section,
        "summary counts add up",
        summary["rows_predicted"]
        == summary["delayed"] + summary["on_time"]
        and sum(summary["risk_counts"].values()) == summary["rows_predicted"]
        and summary["rows_predicted"] + summary["rows_rejected"]
        + summary["rows_failed"]
        == summary["rows_total"],
        str(summary),
    )
    client.delete(f"/api/v1/predict/batch/{status['job_id']}")


def test_chunking_order_and_downloads(client):
    section = "chunking-downloads"
    rate_limit_reset(client.app)

    # 1,250 rows -> spans several 500-row chunks
    rows_text = "".join(
        f"AA{(i % 9000) + 1000:04d},JFK,LAX,2022-12-{(i % 27) + 1:02d}\n"
        for i in range(1, 1251)
    )
    status, results = run_job(
        client, [("big.csv", csv_bytes(CANONICAL_HEADER + rows_text), "text/csv")]
    )
    check(section, "large file runs", status is not None, str(status and status["status"]))
    if status is None:
        return
    job_id = status["job_id"]
    payload = results.json()
    check(
        section,
        "all rows across chunk boundaries predicted",
        payload["rows_total"] == 1250 and payload["summary"]["rows_predicted"] == 1250,
        str(payload["rows_total"]),
    )
    # Page through everything (500 is the max page size) to prove the order.
    numbers = [r["row_number"] for r in payload["rows"]]
    for page_no in (2, 3):
        page = client.get(
            f"/api/v1/predict/batch/{job_id}"
            f"/results?page={page_no}&page_size=500"
        ).json()
        numbers.extend(r["row_number"] for r in page["rows"])
    check(
        section,
        "row order and numbering preserved",
        numbers == list(range(1, 1251)),
        str(numbers[:5]) + "..." + str(numbers[-3:]),
    )

    # Pagination
    page2 = client.get(
        f"/api/v1/predict/batch/{job_id}/results?page=2&page_size=100"
    ).json()
    check(
        section,
        "pagination returns the requested slice",
        len(page2["rows"]) == 100
        and page2["rows"][0]["row_number"] == 101
        and page2["pages"] == 13,
        f"n={len(page2['rows'])} first={page2['rows'] and page2['rows'][0]['row_number']} pages={page2['pages']}",
    )

    # Downloads
    combined = client.get(f"/api/v1/predict/batch/{job_id}/download?file=combined")
    lines = combined.text.splitlines()
    check(
        section,
        "combined CSV download",
        combined.status_code == 200
        and "attachment" in combined.headers.get("content-disposition", "")
        and len(lines) == 1251,
        f"{combined.status_code} lines={len(lines)}",
    )

    summary_csv = client.get(f"/api/v1/predict/batch/{job_id}/download?file=summary")
    check(
        section,
        "summary CSV download with TOTAL row",
        summary_csv.status_code == 200
        and summary_csv.text.splitlines()[-1].startswith(f"{job_id},"),
        summary_csv.text.splitlines()[-1][:80] if summary_csv.text else "",
    )

    failures_csv = client.get(f"/api/v1/predict/batch/{job_id}/download?file=failures")
    check(
        section,
        "failures CSV download",
        failures_csv.status_code == 200
        and failures_csv.text.splitlines()[0].startswith("file_id,file_name,row_number"),
        failures_csv.text.splitlines()[0][:60] if failures_csv.text else "",
    )

    per_file = client.get(f"/api/v1/predict/batch/{job_id}/download?file=f001")
    check(
        section,
        "per-file CSV download",
        per_file.status_code == 200
        and len(per_file.text.splitlines()) == 1251
        and 'filename="big.csv"' in per_file.headers.get("content-disposition", ""),
        per_file.headers.get("content-disposition", ""),
    )

    bad = client.get(f"/api/v1/predict/batch/{job_id}/download?file=../../etc/passwd")
    check(
        section,
        "path traversal in download selector rejected",
        bad.status_code == 400 and bad.json()["error"] == "invalid_download",
        str(bad.status_code),
    )
    unknown = client.get(f"/api/v1/predict/batch/{job_id}/download?file=f999")
    check(
        section,
        "unknown file id rejected",
        unknown.status_code == 404,
        str(unknown.status_code),
    )

    # Downloads are refused while the job is still running.
    real_worker = batch_prediction._process_job
    gate = threading.Event()

    def gated_worker(job_id_arg):
        gate.wait(10)
        real_worker(job_id_arg)

    batch_prediction._process_job = gated_worker
    slow_id = None
    try:
        rate_limit_reset(client.app)
        response = upload(
            client,
            [("slow.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")],
        )
        slow_id = response.json().get("job_id") if response.status_code == 202 else None
        early = client.get(f"/api/v1/predict/batch/{slow_id}/download?file=combined")
        check(
            section,
            "download refused while job is running",
            early.status_code == 409 and early.json()["error"] == "job_not_finished",
            str(early.status_code),
        )
    finally:
        gate.set()
        batch_prediction._process_job = real_worker
        if slow_id:
            wait_terminal(client, slow_id, timeout=30)
            client.delete(f"/api/v1/predict/batch/{slow_id}")

    client.delete(f"/api/v1/predict/batch/{job_id}")


def test_many_files_and_duplicates(client):
    section = "many-files"
    rate_limit_reset(client.app)

    # 105 files (requirement: 100+ per batch), two of them identical.
    files = []
    for i in range(105):
        text = CANONICAL_HEADER + (
            SAMPLE_ROWS if i % 2 == 0 else "UA789,ORD,JFK,2022-12-17\n"
        )
        files.append((f"batch_{i:03d}.csv", csv_bytes(text), "text/csv"))
    files[7] = files[6]  # exact duplicate content

    started = time.time()
    response = upload(client, files)
    elapsed = round(time.time() - started, 2)
    ok = response.status_code == 202
    check(section, "105-file batch accepted", ok, f"{response.status_code} in {elapsed}s")
    if not ok:
        return
    payload = response.json()
    job_id = payload["job_id"]
    check(
        section,
        "every file listed with an id",
        len(payload["files"]) == 105
        and payload["accepted_files"] == 105,
        f"files={len(payload['files'])} accepted={payload['accepted_files']}",
    )
    status = wait_terminal(client, job_id, timeout=120)
    check(
        section,
        "batch completes",
        status is not None and status["status"] in ("completed", "completed_with_errors"),
        str(status and status["status"]),
    )
    if status:
        summary = status["summary"]
        # 53 even-index files carry SAMPLE_ROWS (3 rows); 51 odd-index files
        # carry 1 row; index 7 was replaced with index 6's content (3 rows).
        expected_rows = 53 * 3 + 51 * 1 + 3
        check(
            section,
            "total file and record counts correct",
            summary["files_uploaded"] == 105
            and summary["rows_total"] == expected_rows
            and summary["rows_predicted"] == expected_rows,
            f"files={summary['files_uploaded']} rows={summary['rows_total']} "
            f"expected={expected_rows}",
        )
        dup_warned = any(
            "Duplicate file content" in warning
            for entry in status["files"]
            for warning in (entry.get("warnings") or [])
        )
        check(
            section,
            "duplicate file detected and kept",
            dup_warned,
            str([e["warnings"] for e in status["files"] if e["warnings"]][:2])[:160],
        )
        results = client.get(
            f"/api/v1/predict/batch/{job_id}/results?page_size=500&page=3"
        ).json()
        ids = [r["file_id"] for r in results["rows"]]
        check(
            section,
            "results are ordered by upload order",
            ids == sorted(ids, key=lambda x: int(x[1:])),
            str(ids[:6]),
        )
    client.delete(f"/api/v1/predict/batch/{job_id}")


def test_cleanup_security_and_failures(client):
    section = "cleanup-security"
    rate_limit_reset(client.app)

    # Traversal-style filename is sanitised before touching disk.
    response = upload(
        client,
        [
            (
                "..\\..\\evil.csv",
                csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS),
                "text/csv",
            )
        ],
    )
    ok = response.status_code == 202
    check(section, "traversal filename accepted as a plain name", ok, str(response.status_code))
    if ok:
        payload = response.json()
        name = payload["files"][0]["name"]
        check(
            section,
            "path components stripped from stored filename",
            "\\" not in name and "/" not in name and ".." not in name,
            name,
        )
        leaked = json.dumps(payload)
        check(
            section,
            "no server path or credential in the response",
            str(Path(tempfile.gettempdir())) not in leaked
            and "AVIATIONSTACK" not in leaked.upper()
            and "access_key" not in leaked.lower(),
            "",
        )
        status = wait_terminal(client, payload["job_id"])
        job_dir = Path(batch_prediction._JOBS_ROOT) / f"job-{payload['job_id']}"
        check(section, "job temp dir created", job_dir.exists(), str(job_dir))

        deleted = client.delete(f"/api/v1/predict/batch/{payload['job_id']}")
        check(
            section,
            "delete returns cancelled",
            deleted.status_code == 200 and deleted.json()["status"] == "cancelled",
            str(deleted.status_code),
        )
        time.sleep(1.0)
        check(
            section,
            "temp dir removed after delete",
            not job_dir.exists(),
            str(job_dir.exists()),
        )
        again = client.get(f"/api/v1/predict/batch/{payload['job_id']}")
        check(
            section,
            "job 404 after delete",
            again.status_code == 404 and again.json()["error"] == "job_not_found",
            str(again.status_code),
        )

    # Malformed job id never reaches the filesystem.
    for bad_id in ("../../etc/passwd", "nope", "A" * 32, ""):
        response = client.get(f"/api/v1/predict/batch/{bad_id}")
        # 404 = no match; 405 = empty id resolved to the POST collection route.
        if response.status_code not in (404, 405):
            check(
                section,
                f"malformed job id rejected ({bad_id!r})",
                False,
                str(response.status_code),
            )
    check(section, "malformed job ids rejected", True, "")

    # Expired jobs are swept.
    response = upload(
        client, [("t.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")]
    )
    if response.status_code == 202:
        job_id = response.json()["job_id"]
        wait_terminal(client, job_id)
        with batch_prediction._JOBS_LOCK:
            batch_prediction._JOBS[job_id]["expires_at"] = time.time() - 5
        swept = client.get(f"/api/v1/predict/batch/{job_id}")
        check(
            section,
            "expired job swept to 404",
            swept.status_code == 404,
            str(swept.status_code),
        )
        job_dir = Path(batch_prediction._JOBS_ROOT) / f"job-{job_id}"
        time.sleep(0.5)
        check(
            section,
            "expired job temp dir removed",
            not job_dir.exists(),
            str(job_dir.exists()),
        )

    # Rate limiting: batch GETs are exempt, batch POST is not.
    rate_limit_reset(client.app)
    before = len(client.app.state.rate_limit.get("testclient", []))
    for _ in range(70):
        client.get("/api/v1/predict/batch/" + "0" * 32)
    after = len(client.app.state.rate_limit.get("testclient", []))
    check(
        section,
        "batch polling is not rate limited",
        after == before,
        f"before={before} after={after}",
    )
    rate_limit_reset(client.app)
    response = client.post("/api/v1/predict/batch")
    check(
        section,
        "batch create is still rate limited",
        response.status_code == 422,  # counted, and no files -> our 422
        str(response.status_code),
    )
    rate_limit_reset(client.app)

    # Model unavailable -> explicit 550, never a heuristic job.
    saved_model, saved_names = app_backend._model, app_backend._feature_names
    app_backend._model = None
    app_backend._feature_names = None
    try:
        response = upload(
            client, [("x.csv", csv_bytes(CANONICAL_HEADER + SAMPLE_ROWS), "text/csv")]
        )
        check(
            section,
            "model unavailable -> 550 model_unavailable",
            response.status_code == 550
            and response.json()["error"] == "model_unavailable",
            f"{response.status_code} {response.text[:120]}",
        )
        check(
            section,
            "no job created when the model cannot run",
            batch_prediction._JOBS.keys().isdisjoint(
                [json.loads(response.text).get("job_id", "")]
            )
            if response.status_code == 202
            else True,
            "",
        )
    finally:
        app_backend._model = saved_model
        app_backend._feature_names = saved_names

    # run_batch_predict_proba must never fabricate a score.
    import numpy as np

    saved_model, saved_names = app_backend._model, app_backend._feature_names
    app_backend._model = None
    try:
        check(
            section,
            "batch proba returns None without a model",
            app_backend.run_batch_predict_proba(np.zeros((2, 654))) is None,
            "",
        )
    finally:
        app_backend._model = saved_model
        app_backend._feature_names = saved_names


def test_csv_injection_guard(client):
    section = "export-safety"
    rate_limit_reset(client.app)

    # 1. Exported cells that begin with a formula character are neutralised.
    guarded = [
        batch_prediction._csv_safe(v) == "'" + v
        for v in ("=1+1", "+SUM(A1)", "-2", "@handle")
    ]
    check(
        section,
        "formula-leading export cells are neutralised",
        all(guarded),
        str(guarded),
    )

    # 2. A formula-shaped flight number never reaches an export: it fails
    #    row validation instead of being written out verbatim.
    bad = "flight_number,origin,destination,date\n=cmd|calc,JFK,LAX,2022-12-15\n"
    status, results = run_job(client, [("inject.csv", csv_bytes(bad), "text/csv")])
    check(
        section,
        "formula-shaped input is rejected, not exported",
        status is not None and status["summary"]["rows_predicted"] == 0
        and status["summary"]["rows_rejected"] == 1,
        str(status and status["summary"]),
    )
    if status is None:
        return
    results_csv = client.get(
        f"/api/v1/predict/batch/{status['job_id']}/download?file=combined"
    ).text
    check(
        section,
        "no prediction row for the rejected input",
        len(results_csv.splitlines()) <= 1,
        results_csv.splitlines()[:2],
    )
    failures_csv = client.get(
        f"/api/v1/predict/batch/{status['job_id']}/download?file=failures"
    ).text
    check(
        section,
        "failure ledger records the rejected input",
        "=cmd|calc" in failures_csv,
        failures_csv.splitlines()[1:2],
    )
    client.delete(f"/api/v1/predict/batch/{status['job_id']}")


def main():
    with TestClient(app_backend.app) as client:
        rate_limit_reset(client.app)
        test_templates(client)
        test_upload_validation(client)
        test_encodings(client)
        test_limits(client)
        test_row_validation_and_partial_failure(client)
        test_schema_aliases_and_labels(client)
        test_model_parity_and_thresholds(client)
        test_chunking_order_and_downloads(client)
        test_many_files_and_duplicates(client)
        test_cleanup_security_and_failures(client)
        test_csv_injection_guard(client)

    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print("\n" + "=" * 70)
    print(f"BATCH API SUITE: {passed}/{total} checks passed")
    failures = [(s, n, d) for s, n, ok, d in RESULTS if not ok]
    for section, name, detail in failures:
        print(f"  FAIL {section} :: {name} -- {detail}")
    print("=" * 70)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
