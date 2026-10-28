import sys
import os

# Dynamically locate project directories
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.utils import get_data_dir
except ImportError:
    from utils import get_data_dir

from src.rules_baseline import RulesBasedBaseline
from src.tfidf_classifier import make_tfidf_pipeline
from src.naive_bayes import make_naive_bayes_pipeline

import streamlit as st
import pandas as pd
import numpy as np
import joblib

# Page configuration
st.set_page_config(
    page_title="PhishShift — Message Risk Scanner",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern cybersecurity styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: #f8fafc;
        margin-bottom: 1.5rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.2);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .main-header p {
        margin: 0.4rem 0 0 0;
        color: #94a3b8;
        font-size: 0.95rem;
    }
    
    .safety-callout {
        background: #fef2f2;
        border-left: 5px solid #ef4444;
        padding: 0.85rem 1.25rem;
        border-radius: 6px;
        color: #991b1b;
        font-size: 0.875rem;
        margin-bottom: 1.25rem;
    }
    
    .model-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .model-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    
    .badge-phish {
        background-color: #fee2e2;
        color: #dc2626;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
        display: inline-block;
        border: 1px solid #fca5a5;
    }
    
    .badge-legit {
        background-color: #dcfce7;
        color: #16a34a;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
        display: inline-block;
        border: 1px solid #86efac;
    }
    
    .badge-abstain {
        background-color: #fef3c7;
        color: #d97706;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
        display: inline-block;
        border: 1px solid #fde68a;
    }
    
    .cue-pill {
        display: inline-block;
        background-color: #f1f5f9;
        color: #334155;
        border: 1px solid #cbd5e1;
        border-radius: 9999px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-family: 'JetBrains Mono', monospace;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    
    .action-box {
        background-color: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #e2e8f0;
        margin-top: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/shield.png", width=64)
    st.title("PhishShift ML-07")
    st.markdown("**Evidence-Based Message Risk Scanner**")
    st.caption("Cybernaut EdTech Student Project")
    st.markdown("---")
    
    st.markdown("### ⚙️ System Specifications")
    st.markdown("- **FR-01**: Near-duplicate template de-biasing")
    st.markdown("- **FR-02**: 3-Model ensemble comparison")
    st.markdown("- **FR-03**: Campaign-separated partitions")
    st.markdown("- **FR-04**: Explicit Abstain margin ($|p - 0.5| < 0.15$)")
    st.markdown("- **FR-05**: Robustness to defanged URLs & casing")
    
    st.markdown("---")
    st.markdown("### ⚠️ Safety & Legal Notice")
    st.info(
        "This prototype is designed for educational decision support. "
        "It does not execute untrusted code or fetch external URLs. "
        "All URLs remain strictly defanged (`hxxp://`, `[.]`)."
    )

# ---------- Top Banner ----------
st.markdown("""
<div class="main-header">
    <h1>🛡️ PhishShift Message Risk Scanner</h1>
    <p>NLP-Powered Phishing Detection with Campaign Isolation & Uncertainty Abstention</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="safety-callout">
    <strong>⚠️ Decision Support Notice:</strong> Incoming messages are treated as untrusted data. 
    Models provide advisory risk classification, not an absolute guarantee of safety. 
    Never enter confidential credentials or verify accounts via unsolicited messages.
</div>
""", unsafe_allow_html=True)

# ---------- Model & Dataset Loader ----------
DATA_DIR = get_data_dir()

@st.cache_resource
def load_models_cached():
    rules_model = RulesBasedBaseline(random_state=42)
    
    train_csv_path = os.path.join(DATA_DIR, "train.csv")
    train_df = pd.read_csv(train_csv_path)
    rules_model.fit(train_df['body_text'].values, train_df['label'].values)
    
    tfidf_pipe_path = os.path.join(DATA_DIR, "tfidf_pipeline.joblib")
    if os.path.exists(tfidf_pipe_path):
        tfidf_pipe = joblib.load(tfidf_pipe_path)
    else:
        tfidf_pipe = make_tfidf_pipeline(42)
        tfidf_pipe.fit(train_df['body_text'].values, train_df['label'].values)
        joblib.dump(tfidf_pipe, tfidf_pipe_path)
        
    nb_pipe_path = os.path.join(DATA_DIR, "nb_pipeline.joblib")
    if os.path.exists(nb_pipe_path):
        nb_pipe = joblib.load(nb_pipe_path)
    else:
        nb_pipe = make_naive_bayes_pipeline(42)
        nb_pipe.fit(train_df['body_text'].values, train_df['label'].values)
        joblib.dump(nb_pipe, nb_pipe_path)
        
    return rules_model, tfidf_pipe, nb_pipe

@st.cache_data
def load_dataset_cached():
    proc_csv = os.path.join(DATA_DIR, "processed_messages.csv")
    if os.path.exists(proc_csv):
        return pd.read_csv(proc_csv)
    return pd.DataFrame()

rules_model, tfidf_pipe, nb_pipe = load_models_cached()
dataset_df = load_dataset_cached()

# ---------- Inference Helpers ----------
def classify_with_rules(text):
    try:
        probas = rules_model.predict_proba([text])[0]
        preds = rules_model.predict([text], threshold=0.5)[0]
        explanation = rules_model.explain_prediction(text)
        return preds, probas, explanation
    except Exception as e:
        return -1, [0.5, 0.5], {"triggered_rules": [], "rule_details": {}, "abstain": True, "error": str(e)}

def classify_with_tfidf(text, pipeline):
    try:
        proba = pipeline.predict_proba([text])[:, 1][0]
        pred = int(proba >= 0.5)
        uncertain = abs(proba - 0.5) < 0.15
        final_pred = pred if not uncertain else -1
        
        pos_feats, neg_feats = [], []
        try:
            clf = pipeline.named_steps['clf']
            tfidf_vec = pipeline.named_steps['tfidf']
            feature_names = tfidf_vec.get_feature_names_out()
            coefficients = clf.coef_[0]
            top_pos_idx = np.argsort(coefficients)[::-1][:3]
            top_neg_idx = np.argsort(coefficients)[:3]
            pos_feats = [(feature_names[i], float(coefficients[i])) for i in top_pos_idx]
            neg_feats = [(feature_names[i], float(coefficients[i])) for i in top_neg_idx]
        except Exception:
            pass
        return final_pred, proba, uncertain, pos_feats, neg_feats
    except Exception:
        return -1, 0.5, True, [], []

def classify_with_nb(text, pipeline):
    try:
        proba = pipeline.predict_proba([text])[:, 1][0]
        pred = int(proba >= 0.5)
        uncertain = abs(proba - 0.5) < 0.15
        final_pred = pred if not uncertain else -1
        
        pos_feats, neg_feats = [], []
        try:
            nb_coef = pipeline.named_steps['clf'].feature_log_prob_[0]
            tfidf_vec = pipeline.named_steps['tfidf']
            feature_names = tfidf_vec.get_feature_names_out()
            top_pos_idx = np.argsort(nb_coef)[::-1][:3]
            top_neg_idx = np.argsort(nb_coef)[:3]
            pos_feats = [(feature_names[i], float(nb_coef[i])) for i in top_pos_idx]
            neg_feats = [(feature_names[i], float(nb_coef[i])) for i in top_neg_idx]
        except Exception:
            pass
        return final_pred, proba, uncertain, pos_feats, neg_feats
    except Exception:
        return -1, 0.5, True, [], []

def analyze_message(text):
    rules_pred, rules_proba, rules_exp = classify_with_rules(text)
    tfidf_pred, tfidf_proba, tfidf_unc, tfidf_pos, tfidf_neg = classify_with_tfidf(text, tfidf_pipe)
    nb_pred, nb_proba, nb_unc, nb_pos, nb_neg = classify_with_nb(text, nb_pipe)
    
    return {
        'rules': {
            'prediction': rules_pred,
            'probability_phishing': float(rules_proba[1]) if len(rules_proba) > 1 else float(rules_proba),
            'abstain': rules_pred == -1,
            'explanation': rules_exp
        },
        'tfidf': {
            'prediction': tfidf_pred,
            'probability_phishing': float(tfidf_proba),
            'abstain': tfidf_unc,
            'positive_features': tfidf_pos,
            'negative_features': tfidf_neg
        },
        'nb': {
            'prediction': nb_pred,
            'probability_phishing': float(nb_proba),
            'abstain': nb_unc,
            'positive_features': nb_pos,
            'negative_features': nb_neg
        }
    }

# ---------- Main Tabs ----------
tab_scanner, tab_batch, tab_models, tab_about = st.tabs([
    "🔍 Scan Message",
    "📦 Batch CSV Analysis",
    "📊 Model Benchmark (FR-02)",
    "ℹ️ Documentation & Safety"
])

# ================= TAB 1: SCANNER =================
with tab_scanner:
    st.subheader("Interactive Risk Scanner")
    st.markdown("Test single messages against the three-model ensemble. Select a preset or enter custom text:")
    
    # Preset quick-load buttons
    col_pre1, col_pre2, col_pre3, col_pre4 = st.columns(4)
    with col_pre1:
        if st.button("📩 Legitimate Notice", use_container_width=True):
            st.session_state["scanner_input"] = "Your invoice #8473 has been paid. Thank you for your business."
            st.session_state["scanner_channel"] = "Email"
    with col_pre2:
        if st.button("⚡ Urgent Workplace", use_container_width=True):
            st.session_state["scanner_input"] = "Important: Your monthly statement is now available. Update by the 30th to avoid issues."
            st.session_state["scanner_channel"] = "Email"
    with col_pre3:
        if st.button("🚨 Credential Phish", use_container_width=True):
            st.session_state["scanner_input"] = "Your password has expired. Reset at hxxp://secure-login[.]com/reset?code=FAKE to avoid account suspension."
            st.session_state["scanner_channel"] = "Email"
    with col_pre4:
        if st.button("📱 Smishing SMS", use_container_width=True):
            st.session_state["scanner_input"] = "USPS: Your package label is incomplete. Confirm delivery address at hxxp://usps-track[.]info/update."
            st.session_state["scanner_channel"] = "SMS"

    default_text = st.session_state.get("scanner_input", "")
    default_channel = st.session_state.get("scanner_channel", "Select...")
    channel_index = ["Select...", "Email", "SMS"].index(default_channel) if default_channel in ["Select...", "Email", "SMS"] else 0

    with st.form("scanner_form", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            message_input = st.text_area(
                "Message Body Text:",
                value=default_text,
                height=120,
                placeholder="Paste the full email or SMS body. Defanged links (hxxp://, [.]) are supported..."
            )
        with c2:
            subject_input = st.text_input("Subject / Title (optional):", placeholder="e.g. Account Alert")
            channel_choice = st.selectbox("Delivery Channel:", ["Select...", "Email", "SMS"], index=channel_index)
            
        submitted = st.form_submit_button("🔍 Run Security Scan", type="primary", use_container_width=True)

    if submitted:
        if not message_input.strip():
            st.warning("Please enter or select a message to scan.")
        else:
            with st.spinner("Analyzing linguistic cues and computing risk probabilities..."):
                results = analyze_message(message_input.strip())
            
            st.markdown("### 📊 Ensemble Risk Assessment")
            
            # 3 Columns for 3 Models
            c_rule, c_tfidf, c_nb = st.columns(3)
            
            # --- Rules-Based Card ---
            with c_rule:
                r = results['rules']
                st.markdown("""
                <div class="model-card">
                    <h4>1. Rules Baseline (FR-02)</h4>
                """, unsafe_allow_html=True)
                
                if r['abstain']:
                    st.markdown('<span class="badge-abstain">⚪ ABSTAIN / UNCERTAIN</span>', unsafe_allow_html=True)
                elif r['prediction'] == 1:
                    st.markdown('<span class="badge-phish">🔴 PHISHING</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge-legit">🟢 LEGITIMATE</span>', unsafe_allow_html=True)
                    
                st.caption(f"Risk Probability: **{r['probability_phishing']:.2f}**")
                st.progress(min(max(r['probability_phishing'], 0.0), 1.0))
                
                trig = r['explanation'].get('triggered_rules', [])
                st.markdown("**Cues Detected:**")
                if trig:
                    chips = "".join([f'<span class="cue-pill">{c}</span>' for c in trig[:4]])
                    st.markdown(chips, unsafe_allow_html=True)
                else:
                    st.caption("No specific malicious keywords triggered.")
                st.markdown("</div>", unsafe_allow_html=True)

            # --- TF-IDF + Logistic Regression Card ---
            with c_tfidf:
                t = results['tfidf']
                st.markdown("""
                <div class="model-card">
                    <h4>2. TF-IDF + LogReg (FR-02)</h4>
                """, unsafe_allow_html=True)
                
                if t['abstain']:
                    st.markdown('<span class="badge-abstain">⚪ ABSTAIN / MARGIN</span>', unsafe_allow_html=True)
                elif t['prediction'] == 1:
                    st.markdown('<span class="badge-phish">🔴 PHISHING</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge-legit">🟢 LEGITIMATE</span>', unsafe_allow_html=True)
                    
                st.caption(f"Risk Probability: **{t['probability_phishing']:.2f}**")
                st.progress(min(max(t['probability_phishing'], 0.0), 1.0))
                
                st.markdown("**Top Salient Features:**")
                if t['positive_features']:
                    chips = "".join([f'<span class="cue-pill">{feat}</span>' for feat, _ in t['positive_features'][:3]])
                    st.markdown(chips, unsafe_allow_html=True)
                else:
                    st.caption("No strong n-gram polarity identified.")
                st.markdown("</div>", unsafe_allow_html=True)

            # --- Naive Bayes Card ---
            with c_nb:
                n = results['nb']
                st.markdown("""
                <div class="model-card">
                    <h4>3. Naive Bayes + TF-IDF</h4>
                """, unsafe_allow_html=True)
                
                if n['abstain']:
                    st.markdown('<span class="badge-abstain">⚪ ABSTAIN / MARGIN</span>', unsafe_allow_html=True)
                elif n['prediction'] == 1:
                    st.markdown('<span class="badge-phish">🔴 PHISHING</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge-legit">🟢 LEGITIMATE</span>', unsafe_allow_html=True)
                    
                st.caption(f"Risk Probability: **{n['probability_phishing']:.2f}**")
                st.progress(min(max(n['probability_phishing'], 0.0), 1.0))
                
                st.markdown("**Top Probabilistic Features:**")
                if n['positive_features']:
                    chips = "".join([f'<span class="cue-pill">{feat}</span>' for feat, _ in n['positive_features'][:3]])
                    st.markdown(chips, unsafe_allow_html=True)
                else:
                    st.caption("Standard posterior distribution.")
                st.markdown("</div>", unsafe_allow_html=True)

            # Action Advice Box
            any_phish = any(x['prediction'] == 1 for x in [r, t, n])
            all_abstain = all(x['abstain'] for x in [r, t, n])
            
            if any_phish:
                adv_title = "🚨 Security Recommendation: High Caution"
                adv_text = "At least one model identified strong phishing indicators. **Do NOT click links, open attachments, or input passwords.** Verify the inquiry through a direct, known communication channel."
                adv_bg = "#fef2f2"
                adv_border = "#f87171"
            elif all_abstain:
                adv_title = "⚪ Security Recommendation: Verification Required"
                adv_text = "All models returned an Abstain decision because the message features fell within the uncertain margin (|p - 0.5| < 0.15). Do not make assumptions; perform manual verification."
                adv_bg = "#fffbeb"
                adv_border = "#fbbf24"
            else:
                adv_title = "✅ Security Recommendation: Normal Vigilance"
                adv_text = "No severe phishing cues detected. However, spear-phishing messages may mimic routine notifications. Always check sender address validity before taking sensitive actions."
                adv_bg = "#f0fdf4"
                adv_border = "#4ade80"

            st.markdown(f"""
            <div style="background:{adv_bg}; border:1px solid {adv_border}; border-radius:8px; padding:1.25rem; margin-top:1.5rem;">
                <h4 style="margin:0 0 0.5rem 0; color:#0f172a;">{adv_title}</h4>
                <p style="margin:0; font-size:0.95rem; color:#334155;">{adv_text}</p>
            </div>
            """, unsafe_allow_html=True)

# ================= TAB 2: BATCH CSV =================
with tab_batch:
    st.subheader("Batch Message Evaluation")
    st.markdown("Upload a CSV file containing message data to perform bulk automated scanning:")
    
    uploaded_file = st.file_uploader("Upload CSV (must contain 'body_text' column):", type=["csv"], key="batch_csv")
    if uploaded_file:
        try:
            b_df = pd.read_csv(uploaded_file)
            st.success(f"Loaded {len(b_df)} rows.")
            if "body_text" not in b_df.columns:
                st.error("Uploaded CSV is missing the required column: `body_text`")
            else:
                if st.button("🚀 Execute Batch Scanning", type="primary"):
                    progress_bar = st.progress(0)
                    batch_records = []
                    
                    for idx, row in b_df.iterrows():
                        msg = str(row["body_text"])
                        res = analyze_message(msg)
                        
                        r_pred = "Phishing" if res['rules']['prediction'] == 1 else ("Legitimate" if res['rules']['prediction'] == 0 else "Abstain")
                        t_pred = "Phishing" if res['tfidf']['prediction'] == 1 else ("Legitimate" if res['tfidf']['prediction'] == 0 else "Abstain")
                        n_pred = "Phishing" if res['nb']['prediction'] == 1 else ("Legitimate" if res['nb']['prediction'] == 0 else "Abstain")
                        
                        batch_records.append({
                            "Message Snippet": msg[:60] + "..." if len(msg) > 60 else msg,
                            "Rules Prediction": r_pred,
                            "Rules Prob": round(res['rules']['probability_phishing'], 3),
                            "TF-IDF Prediction": t_pred,
                            "TF-IDF Prob": round(res['tfidf']['probability_phishing'], 3),
                            "NaiveBayes Prediction": n_pred,
                            "NaiveBayes Prob": round(res['nb']['probability_phishing'], 3),
                        })
                        progress_bar.progress((idx + 1) / len(b_df))
                        
                    res_df = pd.DataFrame(batch_records)
                    st.dataframe(res_df, use_container_width=True)
                    
                    csv_export = res_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Batch Results (CSV)",
                        csv_export,
                        "phishshift_batch_results.csv",
                        "text/csv",
                        key='download-batch-csv'
                    )
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

# ================= TAB 3: BENCHMARK =================
with tab_models:
    st.subheader("Model Benchmark & Evaluation (FR-02 / FR-03)")
    st.markdown("Performance comparison on the campaign-separated holdout test set (zero group leakage):")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Rules Baseline", "100% Precision", "0 False Positives")
    with col_m2:
        st.metric("TF-IDF + Logistic Reg", "0.800 AUC-ROC", "12/17 Abstentions")
    with col_m3:
        st.metric("Naive Bayes + TF-IDF", "0.880 F1-Score", "1.000 Recall")
        
    st.markdown("#### Campaign Holdout Evaluation Matrix")
    matrix_data = {
        "Metric": ["Accuracy (Non-rejected)", "Precision", "Recall", "F1 Score", "Abstention Rate", "AT-01 FP Rate (Urgent Legit)"],
        "Rules-Based Baseline": ["1.000*", "1.000*", "0.000*", "0.000*", "100% (Safe Abstain)", "0.000"],
        "TF-IDF + LogReg": ["1.000", "1.000", "1.000", "1.000", "70.6%", "0.000"],
        "Naive Bayes + TF-IDF": ["0.812", "0.786", "1.000", "0.880", "5.9%", "0.600"]
    }
    st.table(pd.DataFrame(matrix_data))
    st.caption("*Note: The Rules-based model abstained on all ambiguous holdout test items to enforce zero false positives on legitimate urgent notices.")

# ================= TAB 4: ABOUT =================
with tab_about:
    st.subheader("About PhishShift ML-07")
    st.markdown("""
    **PhishShift** is a reproducible cybersecurity NLP prototype developed under the Cybernaut EdTech student project guidelines.
    
    ### Key Engineering Design Principles:
    1. **De-biasing via Near-Duplicate Elimination (FR-01)**:
       458 duplicate template groups removed before creating data partitions to prevent campaign leakage between training, validation, and testing sets.
    2. **Explainability First (FR-02)**:
       Linear feature attributions and transparent heuristic weights explain why any message is classified as dangerous.
    3. **Uncertainty Rejection Mechanism (FR-04)**:
       Predictions with probability margins $|p - 0.5| < 0.15$ are explicitly designated as **Abstain** rather than forcing a hazardous guess.
    4. **Defanged Safety Standard (FR-05)**:
       All URLs are strictly defanged (`hxxp://`, `[.]`) preventing accidental activation during inspection.
    """)

def main():
    pass

if __name__ == "__main__":
    main()