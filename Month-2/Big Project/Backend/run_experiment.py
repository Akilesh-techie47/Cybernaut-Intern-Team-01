import os, joblib, numpy as np, pandas as pd, time
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, average_precision_score
import json

base = r'D:\Cybernaut intern\Big project (month-2)'

# Load data using pandas parquet
X_train = pd.read_parquet(os.path.join(base, 'data', 'processed', 'X_train.parquet'))
X_test = pd.read_parquet(os.path.join(base, 'data', 'processed', 'X_test.parquet'))
y_train = pd.read_parquet(os.path.join(base, 'data', 'processed', 'y_train.parquet'))
y_test = pd.read_parquet(os.path.join(base, 'data', 'processed', 'y_test.parquet'))
preprocessor = joblib.load(os.path.join(base, 'artifacts', 'preprocessor.joblib'))

print('Data loaded successfully')
print(f'X_train shape: {X_train.shape}')
print(f'X_test shape: {X_test.shape}')
print(f'y_train unique: {np.unique(y_train, return_counts=True)}')
print(f'y_test unique: {np.unique(y_test, return_counts=True)}')

# The X_train/X_test already have the transformed feature names from the preprocessor
# Use the column names directly as features
feature_names = X_train.columns.tolist()
print(f'Feature names count: {len(feature_names)}')

# Define models
models = {
    'Logistic Regression': LogisticRegression(max_iter=1000, random_state=42),
    'Linear SVC': LinearSVC(max_iter=1000, random_state=42, dual='auto'),
    'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42, max_features='sqrt'),
    'HistGradientBoosting': HistGradientBoostingClassifier(max_iter=100, random_state=42),
}

# Train and evaluate models
results = {}
for name, model in models.items():
    print(f'\nTraining {name}...')
    start_time = time.time()
    
    # Use DataFrame columns directly (already preprocessed)
    X_train_trans = X_train[feature_names]
    X_test_trans = X_test[feature_names]
    
    # Fit model
    model.fit(X_train_trans, y_train.values.ravel())
    
    # Predict
    y_pred = model.predict(X_test_trans)
    y_pred_proba = model.predict_proba(X_test_trans)[:, 1] if hasattr(model, 'predict_proba') else None
    
    elapsed = time.time() - start_time
    
    # Calculate metrics
    # Ensure y_test is a Series for comparison
    y_test_series = y_test.iloc[:, 0] if isinstance(y_test, pd.DataFrame) else y_test
    accuracy = (y_pred == y_test_series).mean()
    
    tp = (y_pred[y_test_series == 1]).sum() if (y_pred[y_test_series == 1]).size > 0 else 0
    fp = (y_pred[y_test_series == 0]).sum() if (y_pred[y_test_series == 0]).size > 0 else 0
    fn = ((y_pred == 1) & (y_test_series == 0)).sum() if ((y_pred == 1) & (y_test_series == 0)).size > 0 else 0
    tn = ((y_pred == 0) & (y_test_series == 0)).sum() if ((y_pred == 0) & (y_test_series == 0)).size > 0 else 0
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else float('nan')
    recall = tp / (tp + fn) if (tp + fn) > 0 else float('nan')
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else float('nan')
    
    try:
        roc_auc = roc_auc_score(y_test_series, y_pred_proba) if y_pred_proba is not None else float('nan')
    except:
        roc_auc = float('nan')
    
    try:
        pr_auc = average_precision_score(y_test_series, y_pred_proba) if y_pred_proba is not None else float('nan')
    except:
        pr_auc = float('nan')
    
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(y_test_series, y_pred)
    
    results[name] = {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'roc_auc': roc_auc,
        'pr_auc': pr_auc,
        'confusion_matrix': cm.tolist(),
        'training_time': elapsed,
        'feature_count': len(feature_names),
        'tp': int(tp),
        'fp': int(fp),
        'fn': int(fn),
        'tn': int(tn),
    }
    
    print(f'Accuracy: {accuracy:.4f}')
    print(f'Precision: {precision:.4f}')
    print(f'Recall: {recall:.4f}')
    print(f'F1: {f1:.4f}')
    print(f'ROC-AUC: {roc_auc:.4f}')
    print(f'PR-AUC: {pr_auc:.4f}')
    print(f'Training time: {elapsed:.2f}s')
    print(f'Confusion Matrix:')
    print(cm)

# Save results
with open(os.path.join(base, 'experiment_results.json'), 'w') as f:
    json.dump(results, f, indent=2, default=float)

print('\nExperiment complete! Results saved to experiment_results.json')

# Also save detailed per-model reports
for name, model in models.items():
    # Get predictions for detailed report
    X_test_trans = X_test[feature_names]
    y_pred = model.predict(X_test_trans)
    
    report = classification_report(y_test, y_pred, target_names=['Not Delayed', 'Delayed'], output_dict=True)
    
    with open(os.path.join(base, f'{name.replace(" ", "_")}_report.json'), 'w') as f:
        json.dump(report, f, indent=2, default=float)
    
    # Save confusion matrix visualization data
    cm = confusion_matrix(y_test, y_pred)
    with open(os.path.join(base, f'{name.replace(" ", "_")}_cm.json'), 'w') as f:
        json.dump({
            'cm': cm.tolist(),
            'labels': ['Not Delayed', 'Delayed'],
            'accuracy': (y_pred == y_test).mean(),
        }, f, indent=2)

print('\nAll experiment files saved!')