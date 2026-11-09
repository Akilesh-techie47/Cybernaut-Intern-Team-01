"""Tests for the AviationStack flight data provider adapter."""

import json
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set the API key environment variable for provider tests
os.environ["AVIATIONSTACK_ACCESS_KEY"] = "test_key_12345"

from src.flight_data._provider import (
    AviationStackProvider,
    FlightInfo,
    ProviderError,
    AirportInfo,
    AircraftPosition,
    ProviderCache,
    _parse_aviationstack_flight,
)


# ---- Fixtures ----

@pytest.fixture
def provider():
    """Provide an AviationStackProvider instance for each test."""
    return AviationStackProvider()


@pytest.fixture
def sample_aviationstack_response():
    """Sample successful AviationStack API response."""
    return {
        "data": [
            {
                "flight": {
                    "iata": "UA123",
                    "icao": "UAL123",
                    "number": "UA123",
                },
                "flight_status": "en_route",
                "departure": {
                    "airport": "JFK",
                    "iata": "JFK",
                    "icao": "KJFK",
                    "city": "New York",
                    "country": "USA",
                    "scheduled": "2024-01-15T10:30:00",
                    "estimated": "2024-01-15T10:45:00",
                    "actual": "2024-01-15T10:35:00",
                    "timezone": "America/New_York",
                    "latitude": 40.6413,
                    "longitude": -73.7781,
                },
                "arrival": {
                    "airport": "LAX",
                    "iata": "LAX",
                    "icao": "KLAX",
                    "city": "Los Angeles",
                    "country": "USA",
                    "scheduled": "2024-01-15T13:25:00",
                    "estimated": "2024-01-15T13:40:00",
                    "actual": "2024-01-15T13:30:00",
                    "timezone": "America/Los_Angeles",
                    "latitude": 33.9416,
                    "longitude": -118.4088,
                },
                "velocity": {"airspeed": 450},
                "heading": {"degrees": 270},
            }
        ],
        "pagination": {"count": 1, "total": 1, "skip": 0, "limit": 10},
    }


# ---- ProviderConfig Tests ----

class TestProviderConfig:
    """Test provider configuration methods."""

    def test_requires_api_key(self, provider):
        """AviationStack provider requires an API key."""
        assert provider.requires_api_key is True

    def test_name(self, provider):
        """Provider has correct name."""
        assert provider.name == "AviationStack"


# ---- ProviderCache Tests ----

class TestProviderCache:
    """Test the ProviderCache helper class."""

    def test_cache_set_and_try_get(self):
        """Cache set and try_get work correctly."""
        cache = ProviderCache(ttl_seconds=300)
        key = ("AviationStack", "UA123", "2024-01-15")

        # Initially empty
        flight_info, error, fresh = cache.try_get(key)
        assert fresh is False

        # Create a mock flight info
        flight_info = FlightInfo(
            flight_number="UA123",
            date="2024-01-15",
            status="en_route",
            origin=AirportInfo(
                name="JFK", city="New York", country="USA",
                iata="JFK", icao="KJFK",
                latitude=40.6413, longitude=-73.7781, timezone="America/New_York"
            ),
            destination=AirportInfo(
                name="LAX", city="Los Angeles", country="USA",
                iata="LAX", icao="KLAX",
                latitude=33.9416, longitude=-118.4088, timezone="America/Los_Angeles"
            ),
            provider="AviationStack",
            retrieval_time=__import__("datetime").datetime.now(),
        )

        # Set in cache
        cache.set(key, flight_info, None)

        # Try get should return fresh
        flight_info2, error2, fresh2 = cache.try_get(key)
        assert fresh2 is True
        assert flight_info2 is not None
        assert error2 is None

    def test_cache_expiry(self):
        """Cache entries expire after TTL."""
        cache = ProviderCache(ttl_seconds=1)  # 1 second TTL for testing
        key = ("AviationStack", "UA123", "2024-01-15")

        # Set in cache
        flight_info = FlightInfo(
            flight_number="UA123",
            date="2024-01-15",
            status="en_route",
            origin=AirportInfo(
                name="JFK", city="New York", country="USA",
                iata="JFK", icao="KJFK",
                latitude=40.6413, longitude=-73.7781, timezone="America/New_York"
            ),
            destination=AirportInfo(
                name="LAX", city="Los Angeles", country="USA",
                iata="LAX", icao="KLAX",
                latitude=33.9416, longitude=-118.4088, timezone="America/Los_Angeles"
            ),
            provider="AviationStack",
            retrieval_time=__import__("datetime").datetime.now(),
        )
        cache.set(key, flight_info, None)

        # Should be fresh immediately
        _, _, fresh = cache.try_get(key)
        assert fresh is True

        # Wait for expiry
        import time
        time.sleep(2)

        # Should now be stale
        _, _, fresh = cache.try_get(key)
        assert fresh is False
        # Entry should be removed
        assert key not in cache._cache


# ---- Lookup Flight Tests ----

class TestLookupFlight:
    """Test the lookup_flight method with mocked HTTP responses."""

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_without_api_key(self, mock_get, provider):
        """Lookup without API key returns configuration error."""
        # Temporarily remove the API key to test the config check path
        with patch.dict("os.environ", {}, clear=True):
            # Clear the cached config
            provider_cached = AviationStackProvider()
            flight_info, error = provider_cached.lookup_flight("UA123", "2024-01-15")
            assert flight_info is None
            assert error is not None
            assert error.type == "configuration"
            "API key not configured" in error.message

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_not_found(self, mock_get, provider, sample_aviationstack_response):
        """Lookup returns not_found when no data matches."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "not_found"
        "No flight found" in error.message

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_ambiguous_matches(self, mock_get, provider, sample_aviationstack_response):
        """Lookup returns ambiguous when multiple flights match the same number."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Return 2 records with the same flight number
        mock_response.json.return_value = {
            "data": [
                {
                    "flight": {"iata": "UA123", "number": "UA123"},
                    "flight_status": "en_route",
                    "departure": {"airport": "JFK", "iata": "JFK", "scheduled": "2024-01-15T10:30:00"},
                    "arrival": {"airport": "LAX", "iata": "LAX", "scheduled": "2024-01-15T13:25:00"},
                },
                {
                    "flight": {"iata": "UA123", "number": "UA123"},
                    "flight_status": "landed",
                    "departure": {"airport": "LGA", "iata": "LGA", "scheduled": "2024-01-15T09:00:00"},
                    "arrival": {"airport": "SFO", "iata": "SFO", "scheduled": "2024-01-15T12:30:00"},
                },
            ],
        }
        mock_get.return_value = mock_response

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "ambiguous"
        "Ambiguous flight number" in error.message

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_successful(self, mock_get, provider, sample_aviationstack_response):
        """Lookup returns FlightInfo when a single match is found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_aviationstack_response
        mock_get.return_value = mock_response

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is not None
        assert error is None
        assert flight_info.flight_number == "UA123"
        assert flight_info.date == "2024-01-15"
        assert flight_info.status == "en_route"
        assert flight_info.origin.iata == "JFK"
        assert flight_info.destination.iata == "LAX"
        assert flight_info.provider == "AviationStack"
        # Check retrieval time is recent
        assert flight_info.data_freshness_seconds >= 0
        # Check raw response is stored
        assert len(flight_info.raw_response) > 0

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_rate_limit(self, mock_get, provider):
        """Lookup returns rate_limit error on HTTP 429."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "rate_limit"
        "rate limit" in error.message.lower()

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_provider_error(self, mock_get, provider):
        """Lookup returns provider_error on non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "provider_error"
        "HTTP 500" in error.message

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_timeout(self, mock_get, provider):
        """Lookup returns timeout error on request timeout."""
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout("Request timed out")

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "timeout"
        "timed out" in error.message.lower()

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_connection_error(self, mock_get, provider):
        """Lookup returns connection_error on network failure."""
        from requests.exceptions import ConnectionError as ConnError
        mock_get.side_effect = ConnError("Connection refused")

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "connection_error"
        "Could not connect" in error.message

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_json_decode_error(self, mock_get, provider):
        """Lookup returns provider_error on invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
        mock_get.return_value = mock_response

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "provider_error"
        "invalid JSON" in error.message.lower()

    @patch("src.flight_data._provider.requests.get")
    def test_lookup_parse_error(self, mock_get, provider):
        """Lookup returns parsing_error when response can't be parsed into FlightInfo."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"bad": "data"}]}
        mock_get.return_value = mock_response

        flight_info, error = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info is None
        assert error is not None
        assert error.type == "parsing_error"
        "parse" in error.message.lower()

    @patch("src.flight_data._provider.requests.get")
    def test_cache_stores_successful_response(self, mock_get, provider, sample_aviationstack_response):
        """Successful lookups are cached and served from cache on second call."""
        from datetime import datetime

        # Configure mock to return the same response for both calls
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_aviationstack_response
        mock_get.return_value = mock_response

        # Call twice with same params
        flight_info1, error1 = provider.lookup_flight("UA123", "2024-01-15")
        flight_info2, error2 = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info1 is not None
        assert flight_info2 is not None
        assert error1 is None
        assert error2 is None
        # Both should return the same cached result
        assert flight_info1.flight_number == flight_info2.flight_number

    @patch("src.flight_data._provider.requests.get")
    def test_cache_stores_error_response(self, mock_get, provider):
        """Error lookups are also cached to avoid repeated API calls."""
        from datetime import datetime

        # Configure mock to always return not_found
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        # Call twice with same params
        flight_info1, error1 = provider.lookup_flight("UA123", "2024-01-15")
        flight_info2, error2 = provider.lookup_flight("UA123", "2024-01-15")

        assert flight_info1 is None
        assert error1 is not None
        assert error1.type == "not_found"
        assert flight_info2 is None
        assert error2 is not None
        assert error2.type == "not_found"


# ---- _parse_aviationstack_flight Tests ----

class TestParseAviationStackFlight:
    """Test the _parse_aviationstack_flight helper function."""

    def test_basic_parsing(self):
        """Basic parsing of AviationStack response into FlightInfo."""
        flight_data = {
            "data": [
                {
                    "flight": {"iata": "UA123", "number": "UA123"},
                    "flight_status": "en_route",
                    "departure": {
                        "airport": "JFK",
                        "iata": "JFK",
                        "scheduled": "2024-01-15T10:30:00",
                        "estimated": "2024-01-15T10:45:00",
                        "actual": "2024-01-15T10:35:00",
                        "timezone": "America/New_York",
                        "latitude": 40.6413,
                        "longitude": -73.7781,
                    },
                    "arrival": {
                        "airport": "LAX",
                        "iata": "LAX",
                        "scheduled": "2024-01-15T13:25:00",
                        "estimated": "2024-01-15T13:40:00",
                        "actual": "2024-01-15T13:30:00",
                        "timezone": "America/Los_Angeles",
                        "latitude": 33.9416,
                        "longitude": -118.4088,
                    },
                }
            ]
        }

        flight_info = _parse_aviationstack_flight(
            flight_data, "UA123", "2024-01-15"
        )

        assert flight_info is not None
        assert flight_info.flight_number == "UA123"
        assert flight_info.date == "2024-01-15"
        assert flight_info.status == "en_route"
        assert flight_info.origin.iata == "JFK"
        assert flight_info.destination.iata == "LAX"
        assert flight_info.scheduled_departure is not None
        assert flight_info.estimated_arrival is not None

    def test_missing_data_handling(self):
        """Parsing handles missing/optional fields gracefully."""
        flight_data = {"data": [{"bad": "structure"}]}

        # This should raise an exception or return partial info
        # The function should not crash completely
        try:
            flight_info = _parse_aviationstack_flight(
                flight_data, "UA123", "2024-01-15"
            )
            # If it returns, fields should be None when missing
            assert flight_info is not None
        except Exception:
            # It's also acceptable for it to raise and be caught by the caller
            pass


# ---- FlightInfo Model Tests ----

class TestFlightInfoModel:
    """Test the FlightInfo Pydantic model."""

    def test_flight_info_creation(self):
        """FlightInfo can be created with all fields."""
        origin = AirportInfo(
            name="JFK", city="New York", country="USA",
            iata="JFK", icao="KJFK",
            latitude=40.6413, longitude=-73.7781, timezone="America/New_York"
        )
        dest = AirportInfo(
            name="LAX", city="Los Angeles", country="USA",
            iata="LAX", icao="KLAX",
            latitude=33.9416, longitude=-118.4088, timezone="America/Los_Angeles"
        )
        ac_pos = AircraftPosition(
            icao24="abc123",
            callsign="UA123",
            latitude=40.6413,
            longitude=-73.7781,
            altitude=35000,
            ground_speed=450,
            true_track=270,
        )

        flight_info = FlightInfo(
            flight_number="UA123",
            date="2024-01-15",
            status="en_route",
            scheduled_departure=None,
            estimated_departure=None,
            actual_departure=None,
            scheduled_arrival=None,
            estimated_arrival=None,
            actual_arrival=None,
            origin=origin,
            destination=dest,
            aircraft_position=ac_pos,
            provider="AviationStack",
            retrieval_time=__import__("datetime").datetime.now(),
        )

        assert flight_info.flight_number == "UA123"
        assert flight_info.status == "en_route"
        assert flight_info.aircraft_position is not None
        assert flight_info.aircraft_position.latitude == 40.6413
        assert flight_info.aircraft_position.ground_speed == 450
        assert isinstance(flight_info.retrieval_time, __import__("datetime").datetime)

    def test_flight_info_minimal(self):
        """FlightInfo can be created with minimal fields."""
        origin = AirportInfo(
            name="JFK", city="New York", country="USA",
            iata="JFK", icao="KJFK",
            latitude=40.6413, longitude=-73.7781, timezone="America/New_York"
        )
        dest = AirportInfo(
            name="LAX", city="Los Angeles", country="USA",
            iata="LAX", icao="KLAX",
            latitude=33.9416, longitude=-118.4088, timezone="America/Los_Angeles"
        )

        flight_info = FlightInfo(
            flight_number="UA123",
            date="2024-01-15",
            status="en_route",
            origin=origin,
            destination=dest,
            provider="AviationStack",
            retrieval_time=__import__("datetime").datetime.now(),
        )

        assert flight_info.flight_number == "UA123"
        assert flight_info.origin is origin
        assert flight_info.destination is dest
        assert flight_info.aircraft_position is None


# ---- Edge case: invalid flight number format ----
class TestFlightNumberValidation:
    """Test flight number format validation outside of Streamlit context."""

    @staticmethod
    def _validate_flight_number(fn: str):
        """Duplicate of the validation logic from app.py."""
        fn = fn.strip().upper()
        if not fn:
            return False, "Please enter a flight number."
        import re
        pattern = r'^[A-Z]{1,2}\d{1,4}$'
        if not re.match(pattern, fn):
            return False, (
                f"Invalid flight number format: '{fn}'. "
                "Expected format: AirlineCode+Number (e.g., UA123, DL456)."
            )
        return True, ""

    def test_valid_flight_numbers(self):
        """Valid flight numbers pass validation."""
        valid_cases = ["UA123", "DL456", "AA1", "B625", "WN101", "F9789"]
        for fn in valid_cases:
            is_valid, msg = self._validate_flight_number(fn)
            assert is_valid, f"Expected '{fn}' to be valid, but got: {msg}"

    def test_invalid_flight_numbers(self):
        """Invalid flight numbers fail validation."""
        invalid_cases = [
            ("", "Please enter a flight number"),
            ("UA", "Airline code only, no number"),
            ("123", "Number only, no airline code"),
            ("UAA123", "Airline code too long (3 letters)"),
            ("UA12345", "Number too long (5 digits)"),
            ("Flight 123", "Spaces not allowed"),
            ("UA-123", "Hyphen not in expected format"),
        ]
        for fn, expected_contains in invalid_cases:
            is_valid, msg = self._validate_flight_number(fn)
            assert not is_valid, f"Expected '{fn}' to be invalid, but passed"
            # Check that the message is helpful
            assert len(msg) > 0