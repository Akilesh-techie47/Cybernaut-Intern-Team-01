"""OPTIONAL DEVELOPMENT AID — synthetic modern-transactional ham generator.

Every row this script emits is TEMPLATE-GENERATED. It is NOT genuine customer
mail, NOT real business correspondence, and must NEVER be presented as such.
Its only purpose is to let the pipeline exercise modern transactional phrasing
(payslips, shipping notices, invoices, ...) until genuine ham can be sourced.

Provenance is enforced three ways:
  1. Output rows carry category '<name>' and are imported with source='synthetic'.
  2. A manifest JSON (generator version, seed, per-category counts, template
     hash) is written next to the CSV for the pool provenance record.
  3. All rows pass through leakage screening before training like any source.

Usage (from project root):
    $env:PYTHONPATH = "src"
    python -m spam_classifier.synthetic_ham --per-category 120 --seed 7
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pandas as pd  # noqa: E402

GENERATOR_VERSION = "synthetic_ham v1 (template dev aid; NOT genuine mail)"
OUT_CSV = PROJECT_ROOT / "data" / "raw" / "synthetic_ham.csv"
OUT_MANIFEST = PROJECT_ROOT / "reports" / "synthetic_ham_manifest.json"

NAMES = ["Asha", "Ravi", "Meera", "Arun", "Divya", "Karthik", "Priya", "Suresh",
         "Lakshmi", "Vijay", "Anita", "Rahul", "Sneha", "Manoj", "Kavya"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
COURSES = ["Data Structures", "Database Systems", "Operating Systems",
           "Machine Learning", "Computer Networks", "Web Programming"]
ITEMS = ["office stationery", "printer cartridges", "lab consumables",
         "network cables", "safety gloves", "notebooks", "USB drives"]
CARRIERS = ["FastTrack Couriers", "SpeedPost", "CityLink Logistics", "Metro Freight"]

# Each category: subject templates + body templates. {placeholders} filled per row.
TEMPLATES: dict[str, dict[str, list[str]]] = {
    "payslip": {
        "subjects": ["Your {month} payslip is available", "{month} salary statement ready",
                     "Payslip for {month} has been generated"],
        "bodies": ["Hi {name},\n\nYour payslip for {month} is now available on the employee portal. "
                   "Gross pay {amount} has been credited after standard deductions for tax and provident fund.\n\n"
                   "Contact payroll support if any figure looks incorrect.\n\nPayroll Team",
                   "Dear {name},\n\nThis confirms salary credit of {amount} for {month}. "
                   "The detailed statement can be downloaded from HR self-service.\n\nRegards,\nPayroll Department"],
    },
    "payroll": {
        "subjects": ["Please review your payroll profile", "Payroll profile update requested",
                     "Action needed: confirm your bank details for payroll"],
        "bodies": ["Hi {name},\n\nPlease review your payroll profile in the employee portal and confirm "
                   "that your bank account details and tax declarations for {month} are current.\n\n"
                   "No action is needed if everything is already correct.\n\nHR Operations",
                   "Hello {name},\n\nOur records show your tax declaration for this financial year is incomplete. "
                   "Kindly update it before the {day} payroll run so deductions are computed correctly.\n\nThank you,\nHR Team"],
    },
    "order_confirmation": {
        "subjects": ["Order {oid} confirmed", "Thank you for your order {oid}",
                     "Your purchase {oid} has been confirmed"],
        "bodies": ["Hi {name},\n\nThanks for shopping with us. Order {oid} for {item} (total {amount}) "
                   "is confirmed and will be packed shortly. A receipt is attached to this message.\n\n"
                   "Track progress from your account page.\n\nCustomer Care",
                   "Dear {name},\n\nOrder {oid} placed on {day} has been confirmed. Estimated dispatch is "
                   "within two working days. Reply to this message for any changes.\n\nBest regards,\nSales Desk"],
    },
    "shipping": {
        "subjects": ["Your order {oid} has shipped", "Shipment update for order {oid}",
                     "Your package via {carrier} is on its way"],
        "bodies": ["Hi {name},\n\nGood news: order {oid} shipped today via {carrier}. Tracking ID {tid}. "
                   "Delivery is expected within 3 to 5 working days.\n\nThanks for shopping with us.",
                   "Dear {name},\n\nYour package ({oid}, {item}) left our warehouse this morning. "
                   "You can follow it with tracking ID {tid} on the carrier website.\n\nRegards,\nDispatch Team"],
    },
    "invoice": {
        "subjects": ["Invoice {inv} for {item}", "Your invoice {inv} is ready",
                     "Payment reminder: invoice {inv} due {day}"],
        "bodies": ["Dear {name},\n\nPlease find invoice {inv} for {item} amounting to {amount}. "
                   "Payment is due by {day}. Bank transfer details are printed on the invoice.\n\n"
                   "Write back if you need a revised invoice.\n\nAccounts Team",
                   "Hi {name},\n\nThis is a friendly reminder that invoice {inv} ({amount}) falls due on {day}. "
                   "Ignore this note if payment was already made.\n\nThank you,\nBilling Desk"],
    },
    "purchase_order": {
        "subjects": ["Purchase order {oid} approved", "PO {oid} status update",
                     "Your purchase request {oid} has been approved"],
        "bodies": ["Hi {name},\n\nPurchase order {oid} for {item} has been approved by the department head. "
                   "Procurement will raise the supplier order this week.\n\nRegards,\nAdmin Office",
                   "Dear {name},\n\nYour purchase request {oid} ({item}, estimated {amount}) is approved. "
                   "Please coordinate with stores for delivery scheduling.\n\nAdmin Team"],
    },
    "meeting": {
        "subjects": ["Meeting invitation: {course} review on {day}", "Calendar invite: sprint review {day}",
                     "Appointment confirmation for {day} at {time}"],
        "bodies": ["Hi {name},\n\nYou are invited to the {course} review meeting on {day} at {time} in Room {room}. "
                   "Agenda: progress review, open issues, and next milestones.\n\nPlease accept this invite.\n\nCoordinator",
                   "Dear {name},\n\nThis confirms your appointment on {day} at {time} at the {place} clinic. "
                   "Please arrive ten minutes early and carry your ID card.\n\nFront Desk"],
    },
    "newsletter": {
        "subjects": ["{month} campus newsletter", "This month at the library: {month} picks",
                     "Department digest for {month}"],
        "bodies": ["Hello readers,\n\nWelcome to the {month} edition. Inside: new arrivals in the {course} section, "
                   "extended weekend hours, and the upcoming coding club meetup on {day}.\n\n"
                   "Unsubscribe anytime from your account settings.\n\nLibrary Team",
                   "Hi {name},\n\nHere is your {month} digest: workshop recordings are online, the {course} lab "
                   "schedule is updated, and scholarship applications close soon.\n\nBest,\nCommunications Team"],
    },
    "library": {
        "subjects": ["Reminder: books due next {day}", "Library: {book} due on {day}",
                     "Overdue notice: please return {book}"],
        "bodies": ["Hi {name},\n\nThis is a reminder that '{book}' is due back on {day}. Renew online if no one "
                   "else has reserved it. A small late fee applies after the due date.\n\nCirculation Desk",
                   "Dear {name},\n\nOur records show '{book}' is overdue. Please return it to the front desk this "
                   "week to keep your borrowing privileges active.\n\nThank you,\nLibrary Staff"],
    },
    "appointment": {
        "subjects": ["Appointment confirmation: {place} on {day}", "Your lab slot on {day} is booked",
                     "Service visit scheduled for {day}"],
        "bodies": ["Hi {name},\n\nYour appointment at {place} is confirmed for {day} at {time}. "
                   "Reference ID {tid}. Reschedule at least a day ahead if needed.\n\nRegards,\nScheduling Desk",
                   "Dear {name},\n\nA technician visit for {item} servicing is scheduled on {day} between 10 AM and 1 PM. "
                   "Someone should be present at the premises.\n\nFacilities Team"],
    },
}


def _fill(rng: random.Random, i: int) -> dict:
    return {
        "name": rng.choice(NAMES), "month": rng.choice(MONTHS), "day": rng.choice(DAYS),
        "course": rng.choice(COURSES), "item": rng.choice(ITEMS), "carrier": rng.choice(CARRIERS),
        "amount": f"Rs. {rng.randint(1, 90) * 1000:,}",
        "oid": f"ORD-{rng.randint(10000, 99999)}", "tid": f"TRK{rng.randint(100000, 999999)}",
        "inv": f"INV-{rng.randint(1000, 9999)}", "time": rng.choice(["10:00 AM", "2:30 PM", "4:00 PM"]),
        "room": rng.choice(["A-201", "B-104", "Seminar Hall 2"]),
        "place": rng.choice(["campus health centre", "city clinic", "engineering block office"]),
        "book": rng.choice(["Introduction to Algorithms", "Database System Concepts",
                            "Operating System Concepts", "Pattern Recognition"]),
        "n": i,
    }


def generate(per_category: int = 120, seed: int = 7) -> tuple[pd.DataFrame, dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    for category, tpl in TEMPLATES.items():
        for i in range(per_category):
            ctx = _fill(rng, i)
            subject = rng.choice(tpl["subjects"]).format(**ctx)
            body = rng.choice(tpl["bodies"]).format(**ctx)
            rows.append({"label": "ham", "subject": subject, "body": body, "category": category})
    df = pd.DataFrame(rows, columns=["label", "subject", "body", "category"])
    before = len(df)
    df = df.drop_duplicates(subset=["label", "subject", "body"], keep="first").reset_index(drop=True)
    blob = "|".join(sorted(tpl["subjects"][0] + tpl["bodies"][0] for tpl in TEMPLATES.values()))
    manifest = {
        "generator": GENERATOR_VERSION,
        "warning": "TEMPLATE-GENERATED. Not genuine mail. Dev aid only.",
        "seed": seed, "per_category_requested": per_category,
        "rows_generated": before, "rows_after_dedupe": int(len(df)),
        "per_category": df["category"].value_counts().to_dict(),
        "template_fingerprint_sha1": hashlib.sha1(blob.encode()).hexdigest()[:12],
    }
    return df, manifest


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Generate clearly-labeled synthetic ham (dev aid only).")
    p.add_argument("--per-category", type=int, default=120)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out-csv", default=str(OUT_CSV))
    p.add_argument("--manifest", default=str(OUT_MANIFEST))
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    df, manifest = generate(a.per_category, a.seed)
    out_csv = pathlib.Path(a.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    mp = pathlib.Path(a.manifest)
    mp.parent.mkdir(parents=True, exist_ok=True)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"synthetic ham: {len(df)} rows -> {out_csv} (manifest: {mp})")
    print(f"per-category: {manifest['per_category']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
