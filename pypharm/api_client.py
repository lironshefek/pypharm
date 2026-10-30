"""
api_client.py - Open-Meteo Weather API integration.
Handles HTTP communication with proper error handling and retry logic.
"""

import logging
import requests
import time

from .config import WeatherConfig
from .exceptions import (
    WeatherCommunicationError,
    WeatherHTTPError,
    WeatherJSONError,
    WeatherDataError,
)
from .weather import WeatherReading

logger = logging.getLogger(__name__)


class WeatherAPIClient:
    """Client for Open-Meteo weather API."""

    source = "live"  # shown in the output so real data is never mistaken for mock data

    def __init__(self, config: WeatherConfig = None):
        self.config = config or WeatherConfig()
        self.base_url = self.config.API_URL

    def get_weather(self, latitude: float, longitude: float) -> WeatherReading:
        """
        Get current weather for location.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            WeatherReading object

        Raises:
            WeatherCommunicationError: On timeout or connection failure
            WeatherHTTPError: On HTTP error (4xx, 5xx)
            WeatherJSONError: On JSON parsing failure
            WeatherDataError: On missing/invalid fields
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,rain,weather_code",
        }

        logger.debug(f"Requesting weather for ({latitude}, {longitude})")

        # Send request
        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.config.TIMEOUT
            )
        except requests.Timeout as e:
            logger.error("Weather API timeout")
            raise WeatherCommunicationError("Weather API timeout") from e
        except requests.ConnectionError as e:
            logger.error("Network connection failed")
            raise WeatherCommunicationError("Network connection failed") from e

        # Check HTTP status
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"HTTP error: {response.status_code}")
            raise WeatherHTTPError(f"HTTP {response.status_code}") from e

        # Parse JSON
        try:
            data = response.json()
        except Exception as e:
            logger.error("Invalid JSON from weather API")
            raise WeatherJSONError("Invalid JSON from weather API") from e

        # Create WeatherReading (validates data)
        try:
            if "current" not in data:
                raise KeyError("Missing 'current' section")
            current_data = data["current"]
            if not isinstance(current_data, dict):
                raise TypeError(f"'current' section must be a dict, got {type(current_data).__name__}")
            weather = WeatherReading.from_api_response(current_data)
            logger.info(f"✅ Weather: {weather.temperature_2m}°C")
            return weather
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data validation failed: {e}")
            raise WeatherDataError(str(e)) from e


class MockWeatherClient:
    """
    Offline stand-in for WeatherAPIClient (same get_weather contract).
    Returns fixed, pre-defined readings so the demo runs without network.
    """

    source = "mock"

    # (latitude, longitude) -> temperature in Celsius
    MOCK_TEMPERATURES = {
        (31.9103, 35.1876): 33.5,  # Modiin - hot day, DANGER
        (32.0853, 34.7818): 24.0,  # Tel Aviv - NORMAL
        (32.8193, 34.9927): 21.5,  # Haifa - NORMAL
    }
    DEFAULT_TEMPERATURE = 22.0

    def __init__(self, temperatures: dict = None):
        """temperatures: optional (latitude, longitude) -> Celsius overrides for a demo scenario."""
        self.temperatures = {**self.MOCK_TEMPERATURES, **(temperatures or {})}

    def get_weather(self, latitude: float, longitude: float) -> WeatherReading:
        temperature = self.temperatures.get((latitude, longitude), self.DEFAULT_TEMPERATURE)
        logger.info(f"Mock weather for ({latitude}, {longitude}): {temperature}°C")
        return WeatherReading(temperature_2m=temperature, rain=0.0)


def get_weather_with_retry(
    latitude: float,
    longitude: float,
    config: WeatherConfig = None,
    client=None,
) -> WeatherReading:
    """
    Get weather with retry logic.

    Retries ONLY on:
    - Timeout
    - ConnectionError

    Does NOT retry on:
    - HTTP 4xx (including 401, 403)
    - HTTP 5xx
    - JSON parsing errors (malformed response)
    - Data validation errors (missing fields)

    Args:
        latitude: Location latitude
        longitude: Location longitude
        config: WeatherConfig instance
        client: Object with get_weather(lat, lon); defaults to WeatherAPIClient

    Returns:
        WeatherReading object

    Raises:
        WeatherCommunicationError: If all retries fail (network issues only)
        WeatherHTTPError: On HTTP error (no retry)
        WeatherJSONError: On JSON error (no retry)
        WeatherDataError: On data error (no retry)
    """
    config = config or WeatherConfig()
    client = client or WeatherAPIClient(config)

    for attempt in range(1, config.RETRY_ATTEMPTS + 1):
        try:
            return client.get_weather(latitude, longitude)

        except WeatherCommunicationError as e:
            # Transient error - retry
            if attempt < config.RETRY_ATTEMPTS:
                logger.warning(
                    f"Attempt {attempt} failed (communication), "
                    f"retrying in {config.RETRY_DELAY}s..."
                )
                time.sleep(config.RETRY_DELAY)
            else:
                logger.error(f"All {config.RETRY_ATTEMPTS} attempts failed")
                raise e

        except (WeatherHTTPError, WeatherJSONError, WeatherDataError) as e:
            # Permanent errors - no retry
            logger.error(f"Permanent error (no retry): {type(e).__name__}")
            raise e

    # Should not reach here
    raise WeatherCommunicationError("Unexpected error in retry logic")
