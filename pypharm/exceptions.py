"""
exceptions.py - Weather API exception hierarchy.
Four distinct exception types for different failure scenarios.
"""


class WeatherAPIException(Exception):
    """Base exception for all weather API errors."""
    pass


class WeatherCommunicationError(WeatherAPIException):
    """Raised when communication with API fails (Timeout, ConnectionError)."""
    pass


class WeatherHTTPError(WeatherAPIException):
    """Raised when HTTP response indicates an error (4xx, 5xx)."""
    pass


class WeatherJSONError(WeatherAPIException):
    """Raised when JSON parsing fails (malformed response)."""
    pass


class WeatherDataError(WeatherAPIException):
    """Raised when response data doesn't match required structure."""
    pass
