"""Tests for asynchronous weather checking."""

import asyncio
from unittest.mock import Mock

import pytest

from pypharm import (
    Location,
    WeatherReading,
    WeatherService,
    check_weather_async,
    check_multiple_locations_async,
    check_multiple_locations_serial,
)


@pytest.fixture
def location():
    return Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818)


@pytest.fixture
def locations():
    return [
        Location("STORE-MODIIN", "Modiin", "STORE", "Modiin", 31.9103, 35.1876),
        Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818),
        Location("STORE-HAIFA", "Haifa", "STORE", "Haifa", 32.8193, 34.9927),
    ]


def test_check_weather_async_normal_temperature(location):
    """Async check returns correct risk level for normal temperature."""
    async def run_test():
        service = WeatherService(
            client=Mock(
                get_weather=Mock(return_value=WeatherReading(temperature_2m=24.0))
            )
        )

        result = await check_weather_async(service, location)

        assert result["location"] == "Tel Aviv"
        assert result["temperature"] == 24.0
        assert result["risk_level"] == "NORMAL"
        assert "WAREHOUSE_MANAGER" in result["required_roles"]

    asyncio.run(run_test())


def test_check_weather_async_danger_temperature(location):
    """Async check returns correct risk level for danger temperature."""
    async def run_test():
        service = WeatherService(
            client=Mock(
                get_weather=Mock(return_value=WeatherReading(temperature_2m=35.0))
            )
        )

        result = await check_weather_async(service, location)

        assert result["location"] == "Tel Aviv"
        assert result["temperature"] == 35.0
        assert result["risk_level"] == "DANGER"
        assert result["required_roles"] == ["LOGISTICS_MANAGER"]

    asyncio.run(run_test())


def test_check_multiple_locations_async_all_concurrent(locations):
    """Async processes multiple locations concurrently."""
    async def run_test():
        service = WeatherService(
            client=Mock(
                get_weather=Mock(
                    side_effect=[
                        WeatherReading(temperature_2m=33.5),
                        WeatherReading(temperature_2m=24.0),
                        WeatherReading(temperature_2m=21.5),
                    ]
                )
            )
        )

        results = await check_multiple_locations_async(service, locations)

        assert len(results) == 3
        assert results[0]["location"] == "Modiin"
        assert results[0]["risk_level"] == "DANGER"
        assert results[1]["location"] == "Tel Aviv"
        assert results[1]["risk_level"] == "NORMAL"
        assert results[2]["location"] == "Haifa"
        assert results[2]["risk_level"] == "NORMAL"

    asyncio.run(run_test())


def test_check_multiple_locations_serial_identical_to_async(locations):
    """Serial version produces same results as async."""
    service = WeatherService(
        client=Mock(
            get_weather=Mock(
                side_effect=[
                    WeatherReading(temperature_2m=33.5),
                    WeatherReading(temperature_2m=24.0),
                    WeatherReading(temperature_2m=21.5),
                ]
            )
        )
    )

    serial_results = check_multiple_locations_serial(service, locations)

    assert len(serial_results) == 3
    assert serial_results[0]["location"] == "Modiin"
    assert serial_results[0]["temperature"] == 33.5
    assert serial_results[1]["location"] == "Tel Aviv"
    assert serial_results[1]["temperature"] == 24.0
    assert serial_results[2]["location"] == "Haifa"
    assert serial_results[2]["temperature"] == 21.5


def test_async_and_serial_produce_identical_results(locations):
    """Async and serial versions produce identical results."""
    async def run_test():
        service = WeatherService(
            client=Mock(
                get_weather=Mock(
                    side_effect=[
                        WeatherReading(temperature_2m=33.5),
                        WeatherReading(temperature_2m=24.0),
                        WeatherReading(temperature_2m=21.5),
                    ]
                )
            )
        )

        serial_results = check_multiple_locations_serial(service, locations)

        # Reset mock for async
        service.client.get_weather.side_effect = [
            WeatherReading(temperature_2m=33.5),
            WeatherReading(temperature_2m=24.0),
            WeatherReading(temperature_2m=21.5),
        ]

        async_results = await check_multiple_locations_async(service, locations)

        assert len(async_results) == len(serial_results)
        for async_r, serial_r in zip(async_results, serial_results):
            assert async_r["location"] == serial_r["location"]
            assert async_r["temperature"] == serial_r["temperature"]
            assert async_r["risk_level"] == serial_r["risk_level"]
            assert async_r["required_roles"] == serial_r["required_roles"]

    asyncio.run(run_test())


def test_async_results_order_preserved(locations):
    """Async results maintain location order."""
    async def run_test():
        service = WeatherService(
            client=Mock(
                get_weather=Mock(
                    side_effect=[
                        WeatherReading(temperature_2m=0.0),
                        WeatherReading(temperature_2m=30.0),
                        WeatherReading(temperature_2m=-5.0),
                    ]
                )
            )
        )

        results = await check_multiple_locations_async(service, locations)

        assert results[0]["location"] == locations[0].name
        assert results[1]["location"] == locations[1].name
        assert results[2]["location"] == locations[2].name
        assert results[0]["temperature"] == 0.0
        assert results[1]["temperature"] == 30.0
        assert results[2]["temperature"] == -5.0

    asyncio.run(run_test())


def test_serial_and_async_edge_temperatures(locations):
    """Both versions handle edge case temperatures correctly."""
    service = WeatherService(
        client=Mock(
            get_weather=Mock(
                side_effect=[
                    WeatherReading(temperature_2m=-15.0),
                    WeatherReading(temperature_2m=0.0),
                    WeatherReading(temperature_2m=50.0),
                ]
            )
        )
    )

    serial_results = check_multiple_locations_serial(service, locations)

    assert serial_results[0]["risk_level"] == "DANGER"  # -15 < 0
    assert serial_results[1]["risk_level"] == "NORMAL"  # 0 is included
    assert serial_results[2]["risk_level"] == "DANGER"  # 50 > 30

    async def run_async():
        service.client.get_weather.side_effect = [
            WeatherReading(temperature_2m=-15.0),
            WeatherReading(temperature_2m=0.0),
            WeatherReading(temperature_2m=50.0),
        ]
        return await check_multiple_locations_async(service, locations)

    async_results = asyncio.run(run_async())

    assert async_results[0]["risk_level"] == "DANGER"
    assert async_results[1]["risk_level"] == "NORMAL"
    assert async_results[2]["risk_level"] == "DANGER"
