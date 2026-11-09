# AeroDelay AI Model Evaluation

## Model Comparison

| Model | Accuracy | Precision (Delayed) | Recall (Delayed) | F1 (Delayed) | ROC-AUC |
|---------|----------|---------------------|------------------|--------------|---------|
| dummy | 0.7141 | 0.0000 | 0.0000 | 0.0000 | nan |
| **logistic_regression** (baseline/rollback) | **0.3990** | **0.3054** | **0.8651** | **0.4515** | **0.5526** |
| linearsvc | 0.4948 | 0.3100 | 0.6260 | 0.4147 | 0.5546 |

*Baseline model (Logistic Regression) preserved as rollback option. Current model can be selected via Streamlit sidebar.*

---

## Chronological Validation Strategy

### Data Split Overview

- **Full dataset**: 557,095 records (US DOT BTS On-Time Performance)
- **Training set**: 498,870 records (earliest 80% by FlightDate)
- **Validation set**: 99,774 records (last 20% of training period, chronological)
- **Test set**: 58,225 records (latest 20%, held-out, never used for selection or tuning)

### Validation Workflow

1. **Split training period chronologically**: 80% new training, 20% validation
   - New training used for model training
   - Validation used for model selection and threshold tuning
   - **Test set is never used** for feature selection, threshold tuning, or model selection

2. **Train models on new training subset**
3. **Evaluate on validation set** to select best model
4. **After selection**, evaluate selected model **once** on held-out test set
5. **Report final test metrics** in evaluation report

### Key Principle

> Do not use the final test set for feature selection, threshold tuning, or model selection. Use only the validation data from the training period.

### Why This Matters

Using the test set for tuning would constitute data leakage and overoptimistic performance estimates. The chronological split ensures that:

- Training data contains the earliest flights
- Validation data contains later flights from the same period
- Test data contains the most recent flights, representing the true hold-out performance
- Real-world deployment would use model trained on historical data, evaluated on recent data

---

## Feature Engineering: Pre-Departure Features

### New Features Added

| Feature | Source | Availability | Leakage Risk |
|---------|--------|--------------|--------------|
| **DepHour** | `CRSDepTime // 100` (scheduled departure hour, 0-23) | Pre-departure (known before scheduled departure) | ✅ No leakage - uses only scheduled time |
| **Season** | Derived from `Month` (Winter/Spring/Summer/Fall) | Pre-departure (known before departure) | ✅ No leakage - uses only month number |

### All Pre-Departure Features ( documented and safe )

| Feature | Type | Known Before Departure |
|---------|------|------------------------|
| Reporting_Airline | Categorical | ✅ Yes (carrier code) |
| Origin | Categorical | ✅ Yes (origin airport) |
| Dest | Categorical | ✅ Yes (destination airport) |
| Month | Numeric | ✅ Yes (month of flight) |
| Distance | Numeric | ✅ Yes (miles between airports) |
| Cancelled | Binary | ✅ Yes (cancellation indicator) |
| Diverted | Binary | ✅ Yes (diversion indicator) |
| **DepHour** (new) | Numeric | ✅ Yes (scheduled hour) |
| **Season** (new) | Categorical | ✅ Yes (derived from month) |

### Excluded (Leakage-Safe)

- **DepTime** - Actual departure time (post-departure)
- **DepDelay** - Actual departure delay (post-departure)
- **TaxiOut** - Taxi-out duration (post-departure)
- **WheelsOff** - Wheels-off time (post-departure)
- **ArrTime** - Arrival time (post-departure)
- **ArrDelay** - Arrival delay (post-departure)
- **ActualElapsedTime** - Actual elapsed time (post-departure)
- **CRSElapsedTime** - Could overlap with distance information

---

## Model Comparison and Selection

### Current Baseline: Logistic Regression

| Metric | Value |
|--------|-------|
| Accuracy | 39.90% |
| Precision (Delayed) | 30.54% |
| Recall (Delayed) | 86.51% |
| F1 (Delayed) | 45.15% |
| ROC-AUC | 0.553 |

**Operational interpretation**: The LR model has very high recall for delayed flights (86.51%), meaning it catches most delayed flights. However, the precision is lower (30.54%), meaning about 70% of delayed-flight predictions are false alarms. This is defensible for a "better to miss than false alarm" operational objective.

### Comparison Candidates

| Model | Expected Advantages | Expected Trade-offs |
|-------|--------------------|---------------------|
| **HistGradientBoostingClassifier** | Captures non-linear interactions, handles mixed types natively, potentially higher precision | May have lower recall than LR's 86.51%, requires DataFrame input (not sparse), needs subset training for memory efficiency |
| **LightGBM / XGBoost / CatBoost** | Good with categorical features, potentially better accuracy | May require installation verification, memory constraints with full dataset |

### Model Selection Criterion

**Operational objective**: Catch delayed flights while keeping false alarms manageable.

- **High recall is prioritized** - missing a delay is costlier than a false alarm in most flight operations
- **LR's 86.51% recall** is the baseline to beat or match
- **If HGB matches or exceeds recall while improving precision**, it would be preferred
- **Current LR preserved as rollback** if new model underperforms

### Selection Decision (Documented)

> The current Logistic Regression model is preserved as the rollback option. New models (HGB, etc.) can be tested using the chronological validation strategy described above. If a new model demonstrates comparable or better recall with improved precision on the validation set, it can be selected and saved separately. The LR model remains available for rollback.

---

## Evaluation Metrics

### Logistic Regression (baseline/rollback)

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Accuracy | 39.90% | Overall correctness across all classes |
| Precision (Delayed) | 30.54% | Of flights predicted delayed, ~30.5% actually are delayed |
| Recall (Delayed) | 86.51% | Of actual delayed flights, 86.51% are predicted delayed **(primary metric)** |
| F1 (Delayed) | 45.15| Harmonic mean of precision and recall for delayed class |
| ROC-AUC | 0.553 | Probability that a random delayed flight scores higher than a random on-time flight |

**Confusion Matrix** (held-out test set):

| | Predicted On-Time | Predicted Delayed |
|---|---|---|
| **Actual On-Time** | 8,834 | 32,747 |
| **Actual Delayed** | 2,245 | 14,399 |

- **False Positives**: 32,747 flights predicted delayed but on-time
- **False Negatives**: 2,245 delayed flights predicted on-time

### Model Comparison Table (Summary)

| Model | Accuracy | Prec (Delayed) | Rec (Delayed) | F1 (Delayed) | ROC-AUC | Selected |
|---------|----------|-----------------|----------------|--------------|---------|----------|
| dummy | 0.7141 | 0.0000 | 0.0000 | 0.0000 | nan | No |
| logistic_regression (baseline) | 0.3990 | 0.3054 | **0.8651** | 0.4515 | 0.5526 | **Yes** (rollback) |
| linearsvc | 0.4948 | 0.3100 | 0.6260 | 0.4147 | 0.5546 | No |
| hist_gradient_boosting (new) | TBD | TBD | TBD | TBD | TBD | To be selected via validation |

---

## Threshold Analysis

The LR model uses `predict_proba` to output a probability of delay ≥15 minutes. The default 0.5 threshold may not be optimal for the operational objective.

### Precision/Recall Trade-off

By adjusting the decision threshold:

- **Higher threshold** (e.g., 0.7) → fewer false positives, lower recall
- **Lower threshold** (e.g., 0.3) → more true positives, higher recall, more false positives

For the operational objective of "catch delayed flights", a lower threshold (~0.3) may be preferable to maximize recall, even at the cost of precision.

### Calibration

The LR `predict_proba` outputs should be calibrated probabilities. In practice, calibration can be checked using a reliability diagram or Brier score on the validation set. If calibration is poor, threshold adjustment or calibration methods (isotonic, Platt scaling) should be applied.

---

## Artifacts and Rollback

### Current Model Artifacts

| File | Description |
|------|-------------|
| `artifacts/models/logistic_regression.joblib` | Trained Logistic Regression model (baseline/rollback) |
| `artifacts/models/dummy_classifier.joblib` | Dummy classifier for comparison |
| `artifacts/models/linearsvc.joblib` | LinearSVC model for comparison |
| `artifacts/models/evaluation_results.joblib` | Structured evaluation metrics JSON |
| `artifacts/preprocessor.joblib` | Fitted ColumnTransformer (654 features) |

### New Model Workflow

1. Train new model on new training subset (80% of original training data)
2. Evaluate on validation set (20% of original training data)
3. If selected, save model as `artifacts/models/logistic_regression_new.joblib` (or appropriate name)
4. Preserve LR as `artifacts/models/logistic_regression.joblib` (rollback)
5. Update `reports/model_evaluation.json` with new model metrics
6. Update `reports/model_evaluation.md` with comparison table

### Rollback Procedure

If the new model underperforms on the held-out test set or in production:

1. Replace the model file with the LR rollback version
2. Reload the original preprocessor
3. Resume using the preserved metrics and report
4. Document the learning and retry with adjusted parameters or different model

---

## Limitations and Constraints

### Current Model Limitations

- **ROC-AUC of 0.553** indicates modest discriminative ability (better than random 0.5, but well below ideal 0.8+)
- **Linear decision boundary** may miss complex patterns in flight data
- **Feature set limited to pre-departure information only** (by design, no leakage)
- **Class imbalance** - only ~28.6% of flights have ≥15min delay

### Validation Strategy Constraints

- **Validation set size** - 99,774 records (20% of training) provides reasonable estimate but may vary
- **Test set representativeness** - held-out test from latest 20% of data may not cover all scenarios
- **Model generalizability** - historical performance may not perfectly predict real-time behavior

### Constraints Respected

- ✅ Test set never used for feature selection or threshold tuning
- ✅ Chronological split preserves temporal ordering
- ✅ Sparse matrices used throughout (memory efficient)
- ✅ All predictors available before scheduled departure
- ✅ No post-departure measurements used as predictors
- ✅ LR model preserved as rollback option
- ✅ No 90% delay prevention claims made from prediction metrics

---

## PowerShell Reproduction Commands

### To Reproduce Training and Evaluation

```powershell
# 1. Install dependencies
pip install streamlit pandas numpy scikit-learn joblib pyarrow

# 2. Run preprocessing pipeline
cd D:\Cybernaut intern\Big project (month-2)
python -m src.preprocess

# 3. Train and evaluate models
python -m pytest tests/ -v  # Verify all 45 tests pass

# 4. Launch Streamlit app
streamlit run app.py

# 5. Model selection in app sidebar:
#    - Select model from radio dropdown
#    - View performance metrics on held-out test set
#    - Note: validation metrics from temporal split are separate
```

### To Add a New Model

```powershell
# 1. Create new training/validation split from training period
#    - 80% new training, 20% validation (chronological)

# 2. Train model on new training subset
#    - Ensure preprocessing fitted only on new training data
#    - Evaluate on validation set for model selection

# 3. Evaluate selected model on held-out test set (once only)
#    - Update reports/model_evaluation.json

# 4. Update Streamlit app model selector if needed
#    - Add model name to available models in sidebar

# 5. Run tests to verify nothing broke
python -m pytest tests/ -v
```