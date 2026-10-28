import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import confusion_matrix, classification_report, roc_auc_score


def make_naive_bayes_pipeline(random_state=42):
    """Create TF-IDF with Naive Bayes classifier pipeline."""
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            ngram_range=(1, 2),
            max_features=5000,
            min_df=2,
            max_df=0.95,
        )),
        ('clf', MultinomialNB(
            alpha=0.1,
            fit_prior=True,
        )),
    ])
    return pipeline


def train_naive_bayes(train_df, random_state=42):
    """Train Naive Bayes model with TF-IDF features."""
    pipeline = make_naive_bayes_pipeline(random_state)
    
    X_train = train_df['body_text']
    y_train = train_df['label']
    
    pipeline.fit(X_train, y_train)
    
    return pipeline


def evaluate_nb(model, df, name="", threshold=0.5, reject_uncertain=True):
    """Evaluate Naive Bayes model on a dataset, with optional uncertain/reject outcome."""
    X = df['body_text']
    y = df['label']
    
    probas = model.predict_proba(X)[:, 1]
    preds_raw = (probas >= threshold).astype(int)
    
    # uncertain/reject mechanism
    if reject_uncertain:
        margin = 0.15
        uncertainties = np.abs(probas - 0.5) < margin
        preds = preds_raw.copy()
        preds[uncertainties] = -1  # -1 = reject/abstain
    else:
        preds = preds_raw
    
    # Compute metrics excluding rejects
    valid_mask = preds != -1
    y_true = y[valid_mask]
    y_pred = preds[valid_mask]
    
    # Remove warning for single-class metrics
    with np.errstate(invalid='ignore'):
        try:
            auc = roc_auc_score(y, probas)
        except:
            auc = float('nan')
    
    unique_classes = np.unique(y_true)
    
    # Handle case where all predictions are rejected or only one class remains
    if len(y_true) == 0:
        cm = np.array([[0, 0], [0, 0]])
        report = {'legitimate': {'precision': float('nan'), 'recall': float('nan'), 
                                  'f1-score': float('nan'), 'support': 0},
                  'phishing': {'precision': float('nan'), 'recall': float('nan'),
                              'f1-score': float('nan'), 'support': 0},
                  'accuracy': float('nan'), 'macro avg': {'precision': float('nan'),
                                  'recall': float('nan'), 'f1-score': float('nan'), 'support': 0},
                  'weighted avg': {'precision': float('nan'), 'recall': float('nan'),
                                  'f1-score': float('nan'), 'support': 0}}
    elif len(unique_classes) == 1:
        if unique_classes[0] == 1:  # only phishing
            cm = np.array([[0, 0], [0, len(y_true)]])
        else:  # only legitimate
            cm = np.array([[len(y_true), 0], [0, 0]])
        report = {'legitimate': {'precision': 1.0, 'recall': 1.0, 'f1-score': 1.0, 'support': len(y_true)},
                  'phishing': {'precision': float('nan'), 'recall': float('nan'), 'f1-score': float('nan'), 'support': 0},
                  'accuracy': 1.0, 'macro avg': {'precision': float('nan'),
                                  'recall': float('nan'), 'f1-score': float('nan'), 'support': len(y_true)},
                  'weighted avg': {'precision': float('nan'), 'recall': float('nan'),
                                  'f1-score': float('nan'), 'support': len(y_true)}}
    else:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        report = classification_report(y_true, y_pred, target_names=['legitimate', 'phishing'], 
                                       zero_division=0, output_dict=True)
    
    results = {
        'name': name,
        'auc': auc,
        'accuracy': np.mean(y_true == y_pred) if len(y_true) > 0 else float('nan'),
        'precision': report['phishing']['precision'] if 'phishing' in report and not np.isnan(report['phishing']['precision']) else float('nan'),
        'recall': report['phishing']['recall'] if 'phishing' in report and not np.isnan(report['phishing']['recall']) else float('nan'),
        'f1': report['phishing']['f1-score'] if 'phishing' in report and not np.isnan(report['phishing']['f1-score']) else float('nan'),
        'threshold': threshold,
        'n_rejected': int(np.sum(uncertainties)) if reject_uncertain else 0,
        'n_total': len(df),
    }
    
    return probas, preds, results, cm


def split_evaluate_nb(train_df, valid_df, test_df, random_state=42):
    """Train Naive Bayes and evaluate across campaign-separated partitions."""
    # Train on train campaigns
    pipeline = make_naive_bayes_pipeline(random_state)
    pipeline.fit(train_df['body_text'], train_df['label'])
    
    results = {}
    
    # Evaluate on each split
    for name, df in [("train", train_df), ("valid", valid_df), ("test", test_df)]:
        probas, preds, r, cm = evaluate_nb(pipeline, df, name=name, 
                                           threshold=0.5, reject_uncertain=True)
        results[name] = r
        print(f"\n{name.upper()} set:")
        print(f"  AUC: {r['auc']:.3f}, Accuracy: {r['accuracy']:.3f}" if not np.isnan(r['accuracy']) else f"  AUC: {r['auc']}, Accuracy: N/A")
        print(f"  Precision/Recall/F1: {r['precision']:.3f}/{r['recall']:.3f}/{r['f1']:.3f}" 
              if not (np.isnan(r['precision']) or np.isnan(r['recall']) or np.isnan(r['f1'])) 
              else f"  Precision/Recall/F1: N/A")
        print(f"  Rejected/abstained: {r['n_rejected']}/{r['n_total']}")
        if np.sum(cm) > 0:
            print(f"  Confusion matrix:\n{cm}")
    
    return results


if __name__ == "__main__":
    try:
        from src.utils import get_data_dir
    except ImportError:
        from utils import get_data_dir
    data_dir = get_data_dir()
    train_df = pd.read_csv(os.path.join(data_dir, "train.csv"))
    valid_df = pd.read_csv(os.path.join(data_dir, "valid.csv"))
    test_df = pd.read_csv(os.path.join(data_dir, "test.csv"))
    
    print("=" * 60)
    print("Naive Bayes + TF-IDF - Campaign-Split Evaluation")
    print("=" * 60)
    results = split_evaluate_nb(train_df, valid_df, test_df, random_state=42)