"""Email Spam Classifier — Streamlit website.

Run locally:  streamlit run app.py

Predictions come from the saved pipeline in models/spam_classifier_pipeline.joblib.
The app never retrains at request time and never stores submitted messages.
"""

from __future__ import annotations

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import streamlit as st  # noqa: E402

from spam_classifier.predict import (  # noqa: E402
    MAX_INPUT_CHARS,
    ModelNotTrainedError,
    get_model,
    load_metadata,
    predict_spam_ham,
)

st.set_page_config(
    page_title="Email Spam Classifier",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------- Theme: minimal dark/light palette ----------
THEME_COLOR = "#1a73e8"
THEME_BG_LIGHT = "#f8f9fa"
THEME_BG_DARK = "#202328"
THEME_CARD = "#ffffff"
THEME_TEXT = "#202118"
THEME_MUTED = "#5f6368"

st.markdown(
    f"""
    <style>
      :root {{
        --theme-color: {THEME_COLOR};
        --theme-bg-light: {THEME_BG_LIGHT};
        --theme-bg-dark: {THEME_BG_DARK};
        --theme-card: {THEME_CARD};
        --theme-text: {THEME_TEXT};
        --theme-muted: {THEME_MUTED};
      }}
      .block-container {{
        max-width: 800px;
        padding-top: 2rem;
        padding-bottom: 2rem;
        color: var(--theme-text);
      }}
      h1, h2, h3 {{
        color: var(--theme-color);
      }}
      .stButton > button {{
        width: 100%;
        border-radius: 8px;
        border: 1px solid var(--theme-color);
        background: var(--theme-color);
        color: #fff;
        font-weight: 600;
        padding: 0.6rem 1rem;
        font-size: 1rem;
      }}
      .stButton > button:hover {{
        background: #1557b0;
        border-color: #1557b0;
      }}
      .stTextArea > textarea {{
        border-radius: 8px;
        border: 1px solid #aaa;
        font-size: 1rem;
        padding: 0.75rem;
      }}
      .stTextArea > textarea:focus {{
        border-color: var(--theme-color);
        box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.15);
      }}
      .result-box {{
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin: 1rem 0;
        border: 2px solid;
        font-size: 1.1rem;
        line-height: 1.4;
      }}
      .result-spam {{
        border-color: #b3261e;
        background: #fdecea;
        color: #410e0b;
      }}
      .result-ham {{
        border-color: #146c2e;
        background: #e6f4ea;
        color: #0d3b1e;
      }}
      .result-title {{
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 0.01em;
        margin-bottom: 0.25rem;
      }}
      .muted {{
        color: var(--theme-muted);
        font-size: 0.85rem;
      }}
      .stTabs [data-baseweb="tab"] {{
        font-weight: 500;
      }}
      .stSpinner > div:first-child {{
        border-color: var(--theme-color) !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------- Example messages (spam / ham) ----------
EXAMPLES = {
    "Spam — prize scam": "Congratulations! You have WON a FREE cash prize of $1000. Claim now by calling 09061701461. Valid 12 hours only!",
    "Spam — urgent link": "URGENT! Your account requires verification. Click http://example-prize-claim.tk/verify now or it will be suspended.",
    "Ham — meeting": "Hey, can you send me the meeting details? I'll reach college at 9 AM tomorrow.",
    "Ham — order update": "Your Amazon order has been shipped and will arrive Thursday. Track it in your account.",
    "Tricky ham (contains 'free')": "Feel free to call me after the meeting to discuss the assignment.",
}

# -------- Session state initialisation ----
for key in ("message", "result", "proba", "error"):
    if key not in st.session_state:
        st.session_state[key] = None if key != "message" else ""


def _load_example(name: str):
    st.session_state.message = EXAMPLES[name]
    st.session_state.result = None
    st.session_state.proba = None
    st.session_state.error = None


def _clear():
    st.session_state.message = ""
    st.session_state.result = None
    st.session_state.proba = None
    st.session_state.error = None


# -------- Header / Hero ----
st.title("📧 Email Spam Classifier")
st.caption(
    "Paste an email or message below to get an automated **Spam** or "
    "**Ham (likely legitimate)** estimate. This is an educational prototype "
    "trained on SMS‑style messages — predictions are estimates, not guarantees."
)

# -------- Input panel ----
st.subheader("1. Enter a message")

col_input, col_actions = st.columns([1, 0.5], gap="small")
with col_input:
    msg = st.text_area(
        "Message text",
        key="message",
        height=120,
        max_chars=MAX_INPUT_CHARS,
        help=f"Paste the message text. Limit: {MAX_INPUT_CHARS:,} characters. Links are never opened or clicked.",
        placeholder="e.g. Congratulations! You've won a free prize. Claim now...",
    )
n_chars = len(st.session_state.message or "")
st.caption(f"{n_chars:,} / {MAX_INPUT_CHARS:,} characters")
if n_chars > MAX_INPUT_CHARS:
    st.warning(
        f"Message is too long ({n_chars:,} characters; limit {MAX_INPUT_CHARS:,}). "
        "Please shorten it before classifying."
    )

with col_actions:
    classify_clicked = st.button("🔍 Classify", type="primary", use_container_width=True)
    st.button("🧹 Clear", use_container_width=True, on_click=_clear)

st.write("Load an example:")
ex_cols = st.columns(3)
for i, name in enumerate(EXAMPLES):
    with ex_cols[i % 3]:
        st.button(f"Load: {name}", key=f"ex_{name}", use_container_width=True,
                  on_click=_load_example, args=(name,))

# -------- Classify ----
if classify_clicked:
    st.session_state.result = None
    st.session_state.proba = None
    st.session_state.error = None
    text = (st.session_state.message or "").strip()
    if not text:
        st.session_state.error = "Please enter a message to classify — the input was empty."
    elif len(text) > MAX_INPUT_CHARS:
        st.session_state.error = (
            f"Message is too long ({len(text):,} characters; limit {MAX_INPUT_CHARS:,}). "
            "Please shorten it and try again."
        )
    else:
        try:
            with st.spinner("Analyzing message…"):
                get_model()  # surfaces missing-model error early
                label, proba = predict_spam_ham(text)
            st.session_state.result = label
            st.session_state.proba = proba
        except ModelNotTrainedError as e:
            st.session_state.error = (
                f"Model is not available. {e}\n\n"
                "To train locally run: `python -m spam_classifier.train`"
            )
        except ValueError as e:
            st.session_state.error = str(e)
        except Exception:  # noqa: BLE001 — never expose internals
            st.session_state.error = (
                "Something went wrong while classifying. Please try again with different text."
            )

if st.session_state.error:
    st.error(st.session_state.error)

# -------- Result panel ----
if st.session_state.result in ("spam", "ham"):
    st.subheader("2. Result")
    label = st.session_state.result
    proba = st.session_state.proba

    # Determine spam probability if available
    spam_pct = None
    ham_pct = None
    if proba and "spam" in proba and "ham" in proba:
        spam_pct = proba["spam"] * 100
        ham_pct = proba["ham"] * 100

    if label == "spam":
        st.markdown(
            f'<div class="result-box result-spam" role="status" aria-live="polite">'
            f'<div class="result-title">🚨 SPAM — likely unsolicited</div>'
            f'<div><strong>This looks like spam.</strong> Do not click links, call numbers, or share '
            f'personal details. Delete or report it.</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="result-box result-ham" role="status" aria-live="polite">'
            f'<div class="result-title">✅ HAM — likely legitimate</div>'
            f'<div><strong>Predicted ham / likely legitimate.</strong> Still verify unexpected '
            f'links and requests before acting. A ham prediction does not guarantee safety.</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # Probability line (only when model supports it)
    if spam_pct is not None and ham_pct is not None:
        st.write(
            f"Model score — spam: **{spam_pct:.1f}%**, ham: **{ham_pct:.1f}%** "
            f"(model estimate only, not a guarantee)."
        )
    else:
        st.caption(
            "No probability shown: the selected model does not produce calibrated "
            "probabilities, so only the class prediction is displayed."
        )

# -------- Model details ----
with st.expander("3. Model details", expanded=False):
    meta = load_metadata()
    metrics_path = PROJECT_ROOT / "reports" / "metrics" / "metrics.json"
    metrics = {}
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            metrics = {}

    if meta:
        st.write(f"**Selected model:** `{meta.get('model_name', '?')}` "
                 f"({meta.get('model_class', '?')})")
        st.write(f"**Dataset:** SMS Spam Collection v.1 (SMS/message prototype — "
                 f"not validated on full email bodies/headers). "
                 f"Rows kept: {meta.get('data_report', {}).get('kept_rows', '?')}.")
        tm = meta.get("test_metrics", {})
        if tm:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Accuracy", f"{tm.get('accuracy', 0):.3f}")
            c2.metric("Spam precision", f"{tm.get('spam_precision', 0):.3f}")
            c3.metric("Spam recall", f"{tm.get('spam_recall', 0):.3f}")
            c4.metric("Spam F1", f"{tm.get('spam_f1', 0):.3f}")
            st.caption(
                f"Test size: {tm.get('n_test', '?')} · spam = positive class · "
                f"confusion [[TN, FP], [FN, TP]] = {tm.get('confusion_matrix', '?')}"
            )
            supports_proba = meta.get("supports_predict_proba", False)
            st.caption(
                f"Calibrated probabilities: {'yes' if supports_proba else 'no — class only'}."
            )
        else:
            st.info("No test metrics available for the current model.")
    elif metrics:
        st.write(f"**Best model (metrics.json):** `{metrics.get('best_model', '?')}`")
        st.json(metrics.get("results", {}))
    else:
        st.warning(
            "Model details unavailable — the model has not been trained yet. "
            "Run `python -m spam_classifier.train` to generate metrics."
        )

# -------- Limitations & safe use ----
with st.expander("ℹ️ Limitations & safe use"):
    st.write(
        "- Prototype trained on short **SMS-style messages** (5,574 rows, ~13% spam); "
        "it has **not** been validated on real email bodies, headers, or attachments.\n"
        "- Predictions are automated estimates. A **ham** result does **not** mean a message is safe.\n"
        "- The app never opens links, executes content, or processes attachments — "
        "message text is treated as untrusted input and is not stored.\n"
        "- Senders/behavior are not analyzed; only message text is used.\n"
        "- Model is selected from the trained artifact at `models/spam_classifier_pipeline.joblib`. "
        "No retraining occurs at request time."
    )

# -------- Footer ----
st.divider()
st.markdown(
    f"<p class='muted'>Educational prototype — not an enterprise email gateway or phishing "
    f"guarantee. Submitted text is processed in memory for prediction and is not retained "
    f"by the app. If hosted publicly, input is processed by the hosted app.</p>",
    unsafe_allow_html=True,
)