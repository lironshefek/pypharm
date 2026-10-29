"""
tests/test_api_client.py - Weather API client tests.
Tests for exception handling, HTTP status validation, and retry logic.
"""

import pytest
from unittest import mock
import requests

from pypharm import (
    WeatherAPIClient,
    get_weather_with_retry,
    WeatherReading,
    WeatherConfig,
    WeatherCommunicationError,
    WeatherHTTPError,
    WeatherJSONError,
    WeatherDataError,
)


class TestWeatherAPIClient:
    """Test WeatherAPIClient HTTP communication."""

    @pytest.fixture
    def client(self):
        """Create a WeatherAPIClient instance."""
        return WeatherAPIClient()

    def test_get_weather_success(self, client):
        """Test successful weather API call."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current": {
                "temperature_2m": 20.5,
                "rain": 2.1,
                "weather_code": 45,
            }
        }

        with mock.patch("requests.get", return_value=mock_response):
            weather = client.get_weather(32.0853, 34.7818)

        assert isinstance(weather, WeatherReading)
        assert weather.temperature_2m == 20.5
        assert weather.rain == 2.1

    def test_get_weather_timeout(self, client):
        """Test timeout error handling."""
        with mock.patch("requests.get", side_effect=requests.Timeout()):
            with pytest.raises(WeatherCommunicationError):
                client.get_weather(32.0853, 34.7818)

    def test_get_weather_connection_error(self, client):
        """Test connection error handling."""
        with mock.patch("requests.get", side_effect=requests.ConnectionError()):
            with pytest.raises(WeatherCommunicationError):
                client.get_weather(32.0853, 34.7818)

    def test_get_weather_http_error(self, client):
        """Test HTTP error handling (401, 403, 500, etc)."""
        mock_response = mock.Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")

        with mock.patch("requests.get", return_value=mock_response):
            with pytest.raises(WeatherHTTPError):
                client.get_weather(32.0853, 34.7818)

    def test_get_weather_invalid_json(self, client):
        """Test invalid JSON response."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with mock.patch("requests.get", return_value=mock_response):
            with pytest.raises(WeatherJSONError):
                client.get_weather(32.0853, 34.7818)

    def test_get_weather_missing_field(self, client):
        """Test missing temperature_2m field."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "current": {"rain": 2.1}  # Missing temperature_2m
        }

        with mock.patch("requests.get", return_value=mock_response):
            with pytest.raises(WeatherDataError):
                client.get_weather(32.0853, 34.7818)

    def test_get_weather_invalid_temperature_value(self, client):
        """Test temperature_2m is not a number."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "current": {"temperature_2m": "abc"}  # Not a number
        }

        with mock.patch("requests.get", return_value=mock_response):
            with pytest.raises(WeatherDataError):
                client.get_weather(32.0853, 34.7818)


class TestRetryLogic:
    """Test retry logic for transient failures."""

    def test_retry_on_timeout(self):
        """Test retry on Timeout - should succeed on 2nd attempt."""
        attempts = []

        def mock_get(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise requests.Timeout()
            # 2nd attempt succeeds
            response = mock.Mock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "current": {"temperature_2m": 15.0, "rain": 1.0}
            }
            return response

        with mock.patch("requests.get", side_effect=mock_get),                 mock.patch("pypharm.api_client.time.sleep") as mock_sleep:
            weather = get_weather_with_retry(32.0853, 34.7818)

        assert len(attempts) == 2
        assert weather.temperature_2m == 15.0
        # One wait between the failed attempt and the successful one
        mock_sleep.assert_called_once_with(WeatherConfig.RETRY_DELAY)

    def test_retry_stops_after_three_attempts(self):
        """Test that a persistent Timeout stops after 3 attempts in total."""
        attempts = []

        def mock_get(*args, **kwargs):
            attempts.append(1)
            raise requests.Timeout()

        with mock.patch("requests.get", side_effect=mock_get),                 mock.patch("pypharm.api_client.time.sleep") as mock_sleep:
            with pytest.raises(WeatherCommunicationError):
                get_weather_with_retry(32.0853, 34.7818)

        assert len(attempts) == 3
        assert mock_sleep.call_count == 2  # waits only between attempts

    def test_no_retry_on_http_error(self):
        """Test NO retry on HTTP 401/403/500 errors."""
        attempts = []

        def mock_get(*args, **kwargs):
            attempts.append(1)
            response = mock.Mock()
            response.status_code = 401
            response.raise_for_status.side_effect = requests.HTTPError("401")
            return response

        with mock.patch("requests.get", side_effect=mock_get):
            with pytest.raises(WeatherHTTPError):
                get_weather_with_retry(32.0853, 34.7818)

        assert len(attempts) == 1  # Only 1 attempt, no retry

    def test_no_retry_on_json_error(self):
        """Test NO retry on JSON parsing errors."""
        attempts = []

        def mock_get(*args, **kwargs):
            attempts.append(1)
            response = mock.Mock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.side_effect = ValueError("Bad JSON")
            return response

        with mock.patch("requests.get", side_effect=mock_get):
            with pytest.raises(WeatherJSONError):
                get_weather_with_retry(32.0853, 34.7818)

        assert len(attempts) == 1  # Only 1 attempt, no retry


class TestWeatherReading:
    """Test WeatherReading object and validation."""

    def test_weather_reading_creation(self):
        """Test creating WeatherReading."""
        reading = WeatherReading(temperature_2m=20.5, rain=2.1, weather_code=45)

        assert reading.temperature_2m == 20.5
        assert reading.rain == 2.1
        assert reading.weather_code == 45

    def test_weather_reading_is_immutable(self):
        """Test a reading cannot be changed after it was received."""
        reading = WeatherReading(temperature_2m=20.5, rain=2.1)

        with pytest.raises(AttributeError):
            reading.temperature_2m = 40.0

        assert reading.temperature_2m == 20.5

    def test_weather_reading_invalid_temperature(self):
        """Test WeatherReading rejects non-numeric temperature."""
        with pytest.raises(ValueError):
            WeatherReading(temperature_2m="not a number")

    def test_weather_reading_from_api_response(self):
        """Test creating WeatherReading from API response dict."""
        api_data = {"temperature_2m": 18.3, "rain": 0.5}
        reading = WeatherReading.from_api_response(api_data)

        assert reading.temperature_2m == 18.3
        assert reading.rain == 0.5

    def test_weather_reading_from_api_missing_temperature(self):
        """Test WeatherReading rejects missing temperature_2m."""
        api_data = {"rain": 0.5}  # Missing temperature_2m

        with pytest.raises(ValueError):
            WeatherReading.from_api_response(api_data)
