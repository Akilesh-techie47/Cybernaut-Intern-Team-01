import joblib, os, numpy as np

base = r'D:\Cybernaut intern\Big project (month-2)'

# Try loading the logistic_regression model
model_path = os.path.join(base, 'artifacts', 'models', 'logistic_regression.joblib')
print(f'Loading: {model_path}')
try:
    m = joblib.load(model_path)
    print(f'Type: {type(m).__name__}')
    has_predict = hasattr(m, 'predict')
    has_predict_proba = hasattr(m, 'predict_proba')
    print(f'Has predict: {has_predict}')
    print(f'Has predict_proba: {has_predict_proba}')
    # Try a simple predict
    X_test = np.random.rand(1, 654)
    try:
        pred = m.predict(X_test)
        print(f'Predict result: {pred}')
    except Exception as e2:
        print(f'Predict error: {str(e2)[:100]}')
except Exception as e:
    print(f'Error loading: {type(e).__name__}: {str(e)[:200]}')