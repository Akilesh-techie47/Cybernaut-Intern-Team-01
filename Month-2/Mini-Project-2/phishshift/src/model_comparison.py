import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.metrics import confusion_matrix, classification_report, roc_auc_score


def make_tfidf_pipeline(random_state=42):
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            lowercase=True, stop_words='english', ngram_range=(1, 2),
            max_features=5000, min_df=2, max_df=0.95,
        )),
        ('clf', LogisticRegression(random_state=random_state, class_weight='balanced',
                                   solver='lbfgs', max_iter=1000)),
    ])
    return pipeline


def make_nb_pipeline(random_state=42):
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            lowercase=True, stop_words='english', ngram_range=(1, 2),
            max_features=5000, min_df=2, max_df=0.95,
        )),
        ('clf', MultinomialNB(alpha=0.1, fit_prior=True)),
    ])
    return pipeline


def rules_predict_proba(X):
    import re
    rules = [
        {'name': 'urgency_language', 'condition': lambda text: any(w in text.lower() for w in ['urgently', 'immediately', 'expired', 'suspended', 'locked', 'expire', 'suspend', 'limited time']), 'weight': 0.3},
        {'name': 'authority_impersonation', 'condition': lambda text: any(phrase in text.lower() for phrase in ['irs', 'tax refund', 'bank alert', 'account suspended', 'admin', 'support team', 'security alert']), 'weight': 0.35},
        {'name': 'password_reset', 'condition': lambda text: any(w in text.lower() for w in ['password', 'reset', 'login', 'credential', 'sign-in']), 'weight': 0.2},
        {'name': 'financial_theme', 'condition': lambda text: any(w in text.lower() for w in ['payment', 'invoice', 'refund', 'overdue', 'outstanding']), 'weight': 0.15},
        {'name': 'defanged_url', 'condition': lambda text: 'hxxp' in text.lower(), 'weight': 0.4},
        {'name': 'no_legitimate_indicator', 'condition': lambda text: not any(w in text.lower() for w in ['thank you', 'confirmation', 'receipt', 'invoice paid', 'successfully', 'update completed']) and any(w in text.lower() for w in ['urgent', 'expired', 'locked', 'suspend']), 'weight': 0.25},
    ]
    probabilities = []
    for text in X:
        score = 0.0
        triggered = []
        for rule in rules:
            if rule['condition'](text):
                score += rule['weight']
                triggered.append(rule['name'])
        max_possible = sum(r['weight'] for r in rules)
        prob_phishing = min(score / max_possible, 1.0)
        probabilities.append([1.0 - prob_phishing, prob_phishing])
    return np.array(probabilities)


def rules_predict(X, threshold=0.5):
    probas = rules_predict_proba(X)
    predictions = []
    for i, prob in enumerate(probas):
        if prob[1] > threshold and abs(prob[1] - 0.5) >= 0.2:
            predictions.append(1 if prob[1] > threshold else -1)
        else:
            predictions.append(-1)  # abstain
    return np.array(predictions)


def evaluate_model(y_true, y_pred, name="", threshold=0.5):
    valid_mask = y_pred != -1
    y_t = y_true[valid_mask]
    y_p = y_pred[valid_mask]
    
    if len(y_t) == 0:
        return {'name': name, 'accuracy': float('nan'), 'precision': float('nan'),
                'recall': float('nan'), 'f1': float('nan'), 'auc': float('nan'),
                'n_rejected': len(y_true), 'n_total': len(y_true),
                'confusion_matrix': np.array([[0, 0], [0, 0]])}
    
    try:
        auc = roc_auc_score(y_t, probas[valid_mask]) if 'probas' in dir() else float('nan')
    except:
        auc = float('nan')
    
    try:
        cm = confusion_matrix(y_t, y_p, labels=[0, 1])
    except:
        cm = np.array([[0, 0], [0, 0]])
    
    try:
        report = classification_report(y_t, y_p, target_names=['legitimate', 'phishing'], zero_division=0, output_dict=True)
    except:
        report = {'legitimate': {'precision': 1.0, 'recall': 1.0, 'f1-score': 1.0, 'support': len(y_t)},
                  'phishing': {'precision': float('nan'), 'recall': float('nan'), 'f1-score': float('nan'), 'support': 0},
                  'accuracy': 1.0, 'macro avg': {'precision': float('nan'), 'recall': float('nan'), 'f1-score': float('nan'), 'support': len(y_t)},
                  'weighted avg': {'precision': float('nan'), 'recall': float('nan'), 'f1-score': float('nan'), 'support': len(y_t)}}
    
    return {
        'name': name, 'accuracy': np.mean(y_t == y_p) if len(y_t) > 0 else float('nan'),
        'precision': report['phishing']['precision'] if 'phishing' in report else float('nan'),
        'recall': report['phishing']['recall'] if 'phishing' in report else float('nan'),
        'f1': report['phishing']['f1-score'] if 'phishing' in report else float('nan'),
        'auc': auc, 'n_rejected': len(y_true) - len(y_t), 'n_total': len(y_true),
        'confusion_matrix': cm
    }


def run_all_evaluations():
    try:
        from src.utils import get_data_dir
    except ImportError:
        from utils import get_data_dir
    data_dir = get_data_dir()
    train_df = pd.read_csv(os.path.join(data_dir, "train.csv"))
    valid_df = pd.read_csv(os.path.join(data_dir, "valid.csv"))
    test_df = pd.read_csv(os.path.join(data_dir, "test.csv"))
    
    # Train models
    print("Training models...")
    tfidf_pipe = make_tfidf_pipeline(42)
    tfidf_pipe.fit(train_df['body_text'], train_df['label'])
    
    nb_pipe = make_nb_pipeline(42)
    nb_pipe.fit(train_df['body_text'], train_df['label'])
    
    # Rules baseline
    rules_preds = rules_predict(test_df['body_text'].values)
    
    # Evaluate TF-IDF
    tfidf_test_probas = tfidf_pipe.predict_proba(test_df['body_text'])[:, 1]
    tfidf_preds_raw = (tfidf_test_probas >= 0.5).astype(int)
    tfidf_uncertain = np.abs(tfidf_test_probas - 0.5) < 0.15
    tfidf_preds = tfidf_preds_raw.copy()
    tfidf_preds[tfidf_uncertain] = -1
    
    # Evaluate NB
    nb_test_probas = nb_pipe.predict_proba(test_df['body_text'])[:, 1]
    nb_preds_raw = (nb_test_probas >= 0.5).astype(int)
    nb_uncertain = np.abs(nb_test_probas - 0.5) < 0.15
    nb_preds = nb_preds_raw.copy()
    nb_preds[nb_uncertain] = -1
    
    # Collect results
    results = []
    
    # Rules
    r = evaluate_model(test_df['label'].values, rules_preds, name="Rules-based")
    r['model'] = 'Rules-based'
    results.append(r)
    
    # TF-IDF
    r = evaluate_model(test_df['label'].values, tfidf_preds, name="TF-IDF-LogReg")
    r['model'] = 'TF-IDF-LogReg'
    results.append(r)
    
    # Naive Bayes
    r = evaluate_model(test_df['label'].values, nb_preds, name="Naive-Bayes")
    r['model'] = 'Naive-Bayes'
    results.append(r)
    
    # Create comparison DataFrame
    comparison = pd.DataFrame([{
        'model': r['model'],
        'accuracy': r['accuracy'] if not np.isnan(r['accuracy']) else 'N/A',
        'precision': r['precision'] if not np.isnan(r['precision']) else 'N/A',
        'recall': r['recall'] if not np.isnan(r['recall']) else 'N/A',
        'f1': r['f1'] if not np.isnan(r['f1']) else 'N/A',
        'auc': r['auc'] if not np.isnan(r['auc']) else 'N/A',
        'rejected': r['n_rejected'],
        'total': r['n_total'],
    } for r in results])
    
    print("\n" + "=" * 70)
    print("MODEL COMPARISON (on test set with campaign separation)")
    print("=" * 70)
    print(comparison.to_string(index=False))
    print()
    
    # Confusion matrices
    print("Confusion matrices (test set):")
    for r in results:
        cm = r['confusion_matrix']
        if np.sum(cm) > 0:
            tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)
            print(f"  {r['model']}: TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    
    # False positive rate on legitimate urgent messages (AT-01)
    print("\nAT-01: False positive rate on legitimate urgent messages")
    legitimate_urgent = test_df[test_df['campaign_group'] == 'legitimate-urgent']
    if len(legitimate_urgent) > 0:
        lbodies = legitimate_urgent['body_text'].values
        # Rules
        r_rules = rules_predict_proba(lbodies)
        r_preds = rules_predict(lbodies, threshold=0.5)
        fp_rules = np.sum((r_preds == 1) & (legitimate_urgent['label'].values == 0))
        print(f"  Rules-based: FP rate = {fp_rules}/{len(legitimate_urgent)} = {fp_rules/len(legitimate_urgent):.3f}")
        
        # TF-IDF
        tfidf_probas = tfidf_pipe.predict_proba(lbodies)[:, 1]
        tfidf_unc = np.abs(tfidf_probas - 0.5) < 0.15
        tfidf_preds = (tfidf_probas >= 0.5).astype(int)
        tfidf_preds[tfidf_unc] = -1
        fp_tfidf = np.sum((tfidf_preds == 1) & (legitimate_urgent['label'].values == 0) & (tfidf_preds != -1))
        total_non_rejected_tfidf = np.sum(tfidf_preds != -1)
        print(f"  TF-IDF: FP rate = {fp_tfidf}/{total_non_rejected_tfidf} = {fp_tfidf/max(total_non_rejected_tfidf,1):.3f} (rejected {np.sum(tfidf_unc)}/{len(tfidf_probas)})")
        
        # Naive Bayes
        nb_probas = nb_pipe.predict_proba(lbodies)[:, 1]
        nb_unc = np.abs(nb_probas - 0.5) < 0.15
        nb_preds = (nb_probas >= 0.5).astype(int)
        nb_preds[nb_unc] = -1
        fp_nb = np.sum((nb_preds == 1) & (legitimate_urgent['label'].values == 0) & (nb_preds != -1))
        total_non_rejected_nb = np.sum(nb_preds != -1)
        print(f"  Naive-Bayes: FP rate = {fp_nb}/{total_non_rejected_nb} = {fp_nb/max(total_non_rejected_nb,1):.3f} (rejected {np.sum(nb_unc)}/{len(nb_probas)})")
    
    return comparison


if __name__ == "__main__":
    run_all_evaluations()