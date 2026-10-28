import re
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin


class RulesBasedBaseline(BaseEstimator, ClassifierMixin):
    """
    Explainable rules-based baseline for phishing detection.
    
    Rules are derived from common phishing indicators:
    - Urgency language ("immediately", "expired", "suspend")
    - Authority impersonation (" IRS ", " bank ", " admin ")
    - Pressure tactics
    - URL-based indicators
    """
    
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.rules = self._define_rules()
        self.threshold = 0.5
    
    def _define_rules(self):
        """Define rules with explanation weights."""
        return [
            # Urgency rule - high confidence phishing indicator
            {
                'name': 'urgency_language',
                'condition': lambda text: any(w in text.lower() for w in [
                    'urgently', 'immediately', 'expired', 'suspended', 'locked',
                    'expire', 'suspend', 'limited time'
                ]),
                'weight': 0.3,
                'explanation': 'Urgency language pressuring immediate action'
            },
            # Authority impersonation rule
            {
                'name': 'authority_impersonation',
                'condition': lambda text: any(phrase in text.lower() for phrase in [
                    'irs', 'tax refund', 'bank alert', 'account suspended',
                    'admin', 'support team', 'security alert'
                ]),
                'weight': 0.35,
                'explanation': 'Authority impersonation claiming official status'
            },
            # Password/reset related
            {
                'name': 'password_reset',
                'condition': lambda text: any(w in text.lower() for w in [
                    'password', 'reset', 'login', 'credential', 'sign-in'
                ]),
                'weight': 0.2,
                'explanation': 'Password or login related request'
            },
            # Financial/theme
            {
                'name': 'financial_theme',
                'condition': lambda text: any(w in text.lower() for w in [
                    'payment', 'invoice', 'refund', 'overdue', 'outstanding'
                ]),
                'weight': 0.15,
                'explanation': 'Financial theme (payment, invoice, refund)'
            },
            # Defanged URL presence
            {
                'name': 'defanged_url',
                'condition': lambda text: 'hxxp' in text.lower(),
                'weight': 0.4,
                'explanation': 'Defanged URL present in message'
            },
            # No legitimate indicator + urgent = phishing
            {
                'name': 'no_legitimate_indicator',
                'condition': lambda text: not any(w in text.lower() for w in [
                    'thank you', 'confirmation', 'receipt', 'invoice paid',
                    'successfully', 'update completed'
                ]) and any(w in text.lower() for w in [
                    'urgent', 'expired', 'locked', 'suspend'
                ]),
                'weight': 0.25,
                'explanation': 'Urgent language without legitimate confirmation markers'
            }
        ]
    
    def fit(self, X, y=None):
        """Fit method for sklearn compatibility - no training needed."""
        return self
    
    def predict_proba(self, X):
        """Return prediction probabilities based on rule weights."""
        probabilities = []
        for text in X:
            score = 0.0
            triggered = []
            for rule in self.rules:
                if rule['condition'](text):
                    score += rule['weight']
                    triggered.append(rule['name'])
            
            # Normalize by total rule weight (sum = 2.0)
            max_possible = sum(r['weight'] for r in self.rules)
            prob_phishing = min(score / max_possible, 1.0)
            prob_legitimate = 1.0 - prob_phishing
            
            probabilities.append([prob_legitimate, prob_phishing])
        
        return np.array(probabilities)
    
    def predict(self, X, threshold=0.5):
        """Predict labels, with explicit reject/abstain for uncertain predictions."""
        probas = self.predict_proba(X)
        predictions = []
        margin = 0.15
        for i, prob in enumerate(probas):
            if abs(prob[1] - 0.5) < margin:
                # Uncertain - abstain
                predictions.append(-1)  # -1 denotes abstain/reject
            elif prob[1] > 0.5:
                predictions.append(1)  # phishing
            else:
                predictions.append(0)  # legitimate
        return np.array(predictions)
    
    def explain_prediction(self, text):
        """Provide explanation tied to actual message features."""
        score = 0.0
        triggered = []
        for rule in self.rules:
            if rule['condition'](text):
                score += rule['weight']
                triggered.append(rule['name'])
        
        max_possible = sum(r['weight'] for r in self.rules)
        prob_phishing = min(score / max_possible, 1.0)
        
        explanation = {
            'probability_phishing': round(prob_phishing, 3),
            'triggered_rules': triggered,
            'rule_details': {r['name']: r['explanation'] for r in self.rules if r['condition'](text)},
            'abstain': prob_phishing < 0.5 or prob_phishing > 0.5 and abs(prob_phishing - 0.5) < 0.2
        }
        return explanation


if __name__ == "__main__":
    try:
        from src.utils import get_data_dir
    except ImportError:
        from utils import get_data_dir
    data_dir = get_data_dir()
    df = pd.read_csv(os.path.join(data_dir, "train.csv"))
    
    # Initialize and fit baseline
    model = RulesBasedBaseline(random_state=42)
    model.fit(df['body_text'], df['label'])
    
    # Test on train data
    X = df['body_text'].values
    y = df['label'].values
    probas = model.predict_proba(X)
    preds = model.predict(X, threshold=0.5)
    
    # Compute metrics
    from sklearn.metrics import confusion_matrix, classification_report
    
    # Filter out abstentions (-1) for accuracy computation
    valid_mask = preds != -1
    y_valid = y[valid_mask]
    preds_valid = preds[valid_mask]
    
    print("Rules-Based Baseline Evaluation (on training data)")
    print(f"Total predictions: {len(preds)}, Abstained: {np.sum(preds == -1)}")
    print(f"Accuracy (non-abstain): {np.mean(y_valid == preds_valid):.3f}")
    print("\nClassification report (non-abstain):")
    print(classification_report(y_valid, preds_valid, target_names=['legitimate', 'phishing']))
    print("\nConfusion matrix (non-abstain):")
    print(confusion_matrix(y_valid, preds_valid, labels=[0, 1]))
    
    # Explain a few predictions
    print("\nSample explanations:")
    for i in range(min(5, len(X))):
        exp = model.explain_prediction(X[i])
        print(f"  Sample {i}: prob_phishing={exp['probability_phishing']}, "
              f"triggered={exp['triggered_rules']}")