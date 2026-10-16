"""
weather.py - WeatherReading data class and utilities.
Represents a weather reading with validation.
"""


class WeatherReading:
    """
    Immutable weather reading from API.
    Validates temperature is a number.
    """

    def __init__(self, temperature_2m: float, rain: float = None, weather_code: int = None):
        """
        Create a weather reading.

        Args:
            temperature_2m: Temperature in Celsius (must be number)
            rain: Optional rain in mm
            weather_code: Optional WMO weather code

        Raises:
            ValueError: If temperature is not a number
        """
        if not isinstance(temperature_2m, (int, float)):
            raise ValueError(f"temperature_2m must be a number, got {type(temperature_2m).__name__}")

        self.temperature_2m = float(temperature_2m)
        self.rain = float(rain) if rain is not None else None
        self.weather_code = int(weather_code) if weather_code is not None else None

    def __repr__(self) -> str:
        return f"WeatherReading(temp={self.temperature_2m}°C, rain={self.rain}mm)"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "temperature_2m": self.temperature_2m,
            "rain": self.rain,
            "weather_code": self.weather_code,
        }

    @classmethod
    def from_api_response(cls, data: dict) -> "WeatherReading":
        """
        Create WeatherReading from API response dict.

        Args:
            data: Dictionary with 'temperature_2m' and optional fields

        Raises:
            ValueError: If temperature_2m is missing or not a number
        """
        if "temperature_2m" not in data:
            raise ValueError("Missing required field: temperature_2m")

        return cls(
            temperature_2m=data["temperature_2m"],
            rain=data.get("rain"),
            weather_code=data.get("weather_code"),
        )
