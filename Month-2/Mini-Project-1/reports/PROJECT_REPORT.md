# Project Report — Email Spam Classifier (SMS/Message Prototype)

## 1. Problem statement

Spam messages flood inboxes with irrelevant or malicious content. This project
builds a machine-learning prototype that distinguishes **spam** from **ham
(legitimate)** by analyzing message text, with a real training pipeline,
evaluation, and a usable web interface for real-time classification.

## 2. Objectives

- Load and validate a labeled spam/ham dataset with a documented schema.
- Build a leakage-safe TF-IDF + classifier pipeline; compare Naive Bayes,
  Logistic Regression, and Linear SVM on the same held-out split.
- Select the final model on measured test results (spam F1, precision/recall trade-off).
- Serve real predictions through a polished, responsive, accessible Streamlit website.
- Provide tests, metrics, visualizations, docs, and hosting instructions.

## 3. Methodology

1. **Data:** UCI SMS Spam Collection (`data/raw/SMSSpamCollection`), normalized to
   canonical `text`/`label` (`spam`/`ham`); invalid rows removed, duplicates
   de-duplicated; stratified 80/20 split, `random_state=42`.
2. **Features:** `TfidfVectorizer(max_features=5000, ngram_range=(1,2), lowercase=True)`
   **inside** each scikit-learn `Pipeline` (vocabulary fit on train only — no leakage).
3. **Models:** `MultinomialNB`, `LogisticRegression(max_iter=1000)`, `LinearSVC` —
   each as `Pipeline(TFIDF → classifier)`.
4. **Evaluation (spam = positive):** accuracy, spam precision/recall/F1, confusion
   matrix; selection by best spam F1, tie-break by spam precision (low false positives).
5. **Serving:** single saved pipeline (`models/spam_classifier_pipeline.joblib`) +
   `metadata.json`; Streamlit app loads the artifact, validates input, never retrains
   per request; class-only display because LinearSVC has no calibrated probabilities.

## 4. Dataset

- UCI SMS Spam Collection v.1 (Almeida et al., ACM DOCENG'11).
- Source: https://archive.ics.uci.edu/dataset/228/sms+spam+collection
- Raw: 5,574 rows, TSV no-header `ham|spam \t message`, UTF-8.
- Cleaned: **5,160 kept** (414 exact `(label,text)` duplicates removed),
  **ham 4,518 / spam 642**; 0 missing/unknown after validation.
- License: free for research (see `data/raw/README_UCI_ORIGINAL.txt`, `data/README.md`).
- Scope honesty: SMS-style short messages; **not** validated on email bodies/headers.

## 5. Models

- TF-IDF (1,2)-grams, 5k features, lowercase; no external NLP downloads (NLTK/spaCy
  not needed — deliberately avoided as extra weight without demonstrated benefit).
- Candidates: Multinomial Naive Bayes / Logistic Regression / Linear SVM (`LinearSVC`).

## 6. Evaluation results (held-out test, n=1032)

| model | accuracy | spam precision | spam recall | spam F1 | confusion [[TN,FP],[FN,TP]] |
|---|---|---|---|---|---|
| naive_bayes | 0.9738 | 1.0000 | 0.7891 | 0.8821 | [[904,0],[27,101]] |
| logistic_regression | 0.9661 | 0.9895 | 0.7344 | 0.8430 | [[903,1],[34,94]] |
| **svm (selected)** | **0.9893** | **0.9916** | **0.9219** | **0.9555** | **[[903,1],[10,118]]** |

Selected **LinearSVC**: highest spam F1 (0.9555), highest recall (0.9219) with only
1 false positive — best false-positive/false-negative trade-off on this split.
NB had perfect precision but missed 27/128 spams (recall 0.789).

Manual spot checks (saved pipeline, fresh process): prize-scam → spam; meeting
details → ham; tricky "Feel free to call me…" → ham (no naive keyword false positive).

## 7. Figures (in `reports/figures/`, all from actual data/results)

- `label_distribution.png` — ham vs spam counts (cleaned dataset).
- `model_comparison.png` — accuracy / spam precision / recall / F1 per model.
- `confusion_matrix_{naive_bayes,logistic_regression,svm}.png` — per-model test confusion.
- `top_spam_terms.png` — top 20 spam-indicative terms from the selected model.
- (No app screenshots are included — none were captured in this environment.)

## 8. Limitations

- SMS-length, English-biased, ~13% spam; not tested on email headers/HTML/attachments.
- Linear bag-of-ngrams only; no sender/URL reputation, no phishing-specific signals.
- Single 80/20 split (no CV tuning, to avoid test-set overfitting per spec).
- LinearSVC outputs uncalibrated scores → no probability % shown (by design).
- Ham ≠ safe: always verify unexpected links/requests.

## 9. Conclusion

All three pipelines trained leak-free; measured comparison selected LinearSVC
(accuracy 0.989, spam F1 0.955) with a verified save→reload→predict round-trip.
The Streamlit site serves real predictions with validation, examples, measured
model details, and safe-use wording; 13/13 tests pass and the app health-checks
HTTP 200 locally. The project is deployment-ready for Streamlit Community Cloud.

## 10. Future scope

- Email-native data (headers, HTML, attachments metadata) + sender features.
- Calibrated probabilities, threshold tuning, cross-validation.
- Phishing/scam/ad sub-types, multilingual support, feedback-driven retraining.
- Monitoring, rate limiting, and abuse controls for public hosting.
