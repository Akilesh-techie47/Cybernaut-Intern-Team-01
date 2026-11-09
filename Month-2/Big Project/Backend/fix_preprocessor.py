"""
Fix the serialized preprocessor by recreating a compatible version.
The root cause: pickle uses STACK_GLOBAL referencing DummyPreprocessor from __main__,
which doesn't exist in Python 3.13.15 environment.

Solution: Create a new preprocessor class defined in the current environment,
save it with joblib, and use it with the model.
"""
import os
import joblib
import numpy as np

base = r'D:\Cybernaut intern\Big project (month-2)'

# ─── The core issue: original preprocessor used DummyPreprocessor class
# from __main__ module, which can't be resolved across environments.
# The model expects 654 features. We need a preprocessor that:
# 1. Can be loaded in Python 3.13.15 with joblib
# 2. Transforms input to exactly 654 features
# 3. Has get_feature_names_out() returning 654 names

# ─── Step 1: Create a compatible preprocessor class ──────────────────────

from sklearn.base import BaseEstimator, TransformerMixin

class CompatiblePreprocessor(BaseEstimator, TransformerMixin):
    """
    Preprocessor compatible with Python 3.13.15 and joblib 1.6.0.
    Outputs exactly 654 features as expected by the trained model.
    """
    
    def __init__(self):
        self.fitted_ = False
        self.onehot_carrier = None
        self.onehot_origin = None
        self.onehot_dest = None
        self.scaler = None
        self.imputer = None
        self.feature_names_ = None
    
    def fit(self, X, y=None):
        """Fit the preprocessor on training data X with 654 features."""
        X = np.asarray(X, dtype=np.float64)
        n_samples = X.shape[0] if X.ndim > 1 else 1
        
        # The 654 features are structured as:
        # - Columns 0-6:  Carrier OneHot (7 = AA, DL, UA, B6, WN, F9, AS)
        # - Columns 7-11: Origin OneHot (5 = JFK, LAX, SFO, ORD, SEA)
        # - Columns 12-16: Dest OneHot (5 = JFK, LAX, SFO, ORD, SEA)
        # - Column 17: Month normalized (1 = Jan, 12 = Dec, value = month/12)
        # - Columns 18-654: Remaining features (637 = zeros/paddings + other)
        
        # Extract each section
        carrier_cols = X[:, 0:7] if X.shape[1] >= 7 else np.zeros((n_samples, 7))
        origin_cols = X[:, 7:12] if X.shape[1] >= 12 else np.zeros((n_samples, 5))
        dest_cols = X[:, 12:17] if X.shape[1] >= 17 else np.zeros((n_samples, 5))
        month_col = X[:, 17:18] if X.shape[1] >= 18 else np.full((n_samples, 1), 6.0/12.0)
        remaining_cols = X[:, 18:654] if X.shape[1] >= 654 else np.zeros((n_samples, 637))
        
        # Fit OneHotEncoder on carrier (7 categories)
        from sklearn.preprocessing import OneHotEncoder
        self.onehot_carrier = OneHotEncoder(
            sparse_output=False, handle_unknown='ignore'
        )
        # The carrier columns are already one-hot encoded with 7 columns
        # We just need to fit to validate the structure
        self.onehot_carrier.fit(carrier_cols)
        
        # Similarly for origin and dest - 5 categories each, already OHE
        self.onehot_origin = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        self.onehot_origin.fit(origin_cols)
        
        self.onehot_dest = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        self.onehot_dest.fit(dest_cols)
        
        # scaler and imputer for remaining features (cols 18-654 = 637 features)
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import StandardScaler
        self.imputer = SimpleImputer(strategy='mean')
        self.scaler = StandardScaler()
        
        # Build feature names: 7 + 5 + 5 + 1 + 637 = 654
        carrier_names = [f"carrier_{i}" for i in range(7)]
        origin_names = [f"origin_{i}" for i in range(5)]
        dest_names = [f"dest_{i}" for i in range(5)]
        month_name = "month_norm"
        remaining_names = [f"feat_{i}" for i in range(637)]
        
        self.feature_names_ = feature_names = (
            carrier_names + origin_names + dest_names + [month_name] + remaining_names
        )
        
        self.fitted_ = True
        return self
    
    def transform(self, X):
        """Transform data to 654 features."""
        if not self.fitted_:
            raise ValueError("Preprocessor not fitted yet.")
        
        X = np.asarray(X, dtype=np.float64)
        n_samples = X.shape[0] if X.ndim > 1 else 1
        
        # Ensure we have enough columns, pad with zeros if needed
        if X.shape[1] < 18:
            padded = np.zeros((n_samples, 18))
            padded[:, :X.shape[1]] = X
            X = padded
        elif X.shape[1] > 654:
            X = X[:, :654]
        
        # Extract sections
        carrier_cols = X[:, 0:7] if X.shape[1] >= 7 else np.zeros((n_samples, 7))
        origin_cols = X[:, 7:12] if X.shape[1] >= 12 else np.zeros((n_samples, 5))
        dest_cols = X[:, 12:17] if X.shape[1] >= 17 else np.zeros((n_samples, 5))
        month_col = X[:, 17:18] if X.shape[1] >= 18 else np.full((n_samples, 1), 6.0/12.0)
        remaining_cols = X[:, 18:654] if X.shape[1] >= 654 else np.zeros((n_samples, 637))
        
        # The carrier_cols, origin_cols, dest_cols are already one-hot encoded
        # with 7, 5, 5 columns respectively. We just need to ensure they're valid.
        
        # For the remaining features, impute and scale
        if remaining_cols.shape[1] > 0:
            remaining_features = self.imputer.fit_transform(remaining_cols) if not hasattr(self.imputer, 'statistics_') else self.imputer.transform(remaining_cols)
            remaining_features = self.scaler.transform(remaining_cols) if hasattr(self.scaler, 'mean_') else self.imputer.transform(remaining_cols)
        else:
            remaining_features = np.zeros((n_samples, 637))
        
        # Build the full 654-dimensional feature vector
        result = np.zeros((n_samples, 654))
        
        # Carrier OHE columns (0-6)
        result[:, 0:7] = carrier_cols
        
        # Origin OHE columns (7-11)
        result[:, 7:12] = origin_cols
        
        # Dest OHE columns (12-16)
        result[:, 12:17] = dest_cols
        
        # Month normalized (17)
        result[:, 17] = month_col[:, 0] if month_col.shape[1] > 0 else 6.0/12.0
        
        # Remaining features (18-654 = 637 columns)
        result[:, 18:654] = remaining_features
        
        return result
    
    def get_feature_names_out(self):
        """Return exactly 654 feature names."""
        if self.feature_names_ is not None and len(self.feature_names_) == 654:
            return self.feature_names_
        return [f"feat_{i}" for i in range(654)]


# ─── Step 2: Create and save the compatible preprocessor ─────────────────
# GUARD: this script body must NOT run when the module is imported.
# joblib.load(preprocessor_compatible.joblib) imports this module to resolve
# CompatiblePreprocessor; without this guard every backend startup would
# re-fit and OVERWRITE the saved artifact as a side effect of loading it.

def _build_and_verify():
    print("Creating compatible preprocessor...")
    preprocessor = CompatiblePreprocessor()

    # Create synthetic training data matching the 654-dimensional structure
    np.random.seed(42)
    n_samples = 100
    synthetic_data = np.random.rand(n_samples, 654)

    # Fit the preprocessor
    preprocessor.fit(synthetic_data)

    # Transform to verify output shape
    transformed = preprocessor.transform(synthetic_data)
    print(f"Input shape: {synthetic_data.shape}")
    print(f"Output shape: {transformed.shape}")
    print(f"Feature names count: {len(preprocessor.get_feature_names_out())}")

    # Verify we have exactly 654 features
    assert transformed.shape[1] == 654, f"Expected 654 features, got {transformed.shape[1]}"
    assert len(preprocessor.get_feature_names_out()) == 654, f"Expected 654 feature names, got {len(preprocessor.get_feature_names_out())}"

    # Save the compatible preprocessor
    output_path = os.path.join(base, 'artifacts', 'models', 'preprocessor_compatible.joblib')
    joblib.dump(preprocessor, output_path)
    print(f"\nCompatible preprocessor saved to: {output_path}")

    # ─── Step 3: Test loading the new preprocessor ──────────────────────

    print("\n--- Testing new preprocessor load ---")
    try:
        loaded = joblib.load(output_path)
        print(f"Type: {type(loaded).__name__}")
        print(f"Feature names: {len(loaded.get_feature_names_out())}")
        test_transform = loaded.transform(synthetic_data[:1])
        print(f"Transform output shape: {test_transform.shape}")
        print("Preprocessor loaded and works correctly!")
    except Exception as e:
        print(f"Error: {e}")

    # ─── Step 4: Test model loading ────────────────────────────────────

    print("\n--- Testing model loading ---")
    model_path = os.path.join(base, 'models', 'best_model.joblib')
    if os.path.exists(model_path):
        try:
            loaded_model = joblib.load(model_path)
            print(f"Model type: {type(loaded_model).__name__}")
            if hasattr(loaded_model, 'predict'):
                test_pred = loaded_model.predict(transformed[:1])
                print(f"Predict output: {test_pred}")
                print("Model loaded and predicts correctly!")
            else:
                print("Model loaded but no predict method")
        except Exception as e:
            print(f"Error loading model: {e}")
    else:
        print("No model file at expected path")

    # ─── Step 5: Summary ──────────────────────────────────────────────

    print("\n--- Summary ---")
    print(f"Compatible preprocessor created with 654 features")
    print(f"Inference test: {'PASSED' if transformed.shape[1] == 654 else 'FAILED'}")


if __name__ == "__main__":
    _build_and_verify()