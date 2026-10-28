# v3 readiness record — data-gated, NO training, NO promotion

Date: 2026-10-10. Production `models/` and deployment config untouched
(verified: `models/` holds only the original two files; site health 200 on
the production SMS model). v2 stays in staging (17 full-email FPs > limit 6).

## Paths inspected (resolved, not assumed)

- `reports/HAM_GAP_ANALYSIS.md` — read; missing-category evidence stands.
- `reports/metrics_email_v2/` — 9 files (metrics, leakage, pool provenance,
  v2 external-test JSONs + per-row predictions, V2_EVALUATION.md).
- Manifest: `reports/synthetic_ham_manifest.json` EXISTS;
  `reports/metrics/synthetic_ham_manifest.json` does NOT exist.
- `models_staging_v2/` — metadata.json + joblib (staged only, never served).
- `ham_import.py` (validate/build_pool, sources spamassassin/modern_ham/synthetic),
  `leakage.py` (300 test forms, exact + Jaccard ≥ 0.90) — APIs confirmed.
- Data scan: `data/raw/*.csv` = corpus-derived + synthetic only; Downloads =
  the two test files only. **Zero genuine modern-ham rows anywhere.**

## Validation performed this round

- Coverage audit on the cleaned v2 pool: 5,290 ham (4,111 genuine-2002,
  1,179 synthetic, **0 modern**), 1,811 spam; per-category genuine/synthetic
  table in `CATEGORY_COVERAGE.md` + `category_coverage.json`.
- Data gate run: `coverage --require-modern-ham 500` → **exit 2, BLOCKED**.
- Full suite: **29/29 pytest pass** (4 new coverage tests). Health: **200**.

## What is still needed (exact)

A `label,subject,body` utf-8 CSV of **≥500 genuine modern ham (≥50/category)**
across personal, educational, conversational, transactional, business,
newsletter, notification — collected per `reports/HAM_COLLECTION_GUIDE.md`
(consent, PII-minimized, no test copies). Then run the guide's steps 1–6
verbatim (import → pool → leakage screen → gate → `models_staging_v3` →
unchanged 200-message test). No retraining is justified before that: the only
trainable pool is byte-identical to v2's.

## Gate and verdict

Acceptance gate unchanged (FP ≤ 6, recall ≥ 0.60, F1 > 0.6977). No candidate
was trained, so nothing is evaluated and nothing passes. **NO promotion.
Production behavior preserved.** No claim of production-readiness is made on
held-out F1 (v2: 0.9708), synthetic results, or unit tests (29/29) — the
external FP evidence (17/50) is the binding verdict until genuine ham arrives.

## Limitations

- Keyword coverage rules are coarse approximations (documented order effects);
  exact counts reproducible via `coverage.py`, not hand-tuned.
- The gate counts `source='modern_ham'` rows but cannot verify donor consent —
  that remains a human attestation in the collection guide.
- Near-duplicate threshold (0.90) may miss heavy paraphrases of test messages;
  the exact-test-copy ban in the guide covers the remainder by policy.
