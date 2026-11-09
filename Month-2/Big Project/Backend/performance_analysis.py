import json

with open('reports/model_evaluation.json') as f:
    eval_metrics = json.load(f)

print('=== Model Performance Summary ===')
for model_name, metrics in eval_metrics.items():
    print(f'\n{model_name.upper()}:')
    print(f'  Accuracy:  {metrics["accuracy"]:.4f}')
    print(f'  Precision (Delayed): {metrics["precision_delayed"]:.4f}')
    print(f'  Recall (Delayed): {metrics["recall_delayed"]:.4f}')
    print(f'  F1 (Delayed): {metrics["f1_delayed"]:.4f}')
    roc_auc = metrics.get("roc_auc")
    if roc_auc is not None:
        print(f'  ROC-AUC: {roc_auc:.4f}')
    else:
        print(f'  ROC-AUC: N/A')
    cm = metrics['confusion_matrix']
    print(f'  Confusion Matrix:')
    print('                Predicted Delayed  Predicted On-time')
    print(f'    Actual Delayed:        {cm[1][0]:>12} {cm[1][1]:>14}')
    print(f'    Actual On-time:        {cm[0][0]:>12} {cm[0][1]:>14}')

import pandas as pd
df = pd.read_csv('data/raw/On_Time_Reporting_Carrier_On_Time_Performance_2022_12.zip_raw.csv', dtype=str, nrows=5000)
delayed = (df['DepDel15'] == '1').sum()
ontime = (df['DepDel15'] == '0').sum()
total = len(df)
print(f'\n\n=== Dataset Class Imbalance (first {total} rows) ===')
print(f'Delayed flights: {delayed} ({delayed/total*100:.1f}%)')
print(f'On-time flights: {ontime} ({ontime/total*100:.1f}%)')
print(f'Imbalance ratio: {ontime/delayed:.1f}:1')