import json
from pathlib import Path

# Read the evaluation metrics
with open('reports/model_evaluation.json') as f:
    eval_metrics = json.load(f)

print('=== Model Comparison ===')
for model_name, metrics in eval_metrics.items():
    print(f'{model_name}:')
    print(f'  Accuracy: {metrics["accuracy"]:.4f}')
    print(f'  Precision: {metrics["precision_delayed"]:.4f}')
    print(f'  Recall: {metrics["recall_delayed"]:.4f}')
    print(f'  F1: {metrics["f1_delayed"]:.4f}')
    print(f'  ROC-AUC: {metrics["roc_auc"]}')
    print()

# Check the actual joblib files
from pathlib import Path
models_dir = Path('artifacts/models')
joblib_files = sorted([f.name for f in models_dir.glob('*.joblib')])
print(f'Actual joblib files: {joblib_files}')

# Key files to examine
print('\nKey files to examine:')
print('- src/preprocess.py (preprocessing pipeline)')
print('- app.py (model loading and selection)')