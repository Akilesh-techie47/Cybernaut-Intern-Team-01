# PhishShift Message Risk Scanner

## ML-07 PhishShift: Message Risk Scanner — Cybernaut EdTech Student Project

### Overview

PhishShift is a reproducible, evidence-based cybersecurity NLP prototype for phishing message detection and risk scoring. It implements the ML-07 requirements from the Cybernaut EdTech student project, providing an explainable, campaign-separated evaluation of phishing detection models.

### Core Features

- **FR-01**: Near-duplicate message template removal before train/valid/test partition creation, preventing duplicate/campaign leakage across partitions
- **FR-02**: Three-model comparison:
  1. **Rules-based baseline** — explainable, feature-weight transparency
  2. **TF-IDF + Logistic Regression** — linear classifier with feature importance
  3. **Naive Bayes + TF-IDF** — probabilistic model with feature contributions
- **FR-03**: Campaign-separated holdout evaluation — no campaign group appears in both training and testing
- **FR-04**: Explicit reject/abstain outcome for uncertain predictions (probability margin < 0.15)
- **FR-05**: False-positive rate measurement on legitimate urgent messages + robustness to wording/punctuation/URL variations

### Dataset

- **Size:** 555 messages (500 phishing + 55 legitimate)
- **Schema:** message_id, channel, subject_or_title, body_text, sanitized_url_features, sender_domain_type, label, campaign_group, collected_date
- **Source:** Synthetic, locally generated — no external data collection, no real credentials, no personal information
- **Campaign groups:** 16 categories covering payroll, tax, delivery, bank, password, invoice, social engineering, tech support, IRS, HR, gift cards, and more
- **Near-duplicate removal:** 458 duplicates removed, 97 messages kept for partition creation
- **Campaign splitting:** 11 campaigns for training, 2 for validation, 4 for testing — zero leakage between splits

### Safety

- All URLs are kept defanged (hxxp://, [.] format) in the interface and evaluation pipeline
- No real credentials, mailbox dumps, or personal information collected or displayed
- Incoming message text is treated as untrusted data, never as executable instructions
- Display disclaimer: results are decision support, not a guarantee of safety
- Safe message scanning with explicit abstain/reject for uncertain predictions

### Warning

**This tool provides decision support only. Results are not a guarantee of safety. Always verify suspicious communications through official channels. Never enter real credentials or sensitive information into this interface.**

### Repository Structure

```
phishshift/
├── data/                    # Dataset files (raw, processed, partitions)
├── src/                     # Source code
│   ├── generate_dataset.py   # Dataset generation (500 phishing + 55 legitimate)
│   ├── near_duplicates.py    # Near-duplicate removal (FR-01)
│   ├── rules_baseline.py     # Rules-based classifier (FR-02 #1)
│   ├── tfidf_classifier.py   # TF-IDF + Logistic Regression (FR-02 #2)
│   ├── naive_bayes.py        # Naive Bayes + TF-IDF (FR-02 #3)
│   ├── model_comparison.py   # Model comparison table
│   └── streamlit_ui.py       # Web UI for message scanning
├── tests/                   # Test suite
│   └── acceptance_tests.py   # AT-01, AT-02, AT-03 acceptance tests
├── scripts/                 # Helper scripts
├── docs/                    # Documentation
└── README.md               # This file
```

### Requirements

See `requirements.txt` for dependency versions.

### Installation

```bash
# Create conda environment (recommended)
conda env create -f environment.yml

# Or install dependencies manually
pip install -r requirements.txt
```

### Running the Web UI

```bash
streamlit run phishshift/src/streamlit_ui.py
```

The interface will be available at `http://localhost:8501`.

### Running Acceptance Tests

```bash
python -m pytest phishshift/tests/acceptance_tests.py -v
```

### Running the Model Comparison

```bash
python phishshift/src/model_comparison.py
```