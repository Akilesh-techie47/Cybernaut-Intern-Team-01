# Category-coverage report — v3 pool audit (genuine vs synthetic separated)

Generated programmatically: `coverage --pool data/raw/email_train_v2_clean.csv`
(full table in `category_coverage.json`; rules in `coverage.CATEGORY_RULES`,
first-match-wins, reproducible). Test-ham map: `test_ham_categories.csv`
(evaluation metadata only — never training input).

## Training-ham coverage by origin (exact counts)

| Category | Genuine (spamassassin + modern_ham) | Synthetic | Total | Modern genuine |
|---|---|---|---|---|
| personal | 197 | 0 | 197 | 0 |
| educational | 243 | 0 | 243 | 0 |
| conversational | 4 | 0 | 4 | 0 |
| transactional | 600 | 710 | 1,310 | 0 |
| business | 227 | 195 | 422 | 0 |
| newsletter | 196 | 0 | 196 | 0 |
| notification | 370 | 274 | 644 | 0 |
| uncategorized | 2,274 | 0 | 2,274 | 0 |
| **Total ham** | **4,111** | **1,179** | **5,290** | **0** |

Pool also holds 1,811 genuine SpamAssassin spam. No `modern_ham` rows exist in
any category: **every "genuine" cell above is 2002–2005 mailing-list ham.**

## Test-ham demand (50 full-email ham, same keyword rules)

notification 14, business 12, transactional 12, educational 4, personal 4,
uncategorized 4, conversational 0, newsletter 0.

## Gap reading

- The v2 FP disaster concentrates where genuine modern coverage is thinnest:
  casual personal/educational phrasing (test needs 8; genuine modern = 0) and
  modern transactional templates (test needs 12; genuine modern = 0).
- Two taxonomy footnotes, no hidden adjustments: (a) most SpamAssassin ham is
  `uncategorized` (2,274) — reported, not force-fit; (b) the generator's
  newsletter/library/appointment templates keyword-map into
  notification/business, so `synthetic newsletter = 0` reflects the coarse
  taxonomy, not absent templates (per-template counts: manifest
  `reports/synthetic_ham_manifest.json`).
- Synthetic rows cover only 3 of 7 rule buckets and are template-bound; they
  cannot stand in for genuine personal/educational/conversational mail. The
  v2 result (13/31 personal-edu FPs) is the receipt.
