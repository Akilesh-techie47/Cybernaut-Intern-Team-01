"""
Provider interface for flight data sources.

Defines the contract that all flight data provider adapters must implement.
This abstraction allows swapping providers without changing the UI or ML integration code.

Keeps API credentials on the server (environment variables) and never exposes them
in Streamlit client code or source control.
"""

from __future__ import annotations

import json  # Added for _make_request JSON handling
import os
import time
import requests  # Added for provider API calls
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data models shared across providers
# ---------------------------------------------------------------------------

class AirportInfo(BaseModel):
    """Airport details."""

    name: str
    city: str
    country: str
    iata: str
    icao: str
    latitude: float
    longitude: float
    timezone: str


class AircraftPosition(BaseModel):
    """Live aircraft position when available."""

    icao24: str
    callsign: Optional[str] = Field(default=None, description="Flight callsign")
    latitude: Optional[float] = Field(default=None, description="WGS-84 latitude")
    longitude: Optional[float] = Field(default=None, description="WGS-84 longitude")
    altitude: Optional[float] = Field(
        default=None, description="Altitude in feet above mean sea level"
    )
    ground_speed: Optional[float] = Field(
        default=None, description="Ground speed in knots"
    )
    true_track: Optional[float] = Field(
        default=None, description="True track in degrees"
    )
    vertical_rate: Optional[float] = Field(
        default=None, description="Vertical rate in feet per minute"
    )


class FlightInfo(BaseModel):
    """Aggregated flight information from a provider."""

    flight_number: str
    date: str  # YYYY-MM-DD
    status: str  # e.g., "scheduled", "en_route", "landed", "delayed", "cancelled"
    scheduled_departure: Optional[datetime] = None
    estimated_departure: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    scheduled_arrival: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    origin: AirportInfo
    destination: AirportInfo
    aircraft_position: Optional[AircraftPosition] = None
    provider: str
    retrieval_time: datetime
    data_freshness_seconds: float = 0.0
    raw_response: Dict = Field(default_factory=dict)


class ProviderError(BaseModel):
    """Error raised when a provider fails."""

    type: str  # e.g., "rate_limit", "not_found", "ambiguous", "unavailable"
    message: str
    code: Optional[str] = None


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class FlightDataProvider(ABC):
    """Abstract base class for flight data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider requires an API key."""

    @abstractmethod
    def lookup_flight(
        self, flight_number: str, date: str
    ) -> Tuple[Optional[FlightInfo], Optional[ProviderError]]:
        """

        Parameters
        ----------
        flight_number : str
            Flight number (e.g., "UA123", "DL456").
        date : str
            Date in YYYY-MM-DD format.

        Returns
        -------
        (flight_info, error)
        - If successful: (FlightInfo, None)
        - If failed: (None, ProviderError)
        - If ambiguous matches found: (None, ProviderError with type "ambiguous")
        """

    @abstractmethod
    def refresh_position(
        self, flight_info: FlightInfo
    ) -> Tuple[FlightInfo, Optional[ProviderError]]:
        """

        Parameters
        ----------
        flight_info : FlightInfo
            Flight info with origin/destination but possibly no position.

        Returns
        -------
        (updated_flight_info, error)
        """
        pass  # default no-op; subclasses override if they support position tracking

    @abstractmethod
    def get_provider_config(self) -> Dict[str, str]:
        """
        Return provider-specific configuration from environment variables.

        Subclasses implement this to read their required credentials
        (e.g., API keys) from os.environ.
        """
        pass


# ---------------------------------------------------------------------------
# Caching helper for provider responses
# ---------------------------------------------------------------------------

class ProviderCache:
    """
    Simple in-memory cache for provider responses.

    Stores responses keyed by (provider, flight_number, date) with a TTL.
    Prevents repeated API calls for the same flight within the cache window.

    Usage:
        cache = ProviderCache(ttl_seconds=300)  # 5-minute TTL
        cache_key = ("AviationStack", "UA123", "2024-01-15")
        if cache.try_get(cache_key):
            flight_info, error = cache.retried_value  # already populated
        else:
            flight_info, error = provider.lookup_flight(...)
            cache.set(cache_key, (flight_info, error))
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Tuple[str, str, str], Tuple[Optional[FlightInfo], Optional[ProviderError], float]] = {}

    def _is_fresh(self, timestamp: float) -> bool:
        return time.time() - timestamp < self.ttl_seconds

    def try_get(self, key: Tuple[str, str, str]) -> Tuple[Optional[FlightInfo], Optional[ProviderError], bool]:
        """
        Check cache for a key.

        Returns
        -------
        (flight_info, error, fresh)
        - fresh=True: cache hit, values are valid
        - fresh=False: cache miss or stale
        """
        if key in self._cache:
            flight_info, error, timestamp = self._cache[key]
            if self._is_fresh(timestamp):
                return flight_info, error, True
            else:
                # Stale entry; remove it
                del self._cache[key]
        return None, None, False

    def set(self, key: Tuple[str, str, str], flight_info: Optional[FlightInfo], error: Optional[ProviderError]) -> None:
        """Store a result in the cache with the current timestamp."""
        self._cache[key] = (flight_info, error, time.time())


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class FlightDataProvider(ABC):
    """Abstract base class for flight data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider requires an API key."""

    @abstractmethod
    def lookup_flight(
        self, flight_number: str, date: str
    ) -> Tuple[Optional[FlightInfo], Optional[ProviderError]]:
        """

        Parameters
        ----------
        flight_number : str
            Flight number (e.g., "UA123", "DL456").
        date : str
            Date in YYYY-MM-DD format.

        Returns
        -------
        (flight_info, error)
        - If successful: (FlightInfo, None)
        - If failed: (None, ProviderError)
        - If ambiguous matches found: (None, ProviderError with type "ambiguous")
        """

    @abstractmethod
    def refresh_position(
        self, flight_info: FlightInfo
    ) -> Tuple[FlightInfo, Optional[ProviderError]]:
        """

        Parameters
        ----------
        flight_info : FlightInfo
            Flight info with origin/destination but possibly no position.

        Returns
        -------
        (updated_flight_info, error)
        """
        pass  # default no-op; subclasses override if they support position tracking

    @abstractmethod
    def get_provider_config(self) -> Dict[str, str]:
        """
        Return provider-specific configuration from environment variables.

        Subclasses implement this to read their required credentials
        (e.g., API keys) from os.environ.
        """
        pass


# ---------------------------------------------------------------------------
# AviationStack provider adapter
# ---------------------------------------------------------------------------

class AviationStackProvider(FlightDataProvider):
    """
    AviationStack Flight API adapter.

    Features:
    - Flight lookup by flight number and date
    - Current status and scheduled/estimated/actual departure/arrival times
    - Origin and destination airport details (IATA/ICAO, city, country)
    - Aircraft position when available (basic plan may not include live tracks)
    - Provider source, retrieval time, and data freshness
    - Configurable request timeouts and caching
    - Proper error handling for key missing, rate limits, and network failures

    API: https://aviationstack.com/
    Free tier: 250 requests/month (sufficient for development/demo)
    Paid plans available for higher volume.

    API key should be set as environment variable: AVIATIONSTACK_ACCESS_KEY
    Never commit this key to source control.
    """

    @property
    def name(self) -> str:
        return "AviationStack"

    @property
    def requires_api_key(self) -> bool:
        return True

    def __init__(self):
        super().__init__()
        self.cache = ProviderCache(ttl_seconds=300)  # 5-minute TTL

    def get_provider_config(self) -> Dict[str, str]:
        """Read AviationStack API key from environment."""
        key = os.environ.get("AVIATIONSTACK_ACCESS_KEY", "")
        return {"access_key": key}

    def _make_request(self, params: Dict[str, str]) -> Tuple[Optional[Dict], Optional[ProviderError]]:
        """
        Make a request to AviationStack /v1/flights endpoint.

        Returns
        -------
        (response_json, error)
        """
        config = self.get_provider_config()
        access_key = config.get("access_key", "")

        if not access_key:
            return None, ProviderError(
                type="configuration",
                message="AviationStack API key not configured. Set AVIATIONSTACK_ACCESS_KEY environment variable.",
            )

        params["access_key"] = access_key

        try:
            timeout = 15  # seconds
            response = requests.get(
                "http://api.aviationstack.com/v1/flights", params=params, timeout=timeout
            )
            if response.status_code == 429:
                return None, ProviderError(
                    type="rate_limit",
                    message="AviationStack rate limit exceeded. Please try again later.",
                )
            if response.status_code != 200:
                return None, ProviderError(
                    type="provider_error",
                    message=f"AviationStack API returned HTTP {response.status_code}",
                    code=str(response.status_code),
                )

            try:
                json_data = response.json()
            except json.JSONDecodeError:
                return None, ProviderError(
                    type="provider_error",
                    message="AviationStack returned invalid JSON response.",
                )

            return json_data, None

        except requests.exceptions.Timeout:
            return None, ProviderError(
                type="timeout",
                message="AviationStack request timed out after 15 seconds.",
            )
        except requests.exceptions.ConnectionError:
            return None, ProviderError(
                type="connection_error",
                message="Could not connect to AviationStack. Check your network.",
            )
        except requests.exceptions.RequestException as e:
            return None, ProviderError(
                type="provider_error",
                message=f"AviationStack request failed: {e}",
            )

    def _check_ambiguous_matches(
        self, flight_data: Dict, flight_number: str
    ) -> List[Dict]:
        """
        Check if the API returned ambiguous matches for the flight number.

        AviationStack may return multiple flights matching the same number
        (especially if the flight number is reused or spans multiple airlines).
        """
        data = flight_data.get("data", [])
        matches = []
        for record in data:
            # Check if flight number matches (case-insensitive)
            fn = record.get("flight", {}).get("iata", "").upper()
            if fn == flight_number.upper():
                matches.append(record)
        return matches

    def lookup_flight(
        self, flight_number: str, date: str
    ) -> Tuple[Optional[FlightInfo], Optional[ProviderError]]:
        """
        Look up a flight by flight number and date using AviationStack.

        Parameters
        ----------
        flight_number : str
            Flight number (e.g., "UA123", "DL456").
        date : str
            Date in YYYY-MM-DD format.

        Returns
        -------
        (flight_info, error)
        - If successful: (FlightInfo, None)
        - If failed: (None, ProviderError)
        - If ambiguous matches: (None, ProviderError with type "ambiguous")
        """
        # Check cache first
        cache_key = ("AviationStack", flight_number, date)
        cached_flight, cached_error, cache_hit = self.cache.try_get(cache_key)
        if cache_hit:
            return cached_flight, cached_error

        import json

        params = {
            "flight_number": flight_number,
            "flight_date": date,
            "limit": "10",  # limit results to avoid excess
        }

        response_json, error = self._make_request(params)
        if error:
            # Store in cache even on error
            self.cache.set(cache_key, None, error)
            return None, error

        # Check for ambiguous matches
        matches = self._check_ambiguous_matches(response_json, flight_number)
        if len(matches) > 1:
            # Multiple flights with the same number on that date
            error_msg = f"Ambiguous flight number: {flight_number} matches {len(matches)} flights on {date}"
            error = ProviderError(type="ambiguous", message=error_msg)
            self.cache.set(cache_key, None, error)
            return None, error

        if not response_json.get("data"):
            error = ProviderError(
                type="not_found",
                message=f"No flight found for {flight_number} on {date}. "
                "Please verify the flight number and date.",
            )
            self.cache.set(cache_key, None, error)
            return None, error

        # Parse the first matching flight
        try:
            flight_info = _parse_aviationstack_flight(
                response_json, flight_number, date
            )
            # Validate that essential flight data is present
            if not flight_info.origin.iata or not flight_info.destination.iata:
                error = ProviderError(
                    type="parsing_error",
                    message="Failed to parse flight data: missing essential airport information.",
                )
                self.cache.set(cache_key, None, error)
                return None, error
            # Store in cache on success
            self.cache.set(cache_key, flight_info, None)
            return flight_info, None
        except Exception as e:
            error = ProviderError(
                type="parsing_error",
                message=f"Failed to parse AviationStack response: {e}",
            )
            self.cache.set(cache_key, None, error)
            return None, error

    def refresh_position(
        self, flight_info: FlightInfo
    ) -> Tuple[FlightInfo, Optional[ProviderError]]:
        """
        Refresh the live aircraft position for a known flight.

        AviationStack basic plan does not include live tracking (latitude/longitude
        for en-route aircraft). This method attempts to augment position data from
        the available fields, but may return the same info or None.

        For live position tracking, consider integrating with OpenSky Network
        (free, open ADS-B coverage) separately.
        """
        # AviationStack does not provide live en-route position in the basic plan.
        # We return the flight info with position set to None and note this.
        # If the flight has already landed, we also skip position refresh.

        if flight_info.aircraft_position is not None:
            # Already have position; we could refresh it, but AviationStack
            # doesn't provide updated positions in the basic plan.
            pass

        # Mark data freshness
        from datetime import datetime as _dt

        age = (_dt.now() - flight_info.retrieval_time).total_seconds()
        # Create updated info with freshness
        updated = flight_info.model_copy(update={"data_freshness_seconds": age})
        return updated, None


def _parse_aviationstack_flight(
    flight_data: Dict, flight_number: str, date_str: str
) -> FlightInfo:
    """
    Parse AviationStack API response into a FlightInfo model.

    Parameters
    ----------
    flight_data : Dict
        Raw JSON response from AviationStack /v1/flights endpoint.
    flight_number : str
        The flight number requested.
    date_str : str
        The date requested in YYYY-MM-DD format.

    Returns
    -------
    FlightInfo
        Populated flight info model.
    """
    # AviationStack returns nested data; extract safely
    data = flight_data.get("data", [])
    if not data:
        raise ValueError("No flight data in AviationStack response")

    # Use the first matching record
    record = data[0]

    # Status
    status = record.get("flight_status", "unknown")

    # Departure/Arrival times (ISO format strings from AviationStack)
    def _parse_dt(val):
        """Parse a datetime string from AviationStack, return datetime or None."""
        if not val:
            return None
        try:
            # AviationStack ISO format: "2024-01-15T10:30:00"
            from datetime import datetime as _dt
            return _dt.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return None

    scheduled_dep = _parse_dt(record.get("departure", {}).get("scheduled"))
    estimated_dep = _parse_dt(record.get("departure", {}).get("estimated"))
    actual_dep = _parse_dt(record.get("departure", {}).get("actual"))
    scheduled_arr = _parse_dt(record.get("arrival", {}).get("scheduled"))
    estimated_arr = _parse_dt(record.get("arrival", {}).get("estimated"))
    actual_arr = _parse_dt(record.get("arrival", {}).get("actual"))

    # Origin airport
    origin_airport = record.get("departure", {}).get("airport", "")
    origin_city = record.get("departure", {}).get("city", "")
    origin_country = record.get("departure", {}).get("country", "")
    origin_iata = record.get("departure", {}).get("iata", "")
    origin_icao = record.get("departure", {}).get("icao", "")

    # Destination airport
    dest_airport = record.get("arrival", {}).get("airport", "")
    dest_city = record.get("arrival", {}).get("city", "")
    dest_country = record.get("arrival", {}).get("country", "")
    dest_iata = record.get("arrival", {}).get("iata", "")
    dest_icao = record.get("arrival", {}).get("icao", "")

    # Build AirportInfo models
    origin_info = AirportInfo(
        name=origin_airport,
        city=origin_city,
        country=origin_country,
        iata=origin_iata,
        icao=origin_icao,
        latitude=record.get("departure", {}).get("latitude", 0.0),
        longitude=record.get("departure", {}).get("longitude", 0.0),
        timezone=record.get("departure", {}).get("timezone", "UTC"),
    )

    dest_info = AirportInfo(
        name=dest_airport,
        city=dest_city,
        country=dest_country,
        iata=dest_iata,
        icao=dest_icao,
        latitude=record.get("arrival", {}).get("latitude", 0.0),
        longitude=record.get("arrival", {}).get("longitude", 0.0),
        timezone=record.get("arrival", {}).get("timezone", "UTC"),
    )

    # Aircraft position (from flight tracking data if available)
    # AviationStack basic plan doesn't always include position; we set it to None
    # and rely on a separate position lookup if needed.
    aircraft_pos = None
    # Check for velocity/heading data that AviationStack may provide
    velocity = record.get("velocity", {})
    heading = record.get("heading", {})

    # Try to get position from the data we have
    lat = record.get("departure", {}).get("latitude")
    lon = record.get("departure", {}).get("longitude")
    if lat is not None and lon is not None:
        aircraft_pos = AircraftPosition(
            icao24="",  # Not provided by AviationStack basic
            callsign=flight_number,
            latitude=float(lat),
            longitude=float(lon),
            ground_speed=velocity.get("airspeed") if velocity else None,
            true_track=heading.get("degrees") if heading else None,
        )

    from datetime import datetime as _dt

    retrieval_time = _dt.now()

    return FlightInfo(
        flight_number=flight_number,
        date=date_str,
        status=status,
        scheduled_departure=scheduled_dep,
        estimated_departure=estimated_dep,
        actual_departure=actual_dep,
        scheduled_arrival=scheduled_arr,
        estimated_arrival=estimated_arr,
        actual_arrival=actual_arr,
        origin=origin_info,
        destination=dest_info,
        aircraft_position=aircraft_pos,
        provider="AviationStack",
        retrieval_time=retrieval_time,
        raw_response=flight_data,
    )