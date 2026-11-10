"""Tests for the AeroDelay AI Streamlit application."""
import pytest
import json
import os
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (
    load_artifacts,
    validate_inputs,
    CSS,
    TARGET_COLUMN,
    MODEL_PATH,
    PREPROCESSOR_PATH,
    EVALUATION_PATH,
)


class TestLoadArtifacts:
    """Test that artifacts load correctly and are compatible."""

    def test_model_and_preprocessor_load(self):
        """Both model and preprocessor should load without error."""
        model, preprocessor, eval_metrics = load_artifacts()
        assert model is not None
        assert preprocessor is not None
        assert eval_metrics is not None
        assert "logistic_regression" in eval_metrics

    def test_feature_compatibility(self):
        """Model and preprocessor should have matching feature names."""
        model, preprocessor, eval_metrics = load_artifacts()
        model_feature_names = getattr(model, "feature_names_in_", None)
        preprocessor_feature_names = list(preprocessor.get_feature_names_out())

        if model_feature_names is not None:
            assert (
                model_feature_names
                == preprocessor_feature_names  # type: ignore[comparison]
            ), f"Feature mismatch: {model_feature_names} vs {preprocessor_feature_names}"


class TestValidateInputs:
    """Test input validation logic."""

    def test_valid_inputs_pass(self):
        """Well-formed inputs should pass validation."""
        input_dict = {
            "Airline": "AA",
            "Origin": "JFK",
            "Dest": "LAX",
            "Month": "1",
            "Distance": "2000",
            "CRSDepTime": "1015",
            "Cancelled": "0",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert valid, f"Expected valid inputs to pass, got: {error_msg}"

    def test_missing_value_fails(self):
        """Missing a value should fail validation."""
        input_dict = {
            "Airline": "AA",
            "Origin": "JFK",
            "Dest": "LAX",
            "Month": "",
            "Distance": "2000",
            "CRSDepTime": "1015",
            "Cancelled": "0",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert not valid
        assert "Please provide a value" in error_msg

    def test_invalid_airport_code_fails(self):
        """Invalid airport code should fail validation."""
        input_dict = {
            "Airline": "AA",
            "Origin": "XYZ",  # Invalid
            "Dest": "LAX",
            "Month": "1",
            "Distance": "2000",
            "CRSDepTime": "1015",
            "Cancelled": "0",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert not valid
        assert "Invalid origin airport code" in error_msg

    def test_origin_dest_same_fails(self):
        """Origin and destination being the same should fail."""
        input_dict = {
            "Airline": "AA",
            "Origin": "JFK",
            "Dest": "JFK",  # Same
            "Month": "1",
            "Distance": "2000",
            "CRSDepTime": "1015",
            "Cancelled": "0",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert not valid
        assert "must be different" in error_msg.lower()

    def test_invalid_dep_time_fails(self):
        """Departure time out of range should fail."""
        input_dict = {
            "Airline": "AA",
            "Origin": "JFK",
            "Dest": "LAX",
            "Month": "1",
            "Distance": "2000",
            "CRSDepTime": "2500",
            "Cancelled": "0",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert not valid
        assert "between 0000 and 2359" in error_msg

    def test_invalid_month_fails(self):
        """Month out of range should fail."""
        input_dict = {
            "Airline": "AA",
            "Origin": "JFK",
            "Dest": "LAX",
            "Month": "13",
            "Distance": "2000",
            "CRSDepTime": "1015",
            "Cancelled": "0",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert not valid
        assert "between 1 and 12" in error_msg

    def test_negative_distance_fails(self):
        """Non-positive distance should fail."""
        input_dict = {
            "Airline": "AA",
            "Origin": "JFK",
            "Dest": "LAX",
            "Month": "1",
            "Distance": "-100",
            "CRSDepTime": "1015",
            "Cancelled": "0",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert not valid
        assert "positive number" in error_msg

    def test_cancelled_diverted_invalid_fails(self):
        """Cancelled/Diverted not 0 or 1 should fail."""
        input_dict = {
            "Airline": "AA",
            "Origin": "JFK",
            "Dest": "LAX",
            "Month": "1",
            "Distance": "2000",
            "CRSDepTime": "1015",
            "Cancelled": "2",
            "Diverted": "0",
        }
        valid, error_msg = validate_inputs(input_dict, None)
        assert not valid
        assert "must be 0 or 1" in error_msg


class TestEvaluationMetrics:
    """Test that evaluation metrics are properly structured."""

    def test_evaluation_json_structure(self):
        """Evaluation JSON should have required keys."""
        basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        eval_path = os.path.join(basedir, "reports", "model_evaluation.json")
        assert os.path.exists(eval_path), f"Evaluation file not found: {eval_path}"

        with open(eval_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        # Check logistic regression keys
        lg = metrics.get("logistic_regression", {})
        required_keys = [
            "accuracy",
            "precision_delayed",
            "recall_delayed",
            "f1_delayed",
            "roc_auc",
        ]
        for key in required_keys:
            assert key in lg, f"Missing key '{key}' in logistic_regression metrics"


class TestAppInit:
    """Test application initialization."""

    def test_css_defined(self):
        """CSS should be a non-empty string."""
        assert isinstance(CSS, str)
        assert len(CSS) > 0

    def test_target_column_defined(self):
        """Target column constant should be set."""
        assert TARGET_COLUMN is not None


class TestArtifactPaths:
    """Test that artifact paths are correctly configured."""

    def test_model_path_exists(self):
        """Model path should point to existing file."""
        assert os.path.exists(MODEL_PATH), f"Model not found at {MODEL_PATH}"

    def test_preprocessor_path_exists(self):
        """Preprocessor path should point to existing file."""
        assert os.path.exists(PREPROCESSOR_PATH), f"Preprocessor not found at {PREPROCESSOR_PATH}"

    def test_evaluation_path_exists(self):
        """Evaluation JSON should exist."""
        assert os.path.exists(EVALUATION_PATH), f"Evaluation not found at {EVALUATION_PATH}"

    def test_model_selector_filters_to_existing_joblibs(self):
        """Only model names whose .joblib files exist should be offered in the selector."""
        # This tests the filtering logic used in main()
        MODEL_DIR = Path("artifacts/models")
        JOBLIB_FILES = {f.name.replace(".joblib", "") for f in MODEL_DIR.glob("*.joblib")}

        import json
        with open(EVALUATION_PATH) as f:
            eval_metrics = json.load(f)

        available_models = [
            name for name in eval_metrics.keys() if name in JOBLIB_FILES
        ]
        available_models.sort()

        # 'dummy' should be excluded because dummy.joblib does not exist
        # (only dummy_classifier.joblib exists)
        assert "dummy" not in available_models, "dummy should be filtered out"

        # 'logistic_regression' and 'linearsvc' should be included
        assert "logistic_regression" in available_models
        assert "linearsvc" in available_models

    def test_model_selector_empty_guard(self):
        """If no models have matching .joblib files, app should show a message and stop."""
        import json
        from pathlib import Path

        # Temporarily modify eval_metrics to have keys that don't match joblib files
        with open(EVALUATION_PATH) as f:
            original_eval = json.load(f)

        # Write a modified eval_metrics with keys that don't match any .joblib files
        modified_eval = {"nonexistent_model1", "nonexistent_model2"}  # use set to avoid dict issues
        # Actually, we need a dict; use arbitrary keys
        modified_eval_dict = {
            "model_xyz": {"accuracy": 0, "precision_delayed": 0, "recall_delayed": 0, "f1_delayed": 0, "roc_auc": 0},
            "model_abc": {"accuracy": 0, "precision_delayed": 0, "recall_delayed": 0, "f1_delayed": 0, "roc_auc": 0},
        }
        with open(EVALUATION_PATH, "w") as f:
            json.dump(modified_eval_dict, f)

        try:
            # Run the filtering logic as in main()
            MODEL_DIR = Path("artifacts/models")
            JOBLIB_FILES = {f.name.replace(".joblib", "") for f in MODEL_DIR.glob("*.joblib")}
            available_models = [
                name for name in modified_eval_dict.keys() if name in JOBLIB_FILES
            ]
            available_models.sort()
            # If available_models is empty, the app calls st.stop()
            assert len(available_models) == 0, "Expected empty available_models with modified eval_metrics"
        finally:
            # Restore original eval_metrics
            with open(EVALUATION_PATH, "w") as f:
                json.dump(original_eval, f)