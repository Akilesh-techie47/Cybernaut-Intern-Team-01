# v2 evaluation — synthetic transactional ham + SpamAssassin (STAGING ONLY)

Production `models/` was NOT modified. All v2 artifacts live in
`models_staging_v2/`, `reports/metrics_email_v2/`, `reports/figures_email_v2/`.
Deployed site behavior is unchanged (health 200 on the production SMS model).

## Training pool (provenance-tracked, leakage-screened)

`data/raw/email_train_v2.csv` (git-ignored; provenance in `pool_provenance.json`):
7,101 rows — `spamassassin/ham` 4,111, `spamassassin/spam` 1,811,
`synthetic/ham` 1,179 across 10 template categories (manifest:
`reports/synthetic_ham_manifest.json`, seed 7). No genuine modern ham exists in
this environment — the synthetic rows are template-generated dev aid, never
presented as genuine mail.

Leakage screen (`leakage_report.json`, exact + token-Jaccard ≥ 0.90 vs all 300
test-message forms): **0 exact, 0 near hits → 0 rows excluded.**

## Held-out (v2 split, n=1,421) — reference only, NOT success evidence

| model | acc | spam prec | spam rec | spam F1 | CM |
|---|---|---|---|---|---|
| NB | 0.9599 | 0.9446 | 0.8950 | 0.9191 | [[1040,19],[38,324]] |
| LR | 0.9761 | 0.9881 | 0.9171 | 0.9513 | [[1055,4],[30,332]] |
| SVM (selected) | 0.9852 | 0.9776 | 0.9641 | 0.9708 | [[1051,8],[13,349]] |

## External 200 (unchanged inputs) — production vs v2-SVM

| Test | Production (SMS) | v2-SVM (staging) |
|---|---|---|
| Short 100 | acc 0.64, prec 1.00, rec 0.28, F1 **0.44**, CM [[50,0],[36,14]] | acc 0.80, prec 0.73, rec 0.94, F1 **0.82**, CM [[33,17],[3,47]] |
| Full-email 100 | acc 0.74, prec 0.83, rec 0.60, F1 **0.70**, CM [[44,6],[20,30]] | acc 0.77, prec 0.72, rec 0.88, F1 **0.79**, CM [[33,17],[6,44]] |

Ham false-positive rate: production 6/50 (12%) → v2 17/50 (**34%**).

## Per-category ham FPs, full-email test (keyword mapping, see analysis script)

| Category | n | Production FP | v2 FP |
|---|---|---|---|
| payslip / payroll / purchase_order / order_ship | 5 | 5 | 0 |
| invoice / statement_bill / appointment | 7 | 1 | 3 |
| meeting / library / newsletter | 7 | 0 | 1 |
| other personal/edu | 31 | 0 | 13 |
| **Transactional subset (12)** | 12 | **6** | **3** |

v2 fixed the transactional FPs it was trained to fix (payslip, payroll, PO,
order-shipped now all correct) but now flags 13/31 casual personal/edu mails —
a category the templates never covered. The FP mass moved, not vanished.

## Acceptance criteria (agreed for promotion)

Promote iff on the unchanged full-email test: ham FP ≤ 6 AND spam recall ≥ 0.60
AND F1 > 0.6977, with no collapse on short messages and held-out F1 ≥ 0.90.

## Verdict: NO PROMOTION ❌

v2 meets recall (0.88), F1 (0.79), and held-out (0.97) — but ham FP is **17,
nearly 3× the allowed 6**. Promoting would make the live site flag roughly a
third of legitimate mail. Transactional-only FPs halved (6→3), proving the
approach works; the blocker is purely the lack of genuine diverse ham
(personal/edu/casual), which templates cannot faithfully reproduce.

## Next step that would change the verdict

Source genuine modern ham covering personal, educational, and casual mail (not
just transactional) — e.g. user-donated mailbox exports via
`ham_import --input mailbox.csv:modern_ham` — then rebuild the pool, re-screen,
retrain, and re-run this identical external test.
