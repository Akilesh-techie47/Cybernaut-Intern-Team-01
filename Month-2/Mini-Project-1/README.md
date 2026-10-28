# Email Spam Classifier (SMS/Message Prototype)

A lightweight Streamlit website that classifies a pasted email/message as
**SPAM** or **HAM (likely legitimate)** using a scikit-learn TF-IDF + classifier
pipeline trained on the UCI SMS Spam Collection.

> Honest scope: this is an **SMS/message spam prototype**. It is presented as a
> prototype for email spam classification (per the brief) but it has **not** been
> validated on real email bodies/headers. The UI, dataset notes, and report state
> this explicitly.

## Features

- Paste-a-message → **SPAM** / **HAM** prediction from a saved pipeline (no retraining at request time)
- Input validation (empty, whitespace-only, >10,000 chars), character counter, Clear button
- 5 one-click example messages (spam, ham, and a tricky ham containing "free")
- Loading indicator, friendly errors (including missing-model guidance), no stack traces in UI
- Model-details section showing the **actual** selected model and measured test metrics
- Probability shown **only** when the selected estimator supports `predict_proba`
  (the selected LinearSVC does not → class-only display, by design)
- Evaluation artifacts: metrics JSON/CSV + plots (label distribution, model
  comparison, per-model confusion matrices, top spam terms)
- 13 automated pytest tests; reproducible stratified split (`random_state=42`)

## Architecture / project tree

```
.
├── app.py                        # Streamlit website (streamlit run app.py)
├── requirements.txt
├── runtime.txt                   # python-3.11 (Streamlit Cloud)
├── .streamlit/config.toml
├── data/
│   ├── README.md                 # source, license, schema, setup
│   └── raw/                      # local dataset (git-ignored): SMSSpamCollection
├── models/
│   ├── spam_classifier_pipeline.joblib  # selected fitted Pipeline (TF-IDF + clf)
│   └── metadata.json             # model type, dataset, timestamp, metrics
├── reports/
│   ├── figures/                  # *.png generated from actual data/results
│   ├── metrics/                  # metrics.json, model_comparison.csv
│   └── PROJECT_REPORT.md
├── src/spam_classifier/
│   ├── __init__.py
│   ├── data.py                   # loading, schema checks, validation
│   ├── preprocessing.py          # label/text validation
│   ├── train.py                  # split, train 3 models, compare, save
│   ├── evaluate.py               # metrics + plots (spam = positive)
│   └── predict.py                # trusted-artifact loading + prediction
└── tests/
    ├── test_data.py
    ├── test_pipeline.py
    └── test_predict.py
```

## Dataset

- **Used:** UCI SMS Spam Collection v.1 — 5,574 messages (after de-dup: 5,160 kept,
  414 duplicates removed; ham 4,518 / spam 642).
- **Source (verified):** https://archive.ics.uci.edu/dataset/228/sms+spam+collection
- **License:** free for research per the dataset readme (`data/raw/README_UCI_ORIGINAL.txt`).
  Raw data is git-ignored; see `data/README.md`.
- **Schema:** TSV, no header, `<ham|spam>\t<message>`. Loader normalizes to
  canonical `text` / `label` (`spam`/`ham`) and reports rows/missing/duplicates/label counts.
- **Place the dataset:** save the file as `data/raw/SMSSpamCollection` (see `data/README.md`
  for the exact download commands). A Kaggle CSV mirror with `v1,v2` columns is
  also auto-detected if present.

## Setup

Windows PowerShell:

```powershell
python --version            # 3.11+ recommended (3.13 works locally)
pip install -r requirements.txt
```

Command Prompt (cmd) uses the same commands without the `$env:` prefix.

Set the import path when running training/tests (Streamlit app handles this itself):

```powershell
$env:PYTHONPATH = "src"
```

## Training and evaluation

```powershell
$env:PYTHONPATH = "src"
python -m spam_classifier.train --data data/raw/SMSSpamCollection
# or: python src/spam_classifier/train.py --data data/raw/SMSSpamCollection
```

What it does: stratified 80/20 split (`random_state=42`), TF-IDF
(`max_features=5000`, `ngram_range=(1,2)`) **inside** each Pipeline (vocabulary fit
on train only), trains MultinomialNB / LogisticRegression / LinearSVC on the same
split, evaluates on the held-out test set (spam = positive), selects best by spam
F1 (tie-break: spam precision), saves the full pipeline + metadata, verifies a
fresh `joblib.load` + predict round-trip.

Artifacts:

- `models/spam_classifier_pipeline.joblib`, `models/metadata.json`
- `reports/metrics/metrics.json`, `reports/metrics/model_comparison.csv`
- `reports/figures/label_distribution.png`, `model_comparison.png`,
  `confusion_matrix_{naive_bayes,logistic_regression,svm}.png`, `top_spam_terms.png`

## Actual measured results (held-out test, n=1032, seed 42)

| model | accuracy | spam precision | spam recall | spam F1 | confusion [[TN,FP],[FN,TP]] |
|---|---|---|---|---|---|
| naive_bayes | 0.9738 | 1.0000 | 0.7891 | 0.8821 | [[904,0],[27,101]] |
| logistic_regression | 0.9661 | 0.9895 | 0.7344 | 0.8430 | [[903,1],[34,94]] |
| **svm (LinearSVC, selected)** | **0.9893** | **0.9916** | **0.9219** | **0.9555** | **[[903,1],[10,118]]** |

Selected **svm** (highest spam F1; also best recall at ~equal precision → lowest
false-negative rate among candidates with 1 false positive). `LinearSVC` has no
`predict_proba`, so the app shows class-only results (no fake confidence %).

## Launch the website locally

```powershell
streamlit run app.py
```

Then open the shown URL (usually http://localhost:8501) and test one ham and one
spam example. If the model file is missing the app shows how to train it.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m compileall -q .
```

Covers: missing dataset file, unexpected columns/labels, missing values, label
normalization, empty/whitespace input, valid input → spam/ham only, vocab-fit
leak safety, save/load round-trip, missing-artifact error, metrics/confusion
shape, long-input validation.

## Hosting / deployment (Streamlit Community Cloud)

1. Push this folder to a public GitHub repo; confirm `app.py`, `requirements.txt`,
   `runtime.txt`, `.streamlit/config.toml`, `models/spam_classifier_pipeline.joblib`,
   and `models/metadata.json` are included (model is ~227 KB — fine for GitHub).
   Do **not** commit `data/raw/` (git-ignored).
2. Sign in at https://share.streamlit.io → New app → pick repo/branch → main file `app.py`.
3. Deploy, wait for build logs, open the public URL, test one ham + one spam message.
4. If the build fails, check logs for Python-version or package issues (see below).

Troubleshooting:

- Missing model file → app shows training command; ensure the `.joblib` was committed.
- Python version → `runtime.txt` pins 3.11; keep `requirements.txt` lower bounds compatible.
- Package build failure → check Streamlit build logs; loosen/upper-bound pins if needed.
- Wrong paths → all paths are relative to the project root; no absolute Windows paths.

Status: **deployment-ready, tested locally; not yet publicly live** (no hosting
credentials were available in this environment, so no live URL is claimed).

## Limitations

- Trained on short SMS-style texts (~13% spam after dedup); **not validated** on real
  email bodies, headers, HTML, attachments, or sender behavior (none used).
- TF-IDF + linear models only; no phishing/URL-reputation analysis; tie-breaking
  favors precision but ham predictions still do **not** guarantee safety.
- English-language bias inherited from the dataset.

## Privacy and safe use

- Message text is treated as **untrusted input**: links are never opened, content
  never executed, attachments not processed.
- Nothing is logged or stored by default; predictions happen in memory.
- Educational prototype — not an enterprise gateway or phishing guarantee. If
  hosted publicly, input is processed by the hosted app.

## Future improvements

- Email-specific dataset (e.g. SpamAssassin/Enron-style with headers) + header features
- Calibrated probabilities (CalibratedClassifierCV) or an explicitly probabilistic model
- Cross-validation + threshold tuning for precision/recall trade-off
- Phishing/URL analysis, multilingual data, feedback loop with human review
