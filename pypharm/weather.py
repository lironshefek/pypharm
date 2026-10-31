"""
weather.py - WeatherReading data class and utilities.
Represents a weather reading with validation.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, repr=False)
class WeatherReading:
    """
    Immutable weather reading from API.
    Validates temperature is a number and numeric fields are finite.
    Fields cannot be changed after creation.

    Args:
        temperature_2m: Temperature in Celsius (must be number)
        rain: Optional rain in mm
        weather_code: Optional WMO weather code

    Raises:
        ValueError: If temperature is not a number or a numeric field is not finite
    """

    temperature_2m: float
    rain: float | None = None
    weather_code: int | None = None

    def __post_init__(self):
        # bool is a subclass of int in Python, so it must be rejected explicitly
        if isinstance(self.temperature_2m, bool) or not isinstance(self.temperature_2m, (int, float)):
            raise ValueError(
                f"temperature_2m must be a number, got {type(self.temperature_2m).__name__}"
            )

        # Normalize and validate before storing values on the frozen dataclass.
        for field, convert in (("temperature_2m", float), ("rain", float), ("weather_code", int)):
            value = getattr(self, field)
            if value is None:
                continue
            try:
                normalized = convert(value)
                finite = isfinite(normalized)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"{field} must be a finite number") from exc
            if not finite:
                raise ValueError(f"{field} must be a finite number")
            object.__setattr__(self, field, normalized)

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


class WeatherReadingBuilder:
    """
    Builder pattern for creating WeatherReading with fluent interface.

    Supports method chaining and provides common presets for testing.
    Example:
        reading = (
            WeatherReadingBuilder()
            .with_temperature(35.0)
            .with_rain(10.0)
            .build()
        )
    """

    def __init__(self):
        self._temperature = 20.0
        self._rain = 0.0
        self._weather_code = 0

    def with_temperature(self, temperature: float) -> "WeatherReadingBuilder":
        """
        Set temperature in Celsius.

        Args:
            temperature: Temperature value (can be negative or very high)

        Returns:
            self for method chaining
        """
        self._temperature = temperature
        return self

    def with_rain(self, rain: float) -> "WeatherReadingBuilder":
        """
        Set rain in mm.

        Args:
            rain: Rainfall amount (non-negative)

        Returns:
            self for method chaining

        Raises:
            ValueError: If rain is negative
        """
        if rain < 0:
            raise ValueError(f"rain must be non-negative, got {rain}")
        self._rain = rain
        return self

    def with_weather_code(self, code: int) -> "WeatherReadingBuilder":
        """
        Set WMO weather code.

        Args:
            code: WMO weather code (0-99)

        Returns:
            self for method chaining
        """
        self._weather_code = code
        return self

    def for_danger_condition(self) -> "WeatherReadingBuilder":
        """Preset for dangerous weather (>30°C)."""
        return self.with_temperature(35.0)

    def for_normal_condition(self) -> "WeatherReadingBuilder":
        """Preset for normal weather (0-30°C)."""
        return self.with_temperature(20.0)

    def for_cold_condition(self) -> "WeatherReadingBuilder":
        """Preset for cold weather (<0°C)."""
        return self.with_temperature(-5.0)

    def reset(self) -> "WeatherReadingBuilder":
        """Reset builder to defaults."""
        self._temperature = 20.0
        self._rain = 0.0
        self._weather_code = 0
        return self

    def build(self) -> WeatherReading:
        """
        Build and return WeatherReading.

        Returns:
            WeatherReading object with configured values
        """
        return WeatherReading(
            temperature_2m=self._temperature,
            rain=self._rain,
            weather_code=self._weather_code,
        )
