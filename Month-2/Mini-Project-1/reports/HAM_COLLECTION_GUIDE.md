# Genuine modern-ham collection & import workflow (v3 data gate input)

Status: NO genuine modern ham has been provided yet (verified 2026-10-10:
`data/raw/` holds only SpamAssassin-derived and synthetic CSVs; Downloads holds
only the two test files). v3 training is BLOCKED until this workflow delivers.
This guide is the exact procedure to unblock it — without scraping mailboxes,
without touching test data, and without weakening any acceptance gate.

## 1. What counts as acceptable genuine ham

- Real messages a person received and is authorized to share: payslips, payroll
  notices, order/shipping/delivery mails, invoices, receipts, purchase orders,
  meeting invites, appointment confirmations, newsletters the recipient opted
  into, library/fee/deadline reminders, utility bills, personal and
  educational correspondence.
- Target minimum: **500 rows total, ≥50 per category** across personal,
  educational, conversational, transactional, business, newsletter, notification
  (see `CATEGORY_COVERAGE.md`; the gate enforces the total, the report tracks
  the spread).

## 2. Privacy rules (mandatory, no exceptions)

1. **Donor consent**: every message must come from its recipient with explicit
   permission to use it for spam-filter research, or from a mailbox the
   collector owns. Never use someone else's inbox, work mailbox exports pulled
   without authorization, or scraped webmail.
2. **Minimize before sharing**: keep ONLY `subject` + plain-text `body`. Drop
   attachments, images, headers (From/To/Message-ID), signatures with phone
   numbers, account numbers, one-time codes, and any credential or payment
   secret. Redact with `[REDACTED]` rather than deleting the sentence, so
   phrasing stays natural.
3. **No test contamination**: do NOT copy, paraphrase, or rebuild any message
   from the 200-message external test files. The leakage screen rejects
   exact and near-duplicate (token-Jaccard ≥ 0.90) matches against all 300
   test-message forms — deliberate test copies will be caught and excluded.
4. **No scraping**: do not harvest mailing-list archives, demo inboxes, or
   other people's published mail without a compatible license and consent.

## 3. Format spec

CSV, utf-8, header row exactly: `label,subject,body`

- `label`: `ham` for every row in a ham collection (the importer also accepts
  `spam` rows with `source=modern_ham` if genuine modern spam is donated the
  same way — same rules apply).
- `subject`, `body`: plain text. Either may be empty, but not both.
- Unknown labels (e.g. `maybe`, blanks) FAIL the import loudly — nothing is
  silently relabeled.

## 4. Import workflow (uses the existing validated importer)

From the project root, with the file staged OUTSIDE the repo (e.g. Downloads):

```powershell
$env:PYTHONPATH = "src"
# 1. Validate + stamp provenance (aborts on bad labels; reports dupes/empties)
python -m spam_classifier.ham_import --input "C:\path\to\modern_ham.csv:modern_ham" `
    --pool data/raw/modern_ham_validated.csv --provenance reports/metrics_email_v3/modern_ham_provenance.json
# 2. Combine with history (SpamAssassin) into the v3 pool
python -m spam_classifier.ham_import `
    --input "data/raw/email_spam_ham.csv:spamassassin" `
    --input "data/raw/modern_ham_validated.csv:modern_ham" `
    --pool data/raw/email_train_v3.csv --provenance reports/metrics_email_v3/pool_provenance_v3.json
# 3. Leakage screen vs all 300 test-message forms (excludes hits)
python -m spam_classifier.leakage --pool data/raw/email_train_v3.csv `
    --clean-pool data/raw/email_train_v3_clean.csv --report reports/metrics_email_v3/leakage_report_v3.json
# 4. Coverage + data gate (exit 0 only with >=500 genuine modern_ham rows)
python -m spam_classifier.coverage --pool data/raw/email_train_v3_clean.csv --require-modern-ham 500
# 5. Train candidates to NEW staging only (never models/)
python -m spam_classifier.train --data data/raw/email_train_v3_clean.csv `
    --models-dir models_staging_v3 --metrics-dir reports/metrics_email_v3 --figures-dir reports/figures_email_v3
# 6. Evaluate on the unchanged 200-message test set
python -m spam_classifier.external_test --name short_messages_v3 --csv "<short-test-csv>" --mode text --artifact models_staging_v3/spam_classifier_pipeline.joblib --out-dir reports/metrics_email_v3
python -m spam_classifier.external_test --name full_emails_v3 --csv "<full-test-csv>" --mode subject_body --artifact models_staging_v3/spam_classifier_pipeline.joblib --out-dir reports/metrics_email_v3
```

Promotion still requires the unchanged gate (full-email ham FP ≤ 6, spam
recall ≥ 0.60, F1 > 0.6977) plus a per-category FP review. Held-out F1 alone
promotes nothing.
