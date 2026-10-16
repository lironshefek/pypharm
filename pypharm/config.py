"""
config.py - Weather API configuration.
Load settings from environment or use defaults.
"""

import os


class WeatherConfig:
    """Configuration for Weather API client."""

    # API endpoint
    API_URL = os.getenv("WEATHER_API_URL", "https://api.open-meteo.com/v1/forecast")

    # Request settings
    TIMEOUT = int(os.getenv("WEATHER_TIMEOUT", "5"))
    RETRY_ATTEMPTS = int(os.getenv("WEATHER_RETRY_ATTEMPTS", "3"))
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
