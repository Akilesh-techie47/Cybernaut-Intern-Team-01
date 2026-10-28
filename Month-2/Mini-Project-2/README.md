# 🛡️ PhishShift: Message Risk Scanner

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B.svg)](https://streamlit.io/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4%2B-F7931E.svg)](https://scikit-learn.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Acceptance%20Tests-3%20Passed-22c55e.svg)](phishshift/tests/acceptance_tests.py)

**ML-07 PhishShift** is a reproducible, evidence-based cybersecurity NLP prototype designed for phishing message detection, risk scoring, and campaign-isolated evaluation. It was developed in compliance with the ML-07 specification from the Cybernaut EdTech student project curriculum.

---

## 🚀 Live Hosting & Deployment

This project is structured for immediate 1-click deployment on modern cloud platforms:

### 1. Streamlit Community Cloud (Recommended & Free)
1. Fork or push this repository to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io/).
3. Click **"New app"**, select your repository, branch (`main`), and set **Main file path** to:
   ```text
   app.py
   ```
4. Click **Deploy!** Your app will be live with HTTPS in ~1 minute.

### 2. Hugging Face Spaces
1. Create a new Space on [Hugging Face Spaces](https://huggingface.co/spaces).
2. Select **Streamlit** as the Space SDK.
3. Push this repository to your Space. The root `app.py` and `requirements.txt` will automatically launch the application.

### 3. Docker Container
Build and run the multi-platform container locally or deploy to AWS ECS, Google Cloud Run, or Azure Container Apps:
```bash
# Build Docker image
docker build -t phishshift .

# Run container on port 8501
docker run -p 8501:8501 phishshift
```
Open `http://localhost:8501` in your browser.

### 4. Render / Railway / Heroku
The included `Procfile` configures the web dyno automatically:
```text
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

---

## 💻 Local Quickstart

### Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Git (optional)

### Installation
```bash
# Clone the repository
git clone https://github.com/your-username/phishshift.git
cd phishshift

# Install dependencies
pip install -r requirements.txt
```

### Launch the Application
- **Windows Double-Click**: Double-click `run.bat` or run `./run.ps1` in PowerShell.
- **Terminal (any OS)**:
  ```bash
  streamlit run app.py
  ```

---

## 🎯 Core Engineering Features

| Requirement | Description | Status |
| :--- | :--- | :--- |
| **FR-01** | Near-duplicate message template de-biasing before partition creation, preventing duplicate/campaign leakage across splits. | ✅ Verified |
| **FR-02** | Three-model comparison: Rules-based baseline, TF-IDF + Logistic Regression, and Multinomial Naive Bayes. | ✅ Verified |
| **FR-03** | Campaign-separated holdout partitions — zero campaign group overlap between training, validation, and testing sets. | ✅ Verified |
| **FR-04** | Explicit **Abstain / Reject** decision when probability margin $|p - 0.5| < 0.15$ for uncertain messages. | ✅ Verified |
| **FR-05** | False-positive mitigation on legitimate urgent messages + robustness to defanged URLs (`hxxp://`, `[.]`) and casing. | ✅ Verified |

---

## 🧪 Acceptance Test Suite

Run the full acceptance test suite:
```bash
python -m pytest phishshift/tests/acceptance_tests.py -v
```
All 3 acceptance tests pass cleanly:
- `AT-01`: Legitimate urgent password-reset notifications false-positive evaluation.
- `AT-02`: Phishing with unfamiliar wording assessed on excluded campaigns.
- `AT-03`: Defanged URL and punctuation robustness checks.

---

## 📁 Repository Structure

```text
├── .streamlit/
│   └── config.toml          # Modern theme and server configuration
├── docs/
│   ├── ML-07_PhishShift_Message_Risk_Scanner_View_Only.pdf # Specification PDF
│   └── requirements_traceability_matrix.csv # Traceability matrix
├── phishshift/
│   ├── data/                 # Datasets (raw, processed, train/valid/test)
│   ├── docs/                 # Project documentation
│   ├── scripts/              # Helper scripts
│   ├── src/                  # Core model algorithms and Streamlit interface
│   └── tests/                # Acceptance test suite (AT-01 to AT-03)
├── app.py                    # Production entrypoint for hosting
├── Dockerfile                # Production container specification
├── Procfile                  # Render / Railway process file
├── requirements.txt          # Python dependencies
├── run.bat                   # 1-click Windows launcher
├── run.ps1                   # 1-click PowerShell launcher
├── .gitignore                # Clean Git tracking
└── README.md                 # Project documentation
```

---

## ⚠️ Security Notice & Disclaimer

**This tool provides educational decision support.** Incoming messages are treated as untrusted data. Models generate advisory risk probabilities and do not execute embedded scripts or connect to external URLs. Always verify critical alerts directly through official, verified communication channels.
