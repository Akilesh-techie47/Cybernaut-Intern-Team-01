# Ham-gap analysis — why the staged email model over-flags legitimate mail

Date: 2026-10-10. Production `models/` untouched; all v2 work stays in staging.

## Production vs staged evidence (identical 200 messages)

| Test | Production (SMS model) | Staged v1 (SpamAssassin email SVM) |
|---|---|---|
| Short 100 | acc 0.64, prec 1.00, rec 0.28, F1 0.44 — 0 FP / 36 FN | acc 0.71, prec 0.64, rec 0.98, F1 0.77 — **28 FP** / 1 FN |
| Full-email 100 | acc 0.74, prec 0.83, rec 0.60, F1 0.70 — 6 FP / 20 FN | acc 0.61, prec 0.56, rec 1.00, F1 0.72 — **39 FP** / 0 FN |

The staged model catches all spam but is unusable: it flags 39/50 legitimate
emails (meeting agendas, payslips, shipping notices, library reminders).

## What the training ham actually is

`data/raw/email_spam_ham.csv`: 4,111 ham / 1,811 spam from SpamAssassin (2002–2005).
Sampled ham subjects are mailing-list/Usenet chatter (`Re: [ILUG] ...`,
`Re: [Razor-users] ...`, news forwards, jokes) — not modern business mail.

Keyword probe over all 4,111 training-ham subject+body texts:

| Category | Training-ham hits | Verdict |
|---|---|---|
| Payslip / salary slip | **0** | MISSING |
| Payroll | 2 | effectively missing |
| Purchase order | 1 | effectively missing |
| Invoice | 6 | effectively missing |
| Order confirmation / delivery | 38 (mostly list chatter, not transactional templates) | missing as a genre |
| Meeting invitation / appointment | 64 (mostly `Re:` threads, not invites/confirmations) | missing as a genre |
| Newsletter | 209 (present but 2002-era announcement style) | weak / dated |
| Library / books-due reminder | 48 (mentions, not reminder templates) | missing as a genre |
| Shipping / tracking / delivery notice | 95 (mentions, not carrier templates) | missing as a genre |

## Missing categories (priority order for sourcing)

1. Payslips / salary statements
2. Payroll / HR self-service notifications
3. Order confirmations, shipping updates, delivery notices, returns/refunds
4. Invoices, receipts, purchase orders, reimbursements
5. Meeting invitations / confirmations / calendar updates, appointments
6. Modern newsletters and promotional-but-legitimate mail
7. Library / fee / deadline reminders, utility bills, statements

## Consequence for this iteration

No genuine modern-transactional ham is available in this environment (no
customer mailbox, no licensed feed, and web-scraping mailboxes is not an
option). Per the brief, this limitation is reported as-is, and a
**clearly labeled synthetic generator** (`src/spam_classifier/synthetic_ham.py`,
`source='synthetic'`) is provided as an *optional development aid only* —
its output is template-generated, never genuine customer data, and is kept
identifiable by provenance through training, evaluation, and reporting.
