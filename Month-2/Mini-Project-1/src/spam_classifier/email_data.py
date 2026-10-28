"""Build email-native training CSV from the SpamAssassin public corpus.

Source: https://spamassassin.apache.org/old/publiccorpus/ (research use;
addresses already obfuscated by the curators; never send these into a live
mail system — this script only reads them offline for training).

Input layout: data/raw/sa_corpus/<set>/.../<nnn> plain RFC-822 files, where
<set> names containing 'spam' are spam and those with 'ham' are ham.
(easy_ham, easy_ham_2, hard_ham -> ham; spam, spam_2, 20050311_spam_2 -> spam.)

Output: CSV with label,subject,body (the format the email site consumes).
Body = concatenated text/plain MIME parts, attachments skipped, whitespace
collapsed. Combined subject+body capped at MAX_CHARS (same 10,000 limit the
website enforces) so train and serve distributions agree.

Usage (from project root):
    $env:PYTHONPATH = "src"
    python -m spam_classifier.email_data
"""

from __future__ import annotations

import argparse
import email
import email.header
import email.policy
import pathlib
import re
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pandas as pd  # noqa: E402

from spam_classifier.predict import MAX_INPUT_CHARS  # noqa: E402

CORPUS_DIR = PROJECT_ROOT / "data" / "raw" / "sa_corpus"
OUT_CSV = PROJECT_ROOT / "data" / "raw" / "email_spam_ham.csv"
WS = re.compile(r"\s+")


def decode_header(value: object) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(str(value))
    out = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            try:
                out.append(chunk.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeError):
                out.append(chunk.decode("utf-8", errors="replace"))
        else:
            out.append(chunk)
    return WS.sub(" ", "".join(out)).strip()


def extract_body(msg: email.message.Message) -> str:
    chunks: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() != "text/plain":
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                chunks.append(payload.decode(charset, errors="replace"))
            except (LookupError, UnicodeError):
                chunks.append(payload.decode("utf-8", errors="replace"))
    else:
        if msg.get_content_type().startswith("text/"):
            try:
                payload = msg.get_payload(decode=True)
            except Exception:
                payload = None
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    chunks.append(payload.decode(charset, errors="replace"))
                except (LookupError, UnicodeError):
                    chunks.append(payload.decode("utf-8", errors="replace"))
            elif isinstance(msg.get_payload(), str):
                chunks.append(msg.get_payload())
    return WS.sub(" ", " ".join(chunks)).strip()


def build_csv(corpus_dir: pathlib.Path | None = None,
              out_csv: pathlib.Path | None = None) -> dict:
    corpus_dir = pathlib.Path(corpus_dir or CORPUS_DIR)
    out_csv = pathlib.Path(out_csv or OUT_CSV)
    rows: list[dict] = []
    skipped = {"non_email": 0, "empty": 0}
    per_set: dict[str, int] = {}
    for path in sorted(corpus_dir.rglob("*")):
        if not path.is_file():
            continue
        set_name = path.relative_to(corpus_dir).parts[0]
        lname = set_name.lower()
        if "spam" in lname:
            label = "spam"
        elif "ham" in lname:
            label = "ham"
        else:
            skipped["non_email"] += 1
            continue
        try:
            raw = path.read_bytes()
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            subject = decode_header(msg.get("Subject", ""))
            body = extract_body(msg)
        except Exception:
            skipped["non_email"] += 1
            continue
        if not body and not subject:
            skipped["empty"] += 1
            continue
        combined_len = len(subject) + len(body)
        truncated = False
        if combined_len > MAX_INPUT_CHARS:
            body = body[: max(0, MAX_INPUT_CHARS - len(subject))]
            truncated = True
        rows.append({"label": label, "subject": subject, "body": body,
                     "set": set_name, "truncated": truncated})
        per_set[set_name] = per_set.get(set_name, 0) + 1

    df = pd.DataFrame(rows, columns=["label", "subject", "body", "set", "truncated"])
    before = len(df)
    df = df.drop_duplicates(subset=["label", "subject", "body"], keep="first").reset_index(drop=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df[["label", "subject", "body"]].to_csv(out_csv, index=False)
    stats = {
        "parsed": before, "kept": len(df), "exact_duplicates": before - len(df),
        "label_counts": df["label"].value_counts().to_dict(),
        "per_set": per_set, "skipped": skipped,
        "truncated_to_site_limit": int(df["truncated"].sum()),
        "out_csv": str(out_csv),
    }
    print(f"parsed={before} kept={len(df)} dups={before - len(df)} "
          f"labels={stats['label_counts']} truncated={stats['truncated_to_site_limit']}")
    print(f"per_set={per_set} skipped={skipped}")
    print(f"wrote {out_csv}")
    return stats


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Build email training CSV from SpamAssassin corpus.")
    p.add_argument("--corpus-dir", default=str(CORPUS_DIR))
    p.add_argument("--out-csv", default=str(OUT_CSV))
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    build_csv(pathlib.Path(a.corpus_dir), pathlib.Path(a.out_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
