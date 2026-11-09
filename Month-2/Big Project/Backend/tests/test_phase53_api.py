"""
Phase 5.3 - Backend API verification suite.

Runs against the real FastAPI app in-process (TestClient) with the REAL
ML artifacts loaded (logistic_regression_new.joblib +
preprocessor_compatible.joblib). Fallback-only checks are explicitly
marked as such and do NOT count as integration evidence.

Run:  python tests/test_phase53_api.py
Exit code 0 = all checks passed.
"""

import json
import os
import sys
import time
from pathlib import Path

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


def main():
    with TestClient(app_backend.app) as client:
        app = app_backend.app

        # ── Artifact sanity (real model evidence) ──────────────────────────
        check(
            "artifacts",
            "logistic_regression_new.joblib exists",
            app_backend.NEW_MODEL_PATH.exists(),
            str(app_backend.NEW_MODEL_PATH),
        )
        check(
            "artifacts",
            "preprocessor_compatible.joblib exists",
            app_backend.NEW_PREPROCESSOR_PATH.exists(),
            str(app_backend.NEW_PREPROCESSOR_PATH),
        )
        check(
            "artifacts",
            "loaded model is sklearn LogisticRegression",
            app_backend._model is not None
            and app_backend._model.__class__.__name__ == "LogisticRegression",
            getattr(app_backend._model, "__class__", type(None)).__name__,
        )
        check(
            "artifacts",
            "feature count is 654",
            app_backend._feature_names is not None
            and len(app_backend._feature_names) == 654,
            str(len(app_backend._feature_names or [])),
        )
        check(
            "artifacts",
            "model info loaded from model_metadata.json",
            app_backend._model_info is not None,
            getattr(app_backend._model_info, "name", "None"),
        )

        # ── 11 documented endpoints ───────────────────────────────────────
        rate_limit_reset(app)

        r = client.get("/health")
        check("endpoint", "GET /health -> 200", r.status_code == 200 and r.json().get("status") == "healthy", str(r.status_code))

        r = client.get("/")
        check("endpoint", "GET / -> 200", r.status_code == 200 and "docs" in r.json(), str(r.status_code))

        r = client.get("/docs")
        check("endpoint", "GET /docs -> 200", r.status_code == 200, str(r.status_code))

        r = client.get("/redoc")
        check("endpoint", "GET /redoc -> 200", r.status_code == 200, str(r.status_code))

        r = client.get("/openapi.json")
        paths = list(r.json().get("paths", {}).keys()) if r.status_code == 200 else []
        check("endpoint", "GET /openapi.json -> 200", r.status_code == 200, f"{len(paths)} paths")

        r = client.get("/api/v1/status")
        body = r.json() if r.status_code == 200 else {}
        services = body.get("services", {})
        check(
            "endpoint",
            "GET /api/v1/status -> 200 with model+preprocessor services",
            r.status_code == 200 and "model" in services and "preprocessor" in services,
            f"{r.status_code} status={body.get('status')} services={services}",
        )

        r = client.get("/api/v1/airlines/references")
        body = r.json() if r.status_code == 200 else {}
        check(
            "endpoint",
            "GET /api/v1/airlines/references -> 200",
            r.status_code == 200 and body.get("total_airlines", 0) > 0 and body.get("total_airports", 0) > 0,
            f"{r.status_code} airlines={body.get('total_airlines')} airports={body.get('total_airports')}",
        )

        r = client.get("/api/v1/routes/analytics")
        body = r.json() if r.status_code == 200 else []
        check(
            "endpoint",
            "GET /api/v1/routes/analytics -> 200 list",
            r.status_code == 200 and isinstance(body, list) and len(body) >= 1,
            f"{r.status_code} routes={len(body) if isinstance(body, list) else 'n/a'}",
        )

        r = client.get("/api/v1/model/info")
        body = r.json() if r.status_code == 200 else {}
        check(
            "endpoint",
            "GET /api/v1/model/info -> 200 with metrics",
            r.status_code == 200 and len(body.get("metrics", {})) > 0,
            f"{r.status_code} name={body.get('name')} features={body.get('features')}",
        )

        # ── POST /api/v1/predict: REAL inference ──────────────────────────
        payload = {
            "flight_number": "AA123",
            "origin": "JFK",
            "destination": "LAX",
            "date": "2026-11-20",
        }
        r = client.post("/api/v1/predict", json=payload)
        pred = r.json() if r.status_code == 200 else {}
        check(
            "predict",
            "valid payload -> 200 with risk fields",
            r.status_code == 200
            and 0.0 <= pred.get("risk_score", -1) <= 1.0
            and pred.get("risk_level") in ("Low", "Medium", "High"),
            f"{r.status_code} score={pred.get('risk_score')} level={pred.get('risk_level')} ms={pred.get('prediction_time_ms')}",
        )

        # Prove endpoint score == direct model output from the same artifacts
        try:
            import numpy as np

            fb = app_backend.build_feature_vector(app_backend.FlightInfo(**payload))
            X = app_backend.transform_features(fb)
            direct = float(app_backend._model.predict_proba([X])[0][1])
            same = abs(direct - pred.get("risk_score", -9)) < 1e-4
            check(
                "predict",
                "endpoint score equals direct joblib model output",
                same,
                f"endpoint={pred.get('risk_score')} direct={round(direct, 6)}",
            )
        except Exception as e:
            check("predict", "endpoint score equals direct joblib model output", False, str(e))

        # Determinism: identical input -> identical output (real model, not random)
        r2 = client.post("/api/v1/predict", json=payload)
        pred2 = r2.json() if r2.status_code == 200 else {}
        check(
            "predict",
            "deterministic across identical requests",
            pred2.get("risk_score") == pred.get("risk_score"),
            f"{pred.get('risk_score')} vs {pred2.get('risk_score')}",
        )

        # Invalid inputs -> 422 (validation errors, no fake prediction)
        bad = {"flight_number": "AA123", "origin": "JFK", "destination": "LAX", "date": "not-a-date"}
        r = client.post("/api/v1/predict", json=bad)
        check("validation", "malformed date -> 422", r.status_code == 422, str(r.status_code))

        r = client.post("/api/v1/predict", json={})
        check("validation", "empty payload -> 422", r.status_code == 422, str(r.status_code))

        r = client.post("/api/v1/predict", json={"flight_number": "", "origin": "", "destination": "", "date": "2026-11-20"})
        check("validation", "blank required fields -> 422", r.status_code == 422, str(r.status_code))

        # ── FALLBACK path (marked as fallback, NOT integration evidence) ──
        saved_model = app_backend._model
        try:
            app_backend._model = None  # simulate artifacts failing to load
            r = client.post("/api/v1/predict", json=payload)
            detail = r.json() if isinstance(r.json(), dict) else {}
            err = detail.get("error", "")
            check(
                "fallback (not integration evidence)",
                "artifacts unavailable -> HTTP 550 model_unavailable",
                r.status_code == 550 and err == "model_unavailable",
                f"{r.status_code} error={err}",
            )
        finally:
            app_backend._model = saved_model

        # After restore, prediction works again
        r = client.post("/api/v1/predict", json=payload)
        check(
            "predict",
            "model restored after fallback test",
            r.status_code == 200,
            str(r.status_code),
        )

        # ── Flight lookup (real AviationStack key from .env, server-side) ─
        rate_limit_reset(app)
        has_key = bool(app_backend.AVIATIONSTACK_KEY)
        r = client.get("/api/v1/flights/lookup", params={"flight_number": "AA100"})
        lookup_status = r.status_code
        try:
            lookup_body = r.json()
        except Exception:
            lookup_body = {}
        key_leaked = False
        if has_key and app_backend.AVIATIONSTACK_KEY:
            key_leaked = app_backend.AVIATIONSTACK_KEY in r.text
        check(
            "lookup",
            "GET /api/v1/flights/lookup returns a typed response",
            lookup_status in (200, 552, 553, 550),
            f"{lookup_status} body={json.dumps(lookup_body)[:160]}",
        )
        check(
            "lookup",
            "API key never present in response body",
            not key_leaked,
            "key configured" if has_key else "key NOT configured in env",
        )
        check(
            "lookup",
            "missing-key state is explicit (553) OR key configured",
            has_key or lookup_status == 553,
            f"has_key={has_key} status={lookup_status}",
        )

        # ── CORS preflight verification ───────────────────────────────────
        rate_limit_reset(app)
        r = client.options(
            "/api/v1/predict",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        acao = r.headers.get("access-control-allow-origin", "")
        check(
            "cors",
            "preflight from http://localhost:3000 accepted",
            r.status_code in (200, 204) and acao == "http://localhost:3000",
            f"{r.status_code} ACAO={acao!r} methods={r.headers.get('access-control-allow-methods', '')}",
        )

        r = client.options(
            "/api/v1/predict",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        acao_bad = r.headers.get("access-control-allow-origin", "")
        check(
            "cors",
            "preflight from unknown origin rejected",
            acao_bad == "" or acao_bad == "null",
            f"{r.status_code} ACAO={acao_bad!r}",
        )

        r = client.get(
            "/api/v1/status",
            headers={"Origin": "http://localhost:3000"},
        )
        acao_get = r.headers.get("access-control-allow-origin", "")
        check(
            "cors",
            "simple GET carries CORS header for frontend origin",
            r.status_code == 200 and acao_get == "http://localhost:3000",
            f"{r.status_code} ACAO={acao_get!r}",
        )

        # No wildcard origins configured
        check(
            "cors",
            "no wildcard origin configured",
            "*" not in app_backend.CORS_ALLOWED_ORIGINS,
            str(app_backend.CORS_ALLOWED_ORIGINS),
        )

        # ── Rate limiting ─────────────────────────────────────────────────
        rate_limit_reset(app)
        statuses = []
        for _ in range(65):
            resp = client.get("/api/v1/airlines/references")
            statuses.append(resp.status_code)
            if resp.status_code == 429:
                break
        saw_429 = 429 in statuses
        check(
            "ratelimit",
            "429 returned after 60 req/min per IP",
            saw_429,
            f"requests={len(statuses)} last={statuses[-1]}",
        )
        rate_limit_reset(app)

        # ── OpenAPI endpoint inventory ────────────────────────────────────
        r = client.get("/openapi.json")
        if r.status_code == 200:
            doc_paths = sorted(r.json().get("paths", {}).keys())
            expected_api = [
                "/api/v1/airlines/references",
                "/api/v1/flights/lookup",
                "/api/v1/model/info",
                "/api/v1/predict",
                "/api/v1/routes/analytics",
                "/api/v1/status",
            ]
            missing = [p for p in expected_api if p not in doc_paths]
            check(
                "openapi",
                "all 6 API routes documented",
                not missing,
                f"missing={missing} total={len(doc_paths)}",
            )
            # 11 documented endpoints = 6 API + / + /health + /docs + /redoc + /openapi.json
            all_routes = {
                r_.path
                for r_ in app.routes
                if hasattr(r_, "path")
            }
            known_11 = {
                "/",
                "/health",
                "/docs",
                "/redoc",
                "/openapi.json",
                *expected_api,
            }
            check(
                "openapi",
                "11 documented endpoints present",
                known_11.issubset(all_routes),
                f"found={len(known_11 & all_routes)}/11 missing={sorted(known_11 - all_routes)}",
            )

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
