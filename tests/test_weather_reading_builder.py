"""TDD Red-Green-Refactor: WeatherReadingBuilder pattern."""

import pytest

from pypharm.weather import WeatherReading, WeatherReadingBuilder


def test_weather_reading_builder_basic():
    """RED: Builder should create WeatherReading with fluent interface."""
    builder = WeatherReadingBuilder()
    reading = (
        builder.with_temperature(25.0)
        .with_rain(5.5)
        .with_weather_code(0)
        .build()
    )

    assert reading.temperature_2m == 25.0
    assert reading.rain == 5.5
    assert reading.weather_code == 0


def test_weather_reading_builder_defaults():
    """Builder should provide reasonable defaults."""
    builder = WeatherReadingBuilder()
    reading = builder.build()

    assert reading.temperature_2m == 20.0
    assert reading.rain == 0.0
    assert reading.weather_code == 0


def test_weather_reading_builder_partial():
    """Builder should support partial builds."""
    reading = (
        WeatherReadingBuilder()
        .with_temperature(35.0)
        .build()
    )

    assert reading.temperature_2m == 35.0
    assert reading.rain == 0.0


def test_weather_reading_builder_chain():
    """Builder should support method chaining."""
    reading = (
        WeatherReadingBuilder()
        .with_temperature(0.0)
        .with_rain(10.0)
        .with_temperature(5.0)  # Override
        .build()
    )

    assert reading.temperature_2m == 5.0
    assert reading.rain == 10.0


def test_weather_reading_builder_edge_cases():
    """Builder should handle edge case temperatures."""
    cold = WeatherReadingBuilder().with_temperature(-15.0).build()
    hot = WeatherReadingBuilder().with_temperature(50.0).build()

    assert cold.temperature_2m == -15.0
    assert hot.temperature_2m == 50.0
