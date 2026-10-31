"""
config.py - Weather API configuration.
Load settings from environment or use defaults.
"""

import os


def validate_retry_attempts(value: int) -> int:
    """Require one to three total attempts, including the initial request."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 3:
        raise ValueError(
            "WEATHER_RETRY_ATTEMPTS must be an integer between 1 and 3 "
            f"(inclusive), got {value!r}"
        )
    return value


def _read_retry_attempts() -> int:
    value = os.getenv("WEATHER_RETRY_ATTEMPTS", "3")
    try:
        attempts = int(value)
    except ValueError as exc:
        raise ValueError(
            "WEATHER_RETRY_ATTEMPTS must be an integer between 1 and 3 "
            f"(inclusive), got {value!r}"
        ) from exc
    return validate_retry_attempts(attempts)


class WeatherConfig:
    """Configuration for Weather API client."""

    # API endpoint
    API_URL = os.getenv("WEATHER_API_URL", "https://api.open-meteo.com/v1/forecast")

    # Request settings
    TIMEOUT = int(os.getenv("WEATHER_TIMEOUT", "5"))
    RETRY_ATTEMPTS = _read_retry_attempts()
    RETRY_DELAY = int(os.getenv("WEATHER_RETRY_DELAY", "1"))

    # Mode: "default" (mock) or "live" (real API)
    MODE = os.getenv("WEATHER_MODE", "default")

    @classmethod
    def is_live_mode(cls) -> bool:
        """Check if using real API (not mock)."""
        return cls.MODE.lower() == "live"

    @classmethod
    def is_mock_mode(cls) -> bool:
        """Check if using mock data (default)."""
        return cls.MODE.lower() == "default"
