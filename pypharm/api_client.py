"""
api_client.py - Open-Meteo Weather API integration.
Simple HTTP client with retry logic.
"""

import requests
import time


class WeatherAPIClient:
    """Client for Open-Meteo weather API."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def get_weather(self, latitude: float, longitude: float) -> dict:
        """
        Get current weather for location.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Dict with temperature_2m (and other fields)

        Raises:
            Exception: On network error, invalid response, or missing field
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,rain,weather_code",
        }

        # Send request with 5 second timeout
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=5)
        except requests.Timeout:
            raise Exception("Weather API timeout")
        except requests.ConnectionError:
            raise Exception("Network connection failed")

        # Check HTTP status using raise_for_status()
        try:
            response.raise_for_status()
        except requests.HTTPError:
            raise Exception(f"Weather API error: HTTP {response.status_code}")

        # Parse JSON
        try:
            data = response.json()
        except Exception:
            raise Exception("Invalid JSON from weather API")

        # Check for required field
        if "current" not in data or "temperature_2m" not in data["current"]:
            raise Exception("Missing temperature_2m in API response")

        return data["current"]


def get_weather_with_retry(latitude: float, longitude: float, max_attempts: int = 3) -> dict:
    """
    Get weather with retries.

    Retries on: Timeout, ConnectionError, Invalid JSON
    Does NOT retry on: HTTP 400 errors, Missing fields

    Args:
        latitude: Location latitude
        longitude: Location longitude
        max_attempts: Number of attempts (default: 3)

    Returns:
        Dict with weather data

    Raises:
        Exception: If all retries fail or permanent error
    """
    client = WeatherAPIClient()

    for attempt in range(1, max_attempts + 1):
        try:
            return client.get_weather(latitude, longitude)
        except Exception as e:
            error_msg = str(e)

            # Permanent errors - don't retry
            if "HTTP 400" in error_msg or "Missing" in error_msg:
                raise e

            # Transient errors - retry
            if attempt < max_attempts:
                print(f"Attempt {attempt} failed, retrying in 1s...")
                time.sleep(1)
            else:
                print(f"Failed after {max_attempts} attempts")
                raise e
