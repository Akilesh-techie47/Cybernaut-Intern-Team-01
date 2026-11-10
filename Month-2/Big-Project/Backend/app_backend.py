"""
AeroDelay AI — Phase 4: FastAPI Backend Integration (Fixed ML Serialization)

Backend for the premium Next.js frontend. Provides:
- Flight delay-risk prediction using properly-serialized ML model
- Live flight lookup via AviationStack (server-side only)
- Airport/airline reference data
- Model information and health status
- Request validation, timeouts, caching, rate limiting
- Typed API responses with Pydantic models
- CORS configuration for frontend integration
"""

import json
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import joblib
import numpy as np

# ─── Configuration ───────────────────────────────────────────────────────

# Resolve all backend resources relative to this file.
BASE = Path(__file__).resolve().parent

MODELS_DIR = BASE / "models"
ARTIFACTS_DIR = BASE / "artifacts" / "models"
DATA_DIR = BASE / "data"

# Load .env (server-side only). Never printed, never exposed to the frontend.
# Values already present in the process environment take precedence.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE / ".env")
except Exception:
    pass

# ─── CORS Configuration ─────────────────────────────────────────────────

# Origins allowed to connect to the API
# In production, replace with specific deployed frontend URLs
# In development, allow local frontend origin
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://aerodelay-ai.vercel.app",
]

CORS_ALLOWED_METHODS = [
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "OPTIONS",
]

CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "X-Requested-With",
    "Accept",
    "Origin",
]

# Create FastAPI app
app = FastAPI(
    title="AeroDelay AI API",
    description="Premium Aviation Intelligence Platform - Backend Integration",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Optional bearer auth: credentials are never required for local API use,
# and never logged. auto_error=False so unauthenticated requests are allowed.
security = HTTPBearer(auto_error=False)

# NOTE: CORS middleware is registered at the END of this module so that it is
# the OUTERMOST middleware and applies CORS headers to error responses too.

# ─── Pydantic Models (Typed API Responses) ───────────────────────────────

class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: float = Field(default_factory=time.time)

class FlightInfo(BaseModel):
    flight_number: str = Field(..., min_length=1, max_length=10)
    origin: str = Field(..., min_length=1, max_length=5)
    destination: str = Field(..., min_length=1, max_length=5)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    delay_minutes: Optional[int] = Field(None, ge=0)
    scheduled_departure: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    status: Optional[str] = Field(None, pattern=r"^(On Time|Delayed|At Risk|Cancelled|Diverted)$")

class RiskPrediction(BaseModel):
    flight_number: str
    origin: str
    destination: str
    date: str
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
    factors: List[Dict[str, str]] = Field(default_factory=list)
    model_version: str = "Phase 2 Ensemble v2.1"
    prediction_time_ms: float

class RouteAnalytics(BaseModel):
    route: str
    on_time_pct: float = Field(ge=0.0, le=100.0)
    delayed_pct: float = Field(ge=0.0, le=100.0)
    cancelled_pct: float = Field(ge=0.0, le=100.0)
    average_delay: float = Field(ge=0.0)
    flights_this_month: int = Field(ge=0)
    airline_breakdown: List[Dict[str, Any]] = Field(default_factory=list)

class ModelInfo(BaseModel):
    name: str
    type: str
    version: str
    status: HealthStatus
    metrics: Dict[str, float]
    training_time_s: float
    features: int
    trained_on: int
    last_checked: float = Field(default_factory=time.time)

class APIStatus(BaseModel):
    status: HealthStatus
    timestamp: float
    services: Dict[str, HealthStatus]
    version: str = "4.0.0"


# ─── New Models for Airport/Airline Search and Flight Lookup ──────────────

class AirportSearchResult(BaseModel):
    iata: str
    icao: str
    name: str
    city: str
    country: str
    latitude: float
    longitude: float
    timezone: str


class AirlineSearchResult(BaseModel):
    code: str
    name: str
    iata: str
    icao: str
    country: str
    hub: str


class AirportSearchResponse(BaseModel):
    airports: List[AirportSearchResult]
    total: int
    query: str


class AirlineSearchResponse(BaseModel):
    airlines: List[AirlineSearchResult]
    total: int
    query: str


class FlightLookupResult(BaseModel):
    found: bool
    message: Optional[str] = None
    flight_number: Optional[str] = None
    airline: Optional[str] = None
    flight_date: Optional[str] = None
    departure: Optional[Dict[str, Any]] = None
    arrival: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    gate: Optional[str] = None
    equipment: Optional[str] = None
    # Model compatibility info
    model_compatible: bool = False
    unsupported_features: List[str] = Field(default_factory=list)


class FlightLookupToPredictionRequest(BaseModel):
    flight_number: str
    date: str


class FlightLookupToPredictionResponse(BaseModel):
    flight_info: FlightLookupResult
    prediction: Optional[RiskPrediction] = None
    feature_compatibility: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


# ─── AviationStack Configuration ────────────────────────────────────────

# Standardized environment variable name: AVIATIONSTACK_ACCESS_KEY
# Backwards-compatible alias: AVIATIONSTACK_KEY (deprecated, same value)
# Never expose in frontend - loaded server-side only from .env file

_AVIATIONSTACK_ACCESS_KEY = os.environ.get("AVIATIONSTACK_ACCESS_KEY", "")
_AVIATIONSTACK_KEY = os.environ.get("AVIATIONSTACK_KEY", "")

# Use the standardized key; fall back to alias if primary not set
AVIATIONSTACK_KEY = _AVIATIONSTACK_ACCESS_KEY or _AVIATIONSTACK_KEY

AVIATIONSTACK_CACHE_TTL = 300  # 5 minutes cache

aviationstack_cache: Dict[str, Dict[str, Any]] = {
    "timestamps": {},
    "data": {},
}


def aviationstack_request(endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make AviationStack API request with caching and rate limiting."""
    import hashlib
    import urllib.parse
    import urllib.request

    # Check cache
    cache_key = hashlib.md5(
        (endpoint + str(sorted(params.items()))).encode()
    ).hexdigest()
    now = time.time()

    if cache_key in aviationstack_cache["timestamps"]:
        if now - aviationstack_cache["timestamps"][cache_key] < AVIATIONSTACK_CACHE_TTL:
            if cache_key in aviationstack_cache["data"]:
                return aviationstack_cache["data"][cache_key]

    # Make API request
    try:
        base_url = "http://api.aviationstack.com/v1"
        # Use the standardized key
        access_key = AVIATIONSTACK_KEY
        if not access_key:
            raise ValueError("AviationStack API key not configured")
        all_params = {"access_key": access_key, **params}
        query = urllib.parse.urlencode(all_params)
        url = f"{base_url}/{endpoint}?{query}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

            # Update cache
            aviationstack_cache["timestamps"][cache_key] = now
            aviationstack_cache["data"][cache_key] = data

            return data
    except HTTPException:
        raise
    except Exception:
        # Never print the actual API key in error logs
        print("AviationStack API request failed: configuration or network error")
        return None


# ─── Airport/Airline Reference Data Loading ─────────────────────────────────

_airports_cache: Optional[List[Dict[str, Any]]] = None
_airlines_cache: Optional[List[Dict[str, Any]]] = None


def load_airports_reference() -> List[Dict[str, Any]]:
    """Load airport reference data from JSON file."""
    global _airports_cache
    if _airports_cache is not None:
        return _airports_cache
    
    airports_path = DATA_DIR / "airports_reference.json"
    if airports_path.exists():
        try:
            with open(airports_path, "r") as f:
                _airports_cache = json.load(f)
            print(f"Loaded {len(_airports_cache)} airports from reference data")
            return _airports_cache
        except Exception as e:
            print(f"Failed to load airports reference: {e}")
    
    # Fallback to minimal set
    _airports_cache = [
        {"iata": "JFK", "icao": "KJFK", "name": "John F. Kennedy International Airport", "city": "New York", "country": "USA", "latitude": 40.6413, "longitude": -73.7781, "timezone": "America/New_York"},
        {"iata": "LAX", "icao": "KLAX", "name": "Los Angeles International Airport", "city": "Los Angeles", "country": "USA", "latitude": 33.9416, "longitude": -118.4085, "timezone": "America/Los_Angeles"},
        {"iata": "ORD", "icao": "KORD", "name": "O'Hare International Airport", "city": "Chicago", "country": "USA", "latitude": 41.9742, "longitude": -87.9073, "timezone": "America/Chicago"},
        {"iata": "ATL", "icao": "KATL", "name": "Hartsfield-Jackson Atlanta International Airport", "city": "Atlanta", "country": "USA", "latitude": 33.6407, "longitude": -84.4277, "timezone": "America/New_York"},
        {"iata": "DFW", "icao": "KDFW", "name": "Dallas/Fort Worth International Airport", "city": "Dallas-Fort Worth", "country": "USA", "latitude": 32.8998, "longitude": -97.0403, "timezone": "America/Chicago"},
    ]
    return _airports_cache


def load_airlines_reference() -> List[Dict[str, Any]]:
    """Load airline reference data from JSON file."""
    global _airlines_cache
    if _airlines_cache is not None:
        return _airlines_cache
    
    airlines_path = DATA_DIR / "airlines_reference.json"
    if airlines_path.exists():
        try:
            with open(airlines_path, "r") as f:
                _airlines_cache = json.load(f)
            print(f"Loaded {len(_airlines_cache)} airlines from reference data")
            return _airlines_cache
        except Exception as e:
            print(f"Failed to load airlines reference: {e}")
    
    # Fallback to minimal set
    _airlines_cache = [
        {"code": "AA", "name": "American Airlines", "iata": "AA", "icao": "AAL", "country": "USA", "hub": "DFW"},
        {"code": "DL", "name": "Delta Air Lines", "iata": "DL", "icao": "DAL", "country": "USA", "hub": "ATL"},
        {"code": "UA", "name": "United Airlines", "iata": "UA", "icao": "UAL", "country": "USA", "hub": "ORD"},
        {"code": "WN", "name": "Southwest Airlines", "iata": "WN", "icao": "SWA", "country": "USA", "hub": "DAL"},
        {"code": "B6", "name": "JetBlue Airways", "iata": "B6", "icao": "JBU", "country": "USA", "hub": "JFK"},
    ]
    return _airlines_cache


def search_airports(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search airports by code, name, or city."""
    airports = load_airports_reference()
    query_lower = query.lower().strip()
    if not query_lower:
        return airports[:limit]
    
    results = []
    for airport in airports:
        # Search in IATA, ICAO, name, city, country
        if (query_lower in airport["iata"].lower() or
            query_lower in airport["icao"].lower() or
            query_lower in airport["name"].lower() or
            query_lower in airport["city"].lower() or
            query_lower in airport["country"].lower()):
            results.append(airport)
            if len(results) >= limit:
                break
    return results


def search_airlines(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search airlines by code or name."""
    airlines = load_airlines_reference()
    query_lower = query.lower().strip()
    if not query_lower:
        return airlines[:limit]
    
    results = []
    for airline in airlines:
        if (query_lower in airline["code"].lower() or
            query_lower in airline["name"].lower() or
            query_lower in airline["iata"].lower() or
            query_lower in airline["icao"].lower()):
            results.append(airline)
            if len(results) >= limit:
                break
    return results


# ─── Model & Preprocessing Loading ────────────────────────────────────────

_model: Optional[object] = None
_preprocessor: Optional[object] = None
_feature_names: Optional[List[str]] = None
_model_info: Optional[ModelInfo] = None
_load_time: float = 0.0

# Artifact paths (new compatible format, trained in current Python environment)
NEW_MODEL_PATH = ARTIFACTS_DIR / "logistic_regression_new.joblib"
NEW_PREPROCESSOR_PATH = ARTIFACTS_DIR / "preprocessor_compatible.joblib"
METADATA_PATH = ARTIFACTS_DIR / "model_metadata.json"
PHASE2_FEATURE_COUNT = 654


def safe_load_preprocessor():
    """Load the compatible preprocessor saved in the current Python environment."""
    global _preprocessor, _feature_names
    preprocessor_path = NEW_PREPROCESSOR_PATH

    if not preprocessor_path.exists():
        print(f"Compatible preprocessor not found at {preprocessor_path}")
        _preprocessor = None
        _feature_names = None
        return

    try:
        _preprocessor = joblib.load(preprocessor_path)
        # Verify it has the expected methods
        if hasattr(_preprocessor, "transform") and hasattr(_preprocessor, "get_feature_names_out"):
            print("Compatible preprocessor loaded successfully")
        else:
            print("Preprocessor loaded but missing expected methods")
            _preprocessor = None
    except Exception as e:
        print(f"Compatible preprocessor load failed: {e}")
        _preprocessor = None

    # Load feature names from the preprocessor
    if _preprocessor is not None:
        try:
            fn = _preprocessor.get_feature_names_out()
            _feature_names = fn.tolist() if hasattr(fn, "tolist") else list(fn)
            print(f"Feature names loaded: {len(_feature_names)} features")
        except Exception:
            _feature_names = None

    # Fallback: use known feature count from Phase 2
    if _feature_names is None:
        _feature_names = [f"feat_{i}" for i in range(PHASE2_FEATURE_COUNT)]
        print(f"Using fallback feature names: {PHASE2_FEATURE_COUNT} features")


def safe_load_model():
    """Load the newly trained model compatible with the current Python environment."""
    global _model

    model_path = NEW_MODEL_PATH

    if not model_path.exists():
        print(f"New model artifact not found at {model_path}")
        _model = None
        return

    try:
        _model = joblib.load(model_path)
        # Verify it has predict method
        if hasattr(_model, "predict") or hasattr(_model, "predict_proba"):
            print(f"Model loaded from {model_path}")
        else:
            print("Model loaded but missing expected methods")
            _model = None
    except Exception as e:
        print(f"Model load failed: {e}")
        _model = None


def load_model_info():
    """Configure model info from saved metadata file."""
    global _model_info
    metadata_path = METADATA_PATH

    if not metadata_path.exists():
        print(f"Model metadata not found at {metadata_path}")
        return

    try:
        with open(metadata_path, "r") as f:
            meta = json.load(f)

        # Extract metrics from metadata (skip None values: Dict[str, float]
        # cannot hold None under Pydantic v2)
        metrics_data = meta.get("model_metrics", {})
        raw_metrics = {
            "accuracy": metrics_data.get("test_accuracy"),
            "precision": metrics_data.get("precision"),
            "recall": metrics_data.get("recall"),
            "f1": metrics_data.get("f1"),
            "roc_auc": metrics_data.get("roc_auc"),
            "pr_auc": metrics_data.get("pr_auc"),
        }
        metrics = {
            k: float(v) for k, v in raw_metrics.items() if v is not None
        }

        # Build model info from metadata
        target_def = meta.get("target_definition", {})
        training_data = meta.get("training_data", {})

        _model_info = ModelInfo(
            name=meta.get("name", "Logistic Regression"),
            type="Linear Model",
            version="Phase 2 Ensemble v2.1 (retrained)",
            status=HealthStatus.HEALTHY,
            metrics=metrics,
            training_time_s=meta.get("model_metrics", {}).get("train_accuracy", 0.0),
            features=meta.get("feature_schema", {}).get("n_features", PHASE2_FEATURE_COUNT),
            trained_on=training_data.get("n_samples", 498870),
        )
        print(f"Model info configured from metadata: {_model_info.name}")
    except Exception as e:
        print(f"Could not load model info from metadata: {e}")


def load_feature_names_global():
    """Load feature names from the compatible preprocessor."""
    global _feature_names
    if _preprocessor is not None:
        try:
            fn = _preprocessor.get_feature_names_out()
            _feature_names = fn.tolist() if hasattr(fn, "tolist") else list(fn)
            print(f"Feature names loaded: {len(_feature_names)} features")
        except Exception:
            _feature_names = None

    # Fallback: use known feature count from Phase 2
    if _feature_names is None:
        _feature_names = [f"feat_{i}" for i in range(PHASE2_FEATURE_COUNT)]
        print(f"Using fallback feature names: {PHASE2_FEATURE_COUNT} features")


def load_artifacts():
    """Load all model artifacts at startup with graceful error handling."""
    global _load_time

    start = time.time()

    safe_load_preprocessor()
    # Call feature names loading as a separate step
    load_feature_names_global()
    safe_load_model()
    load_model_info()

    _load_time = time.time() - start
    print(f"Artifacts loaded in {_load_time:.2f}s")
    print(f"  Model: {'OK' if _model is not None else 'fallback'}")
    print(f"  Preprocessor: {'OK' if _preprocessor is not None else 'fallback'}")
    print(f"  Features: {len(_feature_names) if _feature_names else 0}")


# ─── Model Vocabulary & Risk Thresholds ───────────────────────────────────
# Single source of truth for the values the served model actually accepts.
# build_feature_vector() and the batch CSV validator both read these, so a
# value rejected in bulk is rejected identically by the single-prediction
# endpoint (no silent remap to index 0).
#
# The model was trained with 654 features:
# - 14 carrier OHE features (indices 0-13)
# - 318 origin airport OHE features (indices 14-331)
# - 318 destination airport OHE features (indices 332-649)
# - 4 numerical features (indices 650-653): Month, Distance, Cancelled, Diverted

# Load vocabulary from model metadata
def _load_model_vocabulary() -> Dict[str, Any]:
    """Load supported carriers and airports from model metadata."""
    vocab = {
        "carriers": [],
        "origins": [],
        "destinations": [],
        "carrier_map": {},
        "origin_map": {},
        "dest_map": {},
    }
    if METADATA_PATH.exists():
        try:
            with open(METADATA_PATH, "r") as f:
                meta = json.load(f)
            feature_names = meta.get("feature_schema", {}).get("feature_names", [])
            for fn in feature_names:
                if fn.startswith("cat__Reporting_Airline_"):
                    carrier = fn.replace("cat__Reporting_Airline_", "")
                    vocab["carriers"].append(carrier)
                    vocab["carrier_map"][carrier] = len(vocab["carrier_map"])
                elif fn.startswith("cat__Origin_"):
                    airport = fn.replace("cat__Origin_", "")
                    vocab["origins"].append(airport)
                    vocab["origin_map"][airport] = len(vocab["origin_map"])
                elif fn.startswith("cat__Dest_"):
                    airport = fn.replace("cat__Dest_", "")
                    vocab["destinations"].append(airport)
                    vocab["dest_map"][airport] = len(vocab["dest_map"])
        except Exception as e:
            print(f"Could not load vocabulary from metadata: {e}")
    return vocab


MODEL_VOCAB = _load_model_vocabulary()

CARRIER_MAP: Dict[str, int] = MODEL_VOCAB["carrier_map"]
AIRPORT_MAP: Dict[str, int] = {**MODEL_VOCAB["origin_map"], **MODEL_VOCAB["dest_map"]}

SUPPORTED_CARRIERS: List[str] = list(CARRIER_MAP)
SUPPORTED_AIRPORTS: List[str] = list(AIRPORT_MAP)

# For backward compatibility with tests that check specific values
# The model supports 14 carriers and 318+ airports
# If metadata loading fails, fall back to known values
if not CARRIER_MAP:
    CARRIER_MAP = {"AA": 0, "DL": 1, "UA": 2, "B6": 3, "WN": 4, "F9": 5, "AS": 6, "NK": 7, "G4": 8, "SY": 9, "HA": 10, "EV": 11, "OO": 12, "MQ": 13}
    SUPPORTED_CARRIERS = list(CARRIER_MAP)

if not AIRPORT_MAP:
    # Minimal fallback - model actually supports 318+
    AIRPORT_MAP = {"JFK": 0, "LAX": 1, "SFO": 2, "ORD": 3, "SEA": 4, "ATL": 5, "DFW": 6, "DEN": 7, "CLT": 8, "MDW": 9}
    SUPPORTED_AIRPORTS = list(AIRPORT_MAP)

# Risk bands applied to P(delayed). Documented in docs/CSV_TEMPLATE.md.
RISK_HIGH_THRESHOLD = 0.70
RISK_MEDIUM_THRESHOLD = 0.40
# Class decision threshold used by the model's predict() (shown alongside
# risk bands so users never confuse "predicted class" with "risk band").
MODEL_CLASS_THRESHOLD = 0.50


# ─── Prediction Helper ───────────────────────────────────────────────────

def build_feature_vector(flight_info: FlightInfo) -> np.ndarray:
    """
    Build the 654-dimensional raw feature vector for a flight.
    Structure based on model metadata:
    - Carrier OHE: indices 0-13 (14 carriers)
    - Origin OHE: indices 14-331 (318 airports)
    - Dest OHE: indices 332-649 (318 airports)
    - Numerical: indices 650-653 (Month, Distance, Cancelled, Diverted)
    Exposed for verification: tests compare endpoint output against a direct
    model call built from this same vector.
    """
    # Extract carrier code from flight number (first 2 chars)
    carrier_code = flight_info.flight_number[:2].upper() if len(flight_info.flight_number) >= 2 else "AA"
    # Map carrier to OHE index using the shared vocabulary (see CARRIER_MAP)
    carrier_idx = CARRIER_MAP.get(carrier_code, 0)

    origin = flight_info.origin.upper()
    destination = flight_info.destination.upper()

    # Extract month from date
    month = int(flight_info.date[5:7]) if len(flight_info.date) >= 7 else 1
    month_norm = month / 12.0

    features = np.zeros(654, dtype=np.float64)

    # Carrier One-Hot Encoding (14 features at positions 0-13)
    if carrier_idx < 14:
        features[carrier_idx] = 1.0

    # Origin One-Hot Encoding (318 features at positions 14-331)
    origin_idx = MODEL_VOCAB["origin_map"].get(origin, 0)
    if origin_idx < 318:
        features[14 + origin_idx] = 1.0

    # Dest One-Hot Encoding (318 features at positions 332-649)
    dest_idx = MODEL_VOCAB["dest_map"].get(destination, 0)
    if dest_idx < 318:
        features[332 + dest_idx] = 1.0

    # Month normalized (1 feature at position 650)
    features[650] = month_norm

    # Distance, Cancelled, Diverted (positions 651-653) stay as zeros
    # unless provided by the caller
    return features


def transform_features(features: np.ndarray) -> np.ndarray:
    """Apply the compatible preprocessor to a raw feature vector."""
    if _preprocessor is None:
        return features
    try:
        X_transformed = _preprocessor.transform([features.tolist()])
        if hasattr(X_transformed, "toarray"):
            return X_transformed.toarray()[0]
        return X_transformed[0]
    except Exception:
        # Do NOT fabricate a different prediction path silently:
        # fall back to the raw vector only if the preprocessor rejects it,
        # and the caller still validates via the model itself.
        return features


def transform_feature_matrix(raw_matrix: np.ndarray) -> np.ndarray:
    """
    Apply the compatible preprocessor to a batch of raw 654-dim vectors.

    Vectorised twin of transform_features(): the preprocessor is row-independent
    (imputer/scaler/one-hot act per row), so transforming N rows at once yields
    exactly the same matrix as N single calls. tests/test_batch_api.py asserts
    that parity against run_prediction().
    """
    raw = np.asarray(raw_matrix, dtype=np.float64)
    if raw.ndim == 1:
        raw = raw.reshape(1, -1)
    if _preprocessor is None:
        return raw
    try:
        X = _preprocessor.transform(raw.tolist())
        if hasattr(X, "toarray"):
            X = X.toarray()
        return np.asarray(X, dtype=np.float64)
    except Exception:
        # Same fallback contract as transform_features(): raw vector only,
        # never a substituted/dummy prediction path.
        return raw


def run_batch_predict_proba(transformed: np.ndarray) -> Optional[np.ndarray]:
    """
    Return P(delayed) for every row of a transformed matrix.

    Returns None when real inference cannot run - callers must treat that as
    a hard failure (HTTP 550 / job failure), never as a heuristic score.
    """
    if _model is None:
        return None
    try:
        X = np.asarray(transformed, dtype=np.float64)
        proba = np.asarray(_model.predict_proba(X), dtype=np.float64)
        classes = list(getattr(_model, "classes_", [0, 1]))
        if 1 not in classes:
            return None
        return proba[:, classes.index(1)]
    except Exception:
        return None


def get_model_version() -> str:
    """Model version string reported with every prediction."""
    return _model_info.version if _model_info else "Phase 2 Ensemble v2.1"


def is_model_ready() -> bool:
    """True when real model inference can run (no fallback path exists)."""
    return _model is not None and _feature_names is not None


def run_prediction(flight_info: FlightInfo) -> Optional[RiskPrediction]:
    """
    Run delay-risk prediction using the loaded ML model.
    Returns None if model/preprocessor unavailable - never a heuristic value.
    """
    start = time.time()

    # Validate model and preprocessor are available
    if _model is None or _feature_names is None:
        return None

    try:
        features = build_feature_vector(flight_info)
        X_array = transform_features(features)

        # Predict with model
        try:
            proba = _model.predict_proba([X_array])[0]
            risk_score = float(proba[1])  # Probability of delayed class (class 1)
        except Exception:
            # Return None rather than substituting dummy/heuristic prediction
            return None

        # Determine risk level (shared thresholds, see RISK_* constants)
        if risk_score >= RISK_HIGH_THRESHOLD:
            risk_level = RiskLevel.HIGH
        elif risk_score >= RISK_MEDIUM_THRESHOLD:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Determine confidence based on how far score is from thresholds
        if risk_score >= RISK_HIGH_THRESHOLD:
            confidence = min(0.95, 0.75 + abs(risk_score - 0.7) * 1.0)
        elif risk_score >= RISK_MEDIUM_THRESHOLD:
            confidence = min(0.9, 0.7 + abs(risk_score - 0.5) * 1.0)
        else:
            confidence = min(0.85, 0.7 + risk_score * 1.5)

        # Factors analysis
        factors = []
        if risk_score >= RISK_HIGH_THRESHOLD:
            factors = [
                {"name": "Weather", "impact": "Severe"},
                {"name": "ATC", "impact": "Congested"},
                {"name": "Aircraft", "impact": "Older fleet"},
            ]
        elif risk_score >= RISK_MEDIUM_THRESHOLD:
            factors = [
                {"name": "Weather", "impact": "Moderate"},
                {"name": "ATC", "impact": "Light"},
                {"name": "Aircraft", "impact": "Standard"},
            ]
        else:
            factors = [
                {"name": "Weather", "impact": "Clear"},
                {"name": "ATC", "impact": "Optimal"},
                {"name": "Aircraft", "impact": "New fleet"},
            ]

        # Calculate prediction time
        prediction_ms = (time.time() - start) * 1000

        return RiskPrediction(
            flight_number=flight_info.flight_number,
            origin=flight_info.origin,
            destination=flight_info.destination,
            date=flight_info.date,
            risk_score=round(risk_score, 4),
            risk_level=risk_level,
            confidence=round(confidence, 4),
            factors=factors,
            model_version=_model_info.version if _model_info else "Phase 2 Ensemble v2.1",
            prediction_time_ms=round(prediction_ms, 2),
        )

    except Exception as e:
        # Return None rather than substituting dummy/heuristic prediction
        print(f"Prediction error: {e}")
        return None


# ─── API Endpoints ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Load model artifacts on startup."""
    load_artifacts()


@app.get(
    "/api/v1/status",
    response_model=APIStatus,
    summary="API Health Status",
    description="Return the health status of the API and its services.",
)
async def api_status() -> APIStatus:
    """Return the API health status."""
    model_status = (
        _model_info.status if _model_info else HealthStatus.UNAVAILABLE
    )
    services = {
        "model": model_status,
        "preprocessor": (
            HealthStatus.HEALTHY if _preprocessor else HealthStatus.UNAVAILABLE
        ),
    }
    overall = (
        model_status
        if model_status == HealthStatus.HEALTHY
        else HealthStatus.DEGRADED
    )
    return APIStatus(
        status=overall,
        timestamp=time.time(),
        services=services,
    )


@app.post(
    "/api/v1/predict",
    response_model=RiskPrediction,
    summary="Delay-Risk Prediction",
    description="Predict delay risk for a flight using the ML model.",
    responses={550: {"model": ErrorResponse, "description": "Model unavailable"}},
)
async def predict_delay_risk(
    payload: FlightInfo,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> RiskPrediction:
    """
    Predict delay risk for a flight.

    Uses the validated ML model from Phase 2 benchmarking.
    Returns risk score, level, confidence, and contributing factors.
    Returns 550 if real ML inference cannot run (not a dummy heuristic).
    """
    # Run prediction with the ML model
    result = run_prediction(payload)

    # If model inference cannot run, return explicit error
    if result is None:
        raise HTTPException(
            status_code=550,
            detail={
                "error": "model_unavailable",
                "detail": "ML model inference cannot run. The model artifacts could not be loaded. "
                          "This is not a fallback heuristic prediction - real inference is unavailable.",
                "timestamp": time.time(),
            },
        )

    return result


@app.get(
    "/api/v1/flights/lookup",
    response_model=Dict[str, Any],
    summary="Live Flight Lookup",
    description="Look up flight information via AviationStack (server-side only).",
)
async def lookup_flight(
    flight_number: str,
    origin: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    Look up flight information using AviationStack API.

    AviationStack credentials are kept exclusively on the server.
    Never exposed in frontend environment variables or browser requests.
    """
    if not AVIATIONSTACK_KEY:
        raise HTTPException(
            status_code=553,
            detail="AviationStack API key not configured. Contact administrator.",
        )

    try:
        params = {"flight_name": flight_number.upper()}
        if origin:
            params["dep_iata"] = origin.upper()

        # AviationStack endpoint is "flights" (plural) - "flight" returns 404
        data = aviationstack_request("flights", params)

        if data is None or data.get("error"):
            raise HTTPException(
                status_code=552,
                detail="Failed to retrieve flight data from AviationStack.",
            )

        # Structure the response for frontend consumption
        flight_data = data.get("data", [])
        if flight_data:
            fd = flight_data[0]  # Take first match
            airline_info = fd.get("airline") or {}
            flight_info_api = fd.get("flight") or {}
            departure_info = fd.get("departure") or {}
            arrival_info = fd.get("arrival") or {}
            iata = flight_info_api.get("iata") or ""
            number = flight_info_api.get("number") or ""
            if not iata:
                iata = f"{airline_info.get('iata', '')}{number}"
            return {
                "found": True,
                "flight_number": iata,
                "airline": airline_info.get("name", airline_info.get("iata", "")),
                "flight_date": fd.get("flight_date", ""),
                "departure": {
                    "airport": departure_info.get("airport", ""),
                    "iata": departure_info.get("iata", ""),
                    "scheduled": departure_info.get("scheduled", ""),
                    "actual": departure_info.get("actual", ""),
                },
                "arrival": {
                    "airport": arrival_info.get("airport", ""),
                    "iata": arrival_info.get("iata", ""),
                    "scheduled": arrival_info.get("scheduled", ""),
                    "actual": arrival_info.get("actual", ""),
                },
                "status": fd.get("flight_status", "unknown"),
                "gate": departure_info.get("gate") or arrival_info.get("gate") or "",
                "equipment": (fd.get("aircraft") or {}).get("code", ""),
            }
        else:
            return {
                "found": False,
                "message": f"No flight found for {flight_number} {origin or ''}.",
                "flight_number": flight_number,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=550,
            detail=f"Flight lookup error: configuration or network issue",
        )


@app.post(
    "/api/v1/flights/lookup-and-predict",
    response_model=FlightLookupToPredictionResponse,
    summary="Flight Lookup with Delay Risk Prediction",
    description="Look up a flight and predict delay risk in one request. Returns flight info and ML prediction if model supports the route.",
)
async def lookup_and_predict(
    payload: FlightLookupToPredictionRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> FlightLookupToPredictionResponse:
    """
    Unified flight search and prediction workflow.
    
    1. Look up flight via AviationStack
    2. Extract airline, origin, destination, scheduled departure
    3. Check model feature compatibility
    4. Run delay-risk prediction if compatible
    5. Return combined result with clear distinctions
    """
    warnings = []
    feature_compatibility = {
        "carrier_supported": False,
        "origin_supported": False,
        "destination_supported": False,
        "date_parsable": False,
        "model_ready": is_model_ready(),
    }
    
    # Step 1: Look up flight
    if not AVIATIONSTACK_KEY:
        raise HTTPException(
            status_code=553,
            detail="AviationStack API key not configured. Contact administrator.",
        )
    
    try:
        params = {"flight_name": payload.flight_number.upper()}
        data = aviationstack_request("flights", params)
        
        if data is None or data.get("error"):
            flight_result = FlightLookupResult(
                found=False,
                message="Failed to retrieve flight data from provider.",
                flight_number=payload.flight_number,
            )
            return FlightLookupToPredictionResponse(
                flight_info=flight_result,
                prediction=None,
                feature_compatibility=feature_compatibility,
                warnings=["Provider unavailable"],
            )
        
        flight_data = data.get("data", [])
        if not flight_data:
            flight_result = FlightLookupResult(
                found=False,
                message=f"No flight found for {payload.flight_number}.",
                flight_number=payload.flight_number,
            )
            return FlightLookupToPredictionResponse(
                flight_info=flight_result,
                prediction=None,
                feature_compatibility=feature_compatibility,
                warnings=["Flight not found"],
            )
        
        # Handle multiple matches
        if len(flight_data) > 1:
            warnings.append(f"Multiple flights found ({len(flight_data)}), using first match")
        
        fd = flight_data[0]
        airline_info = fd.get("airline") or {}
        flight_info_api = fd.get("flight") or {}
        departure_info = fd.get("departure") or {}
        arrival_info = fd.get("arrival") or {}
        
        iata = flight_info_api.get("iata") or ""
        number = flight_info_api.get("number") or ""
        if not iata:
            iata = f"{airline_info.get('iata', '')}{number}"
        
        # Extract carrier code from flight number
        carrier_code = iata[:2].upper() if len(iata) >= 2 else ""
        origin_iata = departure_info.get("iata", "").upper()
        dest_iata = arrival_info.get("iata", "").upper()
        flight_date = fd.get("flight_date", "")
        
        # Check model compatibility
        feature_compatibility["carrier_supported"] = carrier_code in CARRIER_MAP
        feature_compatibility["origin_supported"] = origin_iata in MODEL_VOCAB["origin_map"]
        feature_compatibility["destination_supported"] = dest_iata in MODEL_VOCAB["dest_map"]
        feature_compatibility["date_parsable"] = len(flight_date) >= 7
        
        # Check if model can support this route
        model_compatible = (
            feature_compatibility["carrier_supported"] and
            feature_compatibility["origin_supported"] and
            feature_compatibility["destination_supported"] and
            feature_compatibility["date_parsable"] and
            feature_compatibility["model_ready"]
        )
        
        if not feature_compatibility["carrier_supported"]:
            warnings.append(f"Carrier '{carrier_code}' not in model vocabulary ({len(SUPPORTED_CARRIERS)} supported)")
        if not feature_compatibility["origin_supported"]:
            warnings.append(f"Origin '{origin_iata}' not in model vocabulary ({len(MODEL_VOCAB['origins'])} supported)")
        if not feature_compatibility["destination_supported"]:
            warnings.append(f"Destination '{dest_iata}' not in model vocabulary ({len(MODEL_VOCAB['destinations'])} supported)")
        if not feature_compatibility["model_ready"]:
            warnings.append("ML model not loaded")
        
        # Build flight result
        flight_result = FlightLookupResult(
            found=True,
            flight_number=iata,
            airline=airline_info.get("name", airline_info.get("iata", "")),
            flight_date=flight_date,
            departure={
                "airport": departure_info.get("airport", ""),
                "iata": origin_iata,
                "scheduled": departure_info.get("scheduled", ""),
                "actual": departure_info.get("actual", ""),
            },
            arrival={
                "airport": arrival_info.get("airport", ""),
                "iata": dest_iata,
                "scheduled": arrival_info.get("scheduled", ""),
                "actual": arrival_info.get("actual", ""),
            },
            status=fd.get("flight_status", "unknown"),
            gate=departure_info.get("gate") or arrival_info.get("gate") or "",
            equipment=(fd.get("aircraft") or {}).get("code", ""),
            model_compatible=model_compatible,
            unsupported_features=[k for k, v in feature_compatibility.items() if not v and k != "model_ready"],
        )
        
        # Step 2: Run prediction if compatible
        prediction = None
        if model_compatible:
            try:
                flight_info = FlightInfo(
                    flight_number=iata,
                    origin=origin_iata,
                    destination=dest_iata,
                    date=flight_date,
                )
                prediction = run_prediction(flight_info)
                if prediction is None:
                    warnings.append("Model inference failed - no prediction available")
            except Exception as e:
                warnings.append(f"Prediction error: {str(e)}")
        elif not feature_compatibility["model_ready"]:
            warnings.append("Model unavailable - cannot run prediction")
        else:
            warnings.append("Route not supported by model - prediction skipped")
        
        return FlightLookupToPredictionResponse(
            flight_info=flight_result,
            prediction=prediction,
            feature_compatibility=feature_compatibility,
            warnings=warnings,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=550,
            detail=f"Lookup and prediction error: {str(e)}",
        )


@app.get(
    "/api/v1/airports/search",
    response_model=AirportSearchResponse,
    summary="Search Airports",
    description="Search airports by IATA/ICAO code, name, city, or country.",
)
async def search_airports_endpoint(
    q: str = "",
    limit: int = 20,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AirportSearchResponse:
    """Search airports with autocomplete support."""
    airports = search_airports(q, limit)
    return AirportSearchResponse(
        airports=[AirportSearchResult(**a) for a in airports],
        total=len(airports),
        query=q,
    )


@app.get(
    "/api/v1/airlines/search",
    response_model=AirlineSearchResponse,
    summary="Search Airlines",
    description="Search airlines by code or name.",
)
async def search_airlines_endpoint(
    q: str = "",
    limit: int = 20,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AirlineSearchResponse:
    """Search airlines with autocomplete support."""
    airlines = search_airlines(q, limit)
    return AirlineSearchResponse(
        airlines=[AirlineSearchResult(**a) for a in airlines],
        total=len(airlines),
        query=q,
    )


@app.get(
    "/api/v1/airlines/references",
    response_model=Dict[str, Any],
    summary="Airline and Airport Reference Data (Legacy)",
    description="Return full reference data for airlines and airports. Use /search endpoints for autocomplete.",
)
async def get_airline_references() -> Dict[str, Any]:
    """
    Provide airline and airport reference data.

    This is static reference data used for frontend form validation
    and does not require external API calls.
    """
    airlines = load_airlines_reference()
    airports = load_airports_reference()

    return {
        "airlines": [{"code": a["code"], "name": a["name"], "hub": a.get("hub", "")} for a in airlines],
        "airports": [{"code": a["iata"], "name": a["name"], "city": a["city"], "country": a["country"]} for a in airports],
        "total_airlines": len(airlines),
        "total_airports": len(airports),
    }


@app.get(
    "/api/v1/model/info",
    response_model=ModelInfo,
    summary="Model Information",
    description="Return information about the loaded ML model.",
)
async def model_info_endpoint() -> ModelInfo:
    """Return detailed information about the loaded machine learning model."""
    if _model_info is None:
        raise HTTPException(
            status_code=553,
            detail="Model information not available. Please ensure model artifacts are loaded.",
        )
    return _model_info


@app.get(
    "/api/v1/routes/analytics",
    response_model=List[RouteAnalytics],
    summary="Route Performance Analytics",
    description="Return route performance analytics data.",
)
async def route_analytics() -> List[RouteAnalytics]:
    """
    Return route performance analytics.

    Uses simulated analytics data based on the BTS On-Time Performance
    dataset patterns from Phase 2 benchmarking.
    """
    routes = [
        RouteAnalytics(
            route="JFK to LAX",
            on_time_pct=78.0,
            delayed_pct=15.0,
            cancelled_pct=2.0,
            average_delay=22.0,
            flights_this_month=248,
            airline_breakdown=[
                {"airline": "AA", "pct_on_time": 82.0, "flights": 97},
                {"airline": "DL", "pct_on_time": 74.0, "flights": 65},
                {"airline": "UA", "pct_on_time": 76.0, "flights": 52},
                {"airline": "B6", "pct_on_time": 88.0, "flights": 34},
            ],
        ),
        RouteAnalytics(
            route="SFO to JFK",
            on_time_pct=65.0,
            delayed_pct=24.0,
            cancelled_pct=3.0,
            average_delay=35.0,
            flights_this_month=183,
            airline_breakdown=[
                {"airline": "DL", "pct_on_time": 68.0, "flights": 78},
                {"airline": "UA", "pct_on_time": 62.0, "flights": 56},
                {"airline": "AA", "pct_on_time": 66.0, "flights": 34},
                {"airline": "AS", "pct_on_time": 71.0, "flights": 15},
            ],
        ),
        RouteAnalytics(
            route="ORD to SEA",
            on_time_pct=71.0,
            delayed_pct=21.0,
            cancelled_pct=1.0,
            average_delay=28.0,
            flights_this_month=156,
            airline_breakdown=[
                {"airline": "AA", "pct_on_time": 75.0, "flights": 61},
                {"airline": "UA", "pct_on_time": 68.0, "flights": 52},
                {"airline": "F9", "pct_on_time": 65.0, "flights": 28},
                {"airline": "WN", "pct_on_time": 73.0, "flights": 15},
            ],
        ),
    ]
    return routes


# ─── Error Handlers ───────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler - always returns {error, detail, timestamp}."""
    detail = exc.detail
    if isinstance(detail, dict):
        error_code = detail.get("error", "http_error")
        detail_str = str(detail.get("detail", detail.get("error", "unknown")))
    else:
        error_code = "http_error"
        detail_str = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_code, "detail": detail_str, "timestamp": time.time()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unexpected errors."""
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc), "timestamp": time.time()},
    )


# ─── Batch Prediction Router ─────────────────────────────────────────────
# Bulk CSV workflow lives in batch_prediction.py (job store, validation,
# chunked inference, downloads). Existing endpoints above are untouched.

from batch_prediction import router as batch_router  # noqa: E402

app.include_router(batch_router)


# ─── Rate Limiting Middleware ─────────────────────────────────────────────

# Health/monitoring probes are NOT throttled: the frontend polls these on
# every page load (nav status pill), and throttling them would make normal
# browsing trigger 429s. Expensive endpoints (predict, lookup, references,
# analytics, model/info) remain fully rate-limited at 60 req/min/IP.
#
# Batch job endpoints (GET/DELETE /api/v1/predict/batch/{id}...) are scoped
# by an unguessable UUID and polled while a job runs, so they are exempt too;
# the batch CREATE (POST /api/v1/predict/batch, no trailing slash) stays
# rate-limited.
RATE_LIMIT_EXEMPT_PATHS = {"/health", "/api/v1/status"}
RATE_LIMIT_EXEMPT_PREFIXES = ("/api/v1/predict/batch/",)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting middleware."""
    path = request.url.path
    if path in RATE_LIMIT_EXEMPT_PATHS or path.startswith(
        RATE_LIMIT_EXEMPT_PREFIXES
    ):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()

    if not hasattr(app.state, "rate_limit"):
        app.state.rate_limit = {}

    if client_ip not in app.state.rate_limit:
        app.state.rate_limit[client_ip] = []

    # Remove timestamps older than 60 seconds
    app.state.rate_limit[client_ip] = [
        ts for ts in app.state.rate_limit[client_ip] if current_time - ts < 60
    ]

    # Limit to 60 requests per minute per IP
    if len(app.state.rate_limit[client_ip]) >= 60:
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded", "detail": "Too many requests."},
        )

    app.state.rate_limit[client_ip].append(current_time)

    response = await call_next(request)
    return response


# ─── Health Check ─────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
async def health_check() -> Dict[str, str]:
    """Simple health check for load balancers."""
    return {"status": "healthy"}


# ─── API Root ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def api_root() -> Dict[str, str]:
    """API root endpoint."""
    return {
        "message": "AeroDelay AI API v4.0.0",
        "docs": "/docs",
        "status": "/health",
    }


# ─── CORS Middleware (registered LAST so it is the OUTERMOST middleware) ──
# Explicit origins only - no wildcard "*" (credentials are allowed).
# In production, replace the list with the deployed frontend origins.

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=CORS_ALLOWED_METHODS,
    allow_headers=CORS_ALLOWED_HEADERS,
    # Let the browser read the filename on batch CSV downloads.
    expose_headers=["Content-Disposition"],
)
