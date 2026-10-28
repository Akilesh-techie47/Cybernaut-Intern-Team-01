# Dataset

## Used dataset: UCI SMS Spam Collection v.1

- **Source (verified):** https://archive.ics.uci.edu/dataset/228/sms+spam+collection
  (downloaded as `sms+spam+collection.zip`, SHA varies by mirror; local copy
  extracted to `data/raw/SMSSpamCollection`).
- **Paper:** Almeida, T.A., Gómez Hidalgo, J.M., Yamakami, A. Contributions to the
  study of SMS Spam Filtering: New Collection and Results. ACM DOCENG'11.
- **License/terms:** Free for research use per the dataset readme
  (`data/raw/README_UCI_ORIGINAL.txt`). Do not redistribute beyond fair research use;
  the raw file is git-ignored by default.
- **Size:** 5,574 messages — ~4,827 ham (86.6%), ~747 spam (13.4%).
- **Format:** TSV, no header, one message per line: `<ham|spam>\t<message>`.
  Encoding is UTF-8 (latin-1 accepted as fallback by the loader).

## Honest scope note

This is an **SMS/message spam prototype**, not a validated email-body classifier.
It has not been validated on real email headers, HTML bodies, or attachments.
The UI and report state this explicitly.

## Setup

1. The file `data/raw/SMSSpamCollection` should already exist if you ran the
   provided download step. If not, download it:
   ```powershell
   curl.exe -L -o data/raw/SMSSpamCollection.zip "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
   Expand-Archive data/raw/SMSSpamCollection.zip -DestinationPath data/raw/uci_tmp -Force
   Copy-Item data/raw/uci_tmp/SMSSpamCollection data/raw/SMSSpamCollection -Force
   ```
2. Train:
   ```powershell
   python -m spam_classifier.train
   ```
3. Alternative Kaggle mirror (same collection, CSV with `v1,v2` columns, requires
   Kaggle login): https://www.kaggle.com/datasets/uciml/sms-spam-collection-dataset
   The loader auto-detects `v1/v2` and `label/message` headers.

## Canonical schema

Loader output (`src/spam_classifier/data.py::load_dataset`):
- `text`: stripped message string (non-empty)
- `label`: `spam` or `ham` (normalized; `1/0`, `true/false` mapped where present)

Invalid rows (missing/unknown label, empty text) are removed and counted in the
training report. Duplicates `(label, text)` are de-duplicated (first kept).
