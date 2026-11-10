"""Phase 5.3 - live server verification (real HTTP against running servers).

Backend  : http://127.0.0.1:8000  (uvicorn via start_backend.py)
Frontend : http://localhost:3000   (next dev)

Run: python tests/test_phase53_live.py
"""
import sys
import time

import requests

BACKEND = "http://127.0.0.1:8000"
FRONTEND = "http://localhost:3000"
FRONTEND_ORIGIN = "http://localhost:3000"

RESULTS = []


def check(section, name, ok, detail=""):
    RESULTS.append((section, name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {section} :: {name}" + (f" -- {detail}" if detail else ""))


def wait_for_clean_rate_limit_window():
    """Make this suite deterministic regardless of prior activity.

    The backend enforces a sliding 60 req/min/IP window on counted
    endpoints. Previous runs (or manual probes) may have exhausted it,
    which would cause spurious 429 failures that say nothing about the
    integration itself. Force a known state: exhaust until 429 is
    observed, then wait one full window so it drains completely.
    (~65 cheap GETs + ~62s, once per run.)
    """
    print("[setup] draining backend rate-limit window for a clean measurement...")
    hit_429 = False
    for _ in range(65):
        try:
            r = requests.get(f"{BACKEND}/api/v1/airlines/references", timeout=5)
        except Exception:
            break
        if r.status_code == 429:
            hit_429 = True
            break
    if hit_429:
        # Wait past the 60s sliding window so all timestamps expire.
        time.sleep(62)
    else:
        # Window never filled (unexpected) - still wait one full window
        # to guarantee no stale entries remain.
        time.sleep(62)
    print("[setup] rate-limit window drained")


def main():
    wait_for_clean_rate_limit_window()

    # ── Backend endpoints over real HTTP ─────────────────────────────
    try:
        r = requests.get(f"{BACKEND}/health", timeout=5)
        check("backend", "GET /health -> 200", r.status_code == 200 and r.json().get("status") == "healthy", f"{r.status_code} {r.text[:60]}")
    except Exception as e:
        check("backend", "GET /health -> 200", False, str(e))
        print("Backend unreachable - aborting remaining live tests.")
        return 1

    r = requests.get(f"{BACKEND}/", timeout=5)
    check("backend", "GET / -> 200", r.status_code == 200, str(r.status_code))

    r = requests.get(f"{BACKEND}/docs", timeout=5)
    check("backend", "GET /docs -> 200", r.status_code == 200, str(r.status_code))

    r = requests.get(f"{BACKEND}/redoc", timeout=5)
    check("backend", "GET /redoc -> 200", r.status_code == 200, str(r.status_code))

    r = requests.get(f"{BACKEND}/openapi.json", timeout=5)
    check("backend", "GET /openapi.json -> 200", r.status_code == 200, str(r.status_code))

    r = requests.get(f"{BACKEND}/api/v1/status", timeout=5)
    body = r.json() if r.status_code == 200 else {}
    check(
        "backend",
        "GET /api/v1/status -> 200 healthy",
        r.status_code == 200 and body.get("status") == "healthy",
        f"{r.status_code} {body.get('status')} services={body.get('services')}",
    )

    r = requests.get(f"{BACKEND}/api/v1/airlines/references", timeout=5)
    b = r.json() if r.status_code == 200 else {}
    check("backend", "GET /api/v1/airlines/references -> 200", r.status_code == 200 and b.get("total_airlines", 0) > 0, str(r.status_code))

    r = requests.get(f"{BACKEND}/api/v1/routes/analytics", timeout=5)
    b = r.json() if r.status_code == 200 else []
    check("backend", "GET /api/v1/routes/analytics -> 200 list", r.status_code == 200 and isinstance(b, list) and len(b) >= 1, f"{r.status_code} n={len(b) if isinstance(b, list) else '?'}")

    r = requests.get(f"{BACKEND}/api/v1/model/info", timeout=5)
    b = r.json() if r.status_code == 200 else {}
    check("backend", "GET /api/v1/model/info -> 200", r.status_code == 200 and b.get("features") == 654, f"{r.status_code} features={b.get('features')} name={b.get('name')}")

    # ── Real ML prediction over HTTP ─────────────────────────────────
    payload = {"flight_number": "AA123", "origin": "JFK", "destination": "LAX", "date": "2026-11-20"}
    t0 = time.time()
    r = requests.post(f"{BACKEND}/api/v1/predict", json=payload, timeout=15)
    took = (time.time() - t0) * 1000
    p = r.json() if r.status_code == 200 else {}
    check(
        "predict",
        "POST /api/v1/predict -> 200 real inference",
        r.status_code == 200
        and 0.0 <= p.get("risk_score", -1) <= 1.0
        and p.get("risk_level") in ("Low", "Medium", "High"),
        f"{r.status_code} score={p.get('risk_score')} level={p.get('risk_level')} server_ms={p.get('prediction_time_ms')} wall_ms={took:.0f}",
    )

    r = requests.post(f"{BACKEND}/api/v1/predict", json={"flight_number": "X"}, timeout=10)
    check("validation", "invalid payload -> 422 over HTTP", r.status_code == 422, str(r.status_code))

    # ── Flight lookup (live provider) ────────────────────────────────
    r = requests.get(f"{BACKEND}/api/v1/flights/lookup", params={"flight_number": "AA100"}, timeout=20)
    b = r.json() if r.status_code == 200 else {}
    check(
        "lookup",
        "GET /api/v1/flights/lookup over HTTP",
        r.status_code in (200, 552),
        f"{r.status_code} found={b.get('found')} airline={str(b.get('airline'))[:40]}",
    )

    # ── CORS over real HTTP ──────────────────────────────────────────
    r = requests.options(
        f"{BACKEND}/api/v1/predict",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=5,
    )
    acao = r.headers.get("access-control-allow-origin", "")
    check(
        "cors",
        "real preflight from frontend origin accepted",
        r.status_code in (200, 204) and acao == FRONTEND_ORIGIN,
        f"{r.status_code} ACAO={acao!r} allow-methods={r.headers.get('access-control-allow-methods','')}",
    )

    r = requests.options(
        f"{BACKEND}/api/v1/predict",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
        timeout=5,
    )
    acao_bad = r.headers.get("access-control-allow-origin", "")
    check("cors", "real preflight from unknown origin rejected", acao_bad in ("", "null"), f"{r.status_code} ACAO={acao_bad!r}")

    r = requests.get(f"{BACKEND}/api/v1/status", headers={"Origin": FRONTEND_ORIGIN}, timeout=5)
    acao_get = r.headers.get("access-control-allow-origin", "")
    check("cors", "simple GET carries CORS header", acao_get == FRONTEND_ORIGIN, f"ACAO={acao_get!r}")

    # ── Frontend pages over real HTTP ────────────────────────────────
    pages = [
        ("/", ["AeroDelay AI", 'data-testid="lookup-form"', 'data-testid="home-status"']),
        ("/tracking", ['data-testid="tracking-form"', "Live Flight Tracking"]),
        ("/prediction", ['data-testid="predict-form"', "Delay Risk Prediction"]),
        ("/analytics", ['data-testid="analytics-loading"', "Route Analytics"]),
        ("/models", ['data-testid="model-loading"', "Model Information"]),
    ]
    for path, markers in pages:
        try:
            r = requests.get(f"{FRONTEND}{path}", timeout=60)
            html = r.text
            missing = [m for m in markers if m not in html]
            check(
                "frontend",
                f"GET {path} -> 200 with expected markup",
                r.status_code == 200 and not missing,
                f"{r.status_code} missing={missing} bytes={len(html)}",
            )
        except Exception as e:
            check("frontend", f"GET {path} -> 200 with expected markup", False, str(e))

    # CSS pipeline: the compiled stylesheet must exist and contain our theme
    try:
        r = requests.get(f"{FRONTEND}/", timeout=30)
        import re

        css_links = re.findall(
            r'href="(/_next/static/css/[^"]+\.css[^"]*)"', r.text
        )
        if css_links:
            css = requests.get(f"{FRONTEND}{css_links[0]}", timeout=15).text
            check(
                "frontend",
                "compiled CSS contains navy theme + custom utility",
                "--color-navy-950" in css and "home-hero-bg" in css,
                f"link={css_links[0]} len={len(css)} navy={'--color-navy-950' in css} hero={'home-hero-bg' in css}",
            )
        else:
            check("frontend", "compiled CSS contains navy theme + custom utility", False, "no CSS link found in HTML")
    except Exception as e:
        check("frontend", "compiled CSS contains navy theme + custom utility", False, str(e))

    total = len(RESULTS)
    failed = [x for x in RESULTS if not x[2]]
    print("\n" + "=" * 70)
    print(f"LIVE TOTAL: {total} checks, PASSED: {total - len(failed)}, FAILED: {len(failed)}")
    for sec, name, _, detail in failed:
        print(f"  FAILED: [{sec}] {name} -- {detail}")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
