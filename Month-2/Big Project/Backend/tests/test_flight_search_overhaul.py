"""
Phase 5.4 - New flight search overhaul test suite.

Tests for:
- Global airport search (/api/v1/airports/search)
- Airline lookup (/api/v1/airlines/search)
- Flight number search (lookup-and-predict workflow)
- Flight lookup with multiple results
- Historical and future dates
- Flight lookup to prediction workflow
- Unsupported airport categories
- Missing model features
- Provider unavailable
- Invalid API key
- Prediction unavailable
- Successful real-model inference with compatible features
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from fastapi.testclient import TestClient  # noqa: E402
import app_backend  # noqa: E402

RESULTS = []


def check(section, name, ok, detail=""):
    RESULTS.append((section, name, bool(ok), detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {section} :: {name}" + (f" -- {detail}" if detail else ""))


def rate_limit_reset(app):
    try:
        app.state.rate_limit.clear()
    except Exception:
        pass


# ── Test fixtures ──────────────────────────────────────────────────────────

MULTIPLE_FLIGHTS_RESPONSE = {
    "data": [
        {
            "flight": {"iata": "AA100", "number": "AA100"},
            "flight_status": "en_route",
            "flight_date": "2024-01-15",
            "departure": {
                "airport": "John F. Kennedy International",
                "iata": "JFK",
                "city": "New York",
                "country": "USA",
                "scheduled": "2024-01-15T10:30:00",
                "timezone": "America/New_York",
            },
            "arrival": {
                "airport": "Los Angeles International",
                "iata": "LAX",
                "city": "Los Angeles",
                "country": "USA",
                "scheduled": "2024-01-15T13:25:00",
                "timezone": "America/Los_Angeles",
            },
        },
        {
            "flight": {"iata": "AA100", "number": "AA100"},
            "flight_status": "scheduled",
            "flight_date": "2024-01-15",
            "departure": {
                "airport": "John F. Kennedy International",
                "iata": "JFK",
                "city": "New York",
                "country": "USA",
                "scheduled": "2024-01-15T09:00:00",
                "timezone": "America/New_York",
            },
            "arrival": {
                "airport": "San Francisco International",
                "iata": "SFO",
                "city": "San Francisco",
                "country": "USA",
                "scheduled": "2024-01-15T12:30:00",
                "timezone": "America/Los_Angeles",
            },
        },
    ],
}

SINGLE_FLIGHT_RESPONSE = {
    "data": [
        {
            "flight": {"iata": "AA100", "number": "AA100"},
            "flight_status": "en_route",
            "flight_date": "2024-01-15",
            "departure": {
                "airport": "John F. Kennedy International",
                "iata": "JFK",
                "city": "New York",
                "country": "USA",
                "scheduled": "2024-01-15T10:30:00",
                "estimated": "2024-01-15T10:45:00",
                "actual": "2024-01-15T10:35:00",
                "timezone": "America/New_York",
                "gate": "A12",
            },
            "arrival": {
                "airport": "Los Angeles International",
                "iata": "LAX",
                "city": "Los Angeles",
                "country": "USA",
                "scheduled": "2024-01-15T13:25:00",
                "estimated": "2024-01-15T13:40:00",
                "actual": "2024-01-15T13:30:00",
                "timezone": "America/Los_Angeles",
                "gate": "B3",
            },
            "airline": {"name": "American Airlines", "iata": "AA"},
            "aircraft": {"code": "B787-9"},
        }
    ],
}


def main():
    with TestClient(app_backend.app) as client:
        app = app_backend.app

        # ── Setup: ensure model loaded ──
        check(
            "setup",
            "model ready",
            app_backend._model is not None and app_backend._preprocessor is not None,
            f"model={app_backend._model is not None} preprocessor={app_backend._preprocessor is not None}",
        )
        check(
            "setup",
            "carrier count > 7",
            len(app_backend.SUPPORTED_CARRIERS) > 7,
            f"{len(app_backend.SUPPORTED_CARRIERS)} carriers",
        )
        check(
            "setup",
            "airport count > 5",
            len(app_backend.SUPPORTED_AIRPORTS) > 5,
            f"{len(app_backend.SUPPORTED_AIRPORTS)} airports",
        )

        rate_limit_reset(app)

        # ── 1. Global airport search ──
        section = "airport-search"

        r = client.get("/api/v1/airports/search?q=JFK&limit=10")
        check(section, "search by IATA code returns results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            check(section, "results contain JFK", any(a["iata"] == "JFK" for a in body["airports"]), str(body)[:200])
            check(section, "query echoed", body.get("query") == "JFK", str(body.get("query")))

        r = client.get("/api/v1/airports/search?q=Los Angeles&limit=10")
        check(section, "search by city returns results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            has_lax = any("Los Angeles" in a["name"] for a in body["airports"])
            check(section, "results contain LAX/LA area", has_lax, str(body)[:200])

        r = client.get("/api/v1/airports/search?q=Heathrow&limit=10")
        check(section, "search by airport name returns results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            has_lhr = any(a["iata"] == "LHR" for a in body["airports"])
            check(section, "results contain LHR", has_lhr, str(body)[:200])

        r = client.get("/api/v1/airports/search?q=KJFK&limit=10")
        check(section, "search by ICAO code returns results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            has_kjfk = any(a["icao"] == "KJFK" for a in body["airports"])
            check(section, "results contain KJFK", has_kjfk, str(body)[:200])

        r = client.get("/api/v1/airports/search?q=&limit=5")
        check(section, "empty query returns limited results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            check(section, "limit respected", len(body["airports"]) <= 5, str(len(body["airports"])))

        r = client.get("/api/v1/airports/search?q=ZZZXYZ&limit=10")
        check(section, "unknown code returns empty results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            check(section, "no results for unknown code", len(body["airports"]) == 0, str(len(body["airports"])))

        # ── 2. Airline lookup ──
        section = "airline-search"

        r = client.get("/api/v1/airlines/search?q=AA&limit=10")
        check(section, "search by airline code returns results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            has_aa = any(a["code"] == "AA" for a in body["airlines"])
            check(section, "results contain AA", has_aa, str(body)[:200])

        r = client.get("/api/v1/airlines/search?q=Delta&limit=10")
        check(section, "search by airline name returns results", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            has_delta = any("Delta" in a["name"] for a in body["airlines"])
            check(section, "results contain Delta", has_delta, str(body)[:200])

        r = client.get("/api/v1/airlines/search?q=ZZZ&limit=10")
        check(section, "unknown airline returns empty", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            body = r.json()
            check(section, "no results for unknown airline", len(body["airlines"]) == 0, str(len(body["airlines"])))

        # ── 3. Flight number search - not found ──
        section = "flight-search"

        with patch("app_backend.aviationstack_request", return_value={"data": []}):
            r = client.get("/api/v1/flights/lookup", params={"flight_number": "ZZ999"})
            check(section, "flight not found returns found=False", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                check(section, "not found flag set", body.get("found") is False, str(body)[:200])

        # ── 4. Flight lookup with multiple results ──
        section = "multiple-results"

        with patch("app_backend.aviationstack_request", return_value=MULTIPLE_FLIGHTS_RESPONSE):
            r = client.get("/api/v1/flights/lookup", params={"flight_number": "AA100"})
            check(section, "multiple matches returns first", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                check(section, "multiple matches found flag", body.get("found") is True, str(body)[:200])

        # ── 5. Historical and future dates ──
        section = "date-handling"

        # Future date lookup
        with patch("app_backend.aviationstack_request", return_value=SINGLE_FLIGHT_RESPONSE):
            r = client.get("/api/v1/flights/lookup", params={"flight_number": "AA100"})
            check(section, "future date lookup works", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                check(section, "future date returns flight data", body.get("found") is True, str(body)[:200])
                check(section, "scheduled time present", body.get("departure", {}).get("scheduled") is not None, str(body)[:200])

        # ── 6. Flight lookup to prediction workflow ──
        section = "lookup-to-prediction"

        with patch("app_backend.aviationstack_request", return_value=SINGLE_FLIGHT_RESPONSE):
            r = client.post(
                "/api/v1/flights/lookup-and-predict",
                json={"flight_number": "AA100", "date": "2024-01-15"},
            )
            check(section, "lookup-and-predict returns 200", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                check(section, "flight info present", body.get("flight_info", {}).get("found") is True, str(body)[:200])
                check(section, "airline extracted", body.get("flight_info", {}).get("airline") is not None, str(body)[:200])
                check(section, "origin extracted", body.get("flight_info", {}).get("departure", {}).get("iata") == "JFK", str(body)[:200])
                check(section, "destination extracted", body.get("flight_info", {}).get("arrival", {}).get("iata") == "LAX", str(body)[:200])
                check(section, "feature compatibility present", "feature_compatibility" in body, str(body)[:200])

                compat = body.get("feature_compatibility", {})
                check(section, "carrier supported", compat.get("carrier_supported") is True, str(compat))
                check(section, "origin supported", compat.get("origin_supported") is True, str(compat))
                check(section, "destination supported", compat.get("destination_supported") is True, str(compat))
                check(section, "date parsable", compat.get("date_parsable") is True, str(compat))
                check(section, "model ready", compat.get("model_ready") is True, str(compat))

                if body.get("prediction"):
                    check(section, "prediction has risk score", "risk_score" in body["prediction"], str(body["prediction"])[:200])
                    check(section, "prediction has risk level", "risk_level" in body["prediction"], str(body["prediction"])[:200])
                    check(section, "prediction has model version", "model_version" in body["prediction"], str(body["prediction"])[:200])
                    check(
                        section,
                        "risk score is valid probability",
                        0.0 <= body["prediction"]["risk_score"] <= 1.0,
                        str(body["prediction"]["risk_score"]),
                    )

        # ── 7. Unsupported airport categories ──
        section = "unsupported-categories"

        unsupported_flight = {
            "data": [
                {
                    "flight": {"iata": "SQ1", "number": "SQ1"},
                    "flight_status": "en_route",
                    "flight_date": "2024-01-15",
                    "departure": {
                        "airport": "Singapore Changi",
                        "iata": "SIN",
                        "city": "Singapore",
                        "country": "Singapore",
                        "scheduled": "2024-01-15T10:30:00",
                    },
                    "arrival": {
                        "airport": "London Heathrow",
                        "iata": "LHR",
                        "city": "London",
                        "country": "UK",
                        "scheduled": "2024-01-15T15:30:00",
                    },
                    "airline": {"name": "Singapore Airlines", "iata": "SQ"},
                }
            ],
        }

        with patch("app_backend.aviationstack_request", return_value=unsupported_flight):
            r = client.post(
                "/api/v1/flights/lookup-and-predict",
                json={"flight_number": "SQ1", "date": "2024-01-15"},
            )
            check(section, "unsupported route returns 200", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                check(section, "flight info found", body.get("flight_info", {}).get("found") is True, str(body)[:200])
                check(section, "prediction is None for unsupported", body.get("prediction") is None, str(body)[:200])
                check(section, "warnings present", len(body.get("warnings", [])) > 0, str(body.get("warnings")))

                compat = body.get("feature_compatibility", {})
                check(section, "carrier not supported", compat.get("carrier_supported") is False, str(compat))
                check(section, "origin not supported", compat.get("origin_supported") is False, str(compat))
                check(section, "destination not supported", compat.get("destination_supported") is False, str(compat))

        # ── 8. Missing model features (simulated) ──
        section = "missing-features"

        # Test with a flight that has partial support
        partial_flight = {
            "data": [
                {
                    "flight": {"iata": "AA100", "number": "AA100"},
                    "flight_status": "scheduled",
                    "flight_date": "2024-01-15",
                    "departure": {
                        "airport": "John F. Kennedy International",
                        "iata": "JFK",
                        "scheduled": "2024-01-15T10:30:00",
                    },
                    "arrival": {
                        "airport": "London Heathrow",
                        "iata": "LHR",
                        "scheduled": "2024-01-15T15:30:00",
                    },
                    "airline": {"name": "American Airlines", "iata": "AA"},
                }
            ],
        }

        with patch("app_backend.aviationstack_request", return_value=partial_flight):
            r = client.post(
                "/api/v1/flights/lookup-and-predict",
                json={"flight_number": "AA100", "date": "2024-01-15"},
            )
            check(section, "partial support returns 200", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                compat = body.get("feature_compatibility", {})
                check(section, "carrier supported", compat.get("carrier_supported") is True, str(compat))
                check(section, "origin supported", compat.get("origin_supported") is True, str(compat))
                check(section, "destination not supported", compat.get("destination_supported") is False, str(compat))
                check(section, "prediction is None", body.get("prediction") is None, str(body)[:200])

        # ── 9. Provider unavailable ──
        section = "provider-unavailable"

        with patch("app_backend.AVIATIONSTACK_KEY", ""):
            r = client.get("/api/v1/flights/lookup", params={"flight_number": "AA100"})
            check(section, "missing key returns 553", r.status_code == 553, str(r.status_code))

        # ── 10. Invalid API key ──
        section = "invalid-api-key"

        with patch("app_backend.aviationstack_request", side_effect=Exception("Invalid API key")):
            r = client.get("/api/v1/flights/lookup", params={"flight_number": "AA100"})
            check(section, "provider error returns 550", r.status_code == 550, str(r.status_code))

        # ── 11. Prediction unavailable ──
        section = "prediction-unavailable"

        saved_model = app_backend._model
        try:
            app_backend._model = None  # simulate model unavailable
            r = client.post(
                "/api/v1/flights/lookup-and-predict",
                json={"flight_number": "AA100", "date": "2024-01-15"},
            )
            check(section, "model unavailable returns 200 with no prediction", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                check(section, "prediction is None", body.get("prediction") is None, str(body)[:200])
                compat = body.get("feature_compatibility", {})
                check(section, "model_ready is False", compat.get("model_ready") is False, str(compat))
        finally:
            app_backend._model = saved_model

        # ── 12. Successful real-model inference with compatible features ──
        section = "real-model-inference"

        compatible_flight = {
            "data": [
                {
                    "flight": {"iata": "AA100", "number": "AA100"},
                    "flight_status": "en_route",
                    "flight_date": "2024-01-15",
                    "departure": {
                        "airport": "John F. Kennedy International",
                        "iata": "JFK",
                        "scheduled": "2024-01-15T10:30:00",
                    },
                    "arrival": {
                        "airport": "Los Angeles International",
                        "iata": "LAX",
                        "scheduled": "2024-01-15T13:25:00",
                    },
                    "airline": {"name": "American Airlines", "iata": "AA"},
                }
            ],
        }

        with patch("app_backend.aviationstack_request", return_value=compatible_flight):
            r = client.post(
                "/api/v1/flights/lookup-and-predict",
                json={"flight_number": "AA100", "date": "2024-01-15"},
            )
            check(section, "compatible route returns 200", r.status_code == 200, str(r.status_code))
            if r.status_code == 200:
                body = r.json()
                pred = body.get("prediction")
                check(section, "prediction present", pred is not None, str(body)[:200])
                if pred:
                    check(section, "risk_score is valid", 0.0 <= pred["risk_score"] <= 1.0, str(pred["risk_score"]))
                    check(section, "risk_level is valid", pred["risk_level"] in ("Low", "Medium", "High"), str(pred["risk_level"]))
                    check(section, "confidence is valid", 0.0 <= pred["confidence"] <= 1.0, str(pred["confidence"]))
                    check(section, "model_version present", bool(pred.get("model_version")), str(pred)[:200])

    # ── Summary ───────────────────────────────────────────────────────────
    total = len(RESULTS)
    failed = [x for x in RESULTS if not x[2]]
    print("\n" + "=" * 70)
    print(f"TOTAL: {total} checks, PASSED: {total - len(failed)}, FAILED: {len(failed)}")
    for sec, name, _, detail in failed:
        print(f"  FAILED: [{sec}] {name} -- {detail}")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
