import os, json
base = r'D:\Cybernaut intern\Big project (month-2)'
print('Model artifacts:')
for f in os.listdir(os.path.join(base, 'models')):
    full = os.path.join(base, 'models', f)
    print(f'  {f}: {os.path.getsize(full)} bytes')
print()
print('Artifacts:')
for f in os.listdir(os.path.join(base, 'artifacts', 'models')):
    full = os.path.join(base, 'artifacts', 'models', f)
    print(f'  {f}: {os.path.getsize(full)} bytes')
print()
print('Experiment results:')
with open(os.path.join(base, 'experiment_results.json'), 'r') as f:
    results = json.load(f)
    for model, metrics in results.items():
        print(f'  {model}: accuracy={metrics["accuracy"]:.4f}, precision={metrics["precision"]:.4f}, recall={metrics["recall"]:.4f}, f1={metrics["f1"]:.4f}, roc_auc={metrics["roc_auc"]:.4f}, pr_auc={metrics["pr_auc"]:.4f}, training_time={metrics["training_time"]:.2f}s')