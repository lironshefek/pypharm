"""Tests for the serial and concurrent branch weather checks (simulation, no network)."""

import asyncio
from unittest.mock import patch

import pytest

from pypharm import WeatherService, check_branch_weather, check_branches_concurrent, check_branches_serial
from pypharm.api_client import MockWeatherClient

BRANCHES = ["WH-CENTRAL", "STORE-TLV", "STORE-HAIFA"]

# Longest wait first, so the checks finish in the reverse of the input order.
WEATHER_DATA = {
    "WH-CENTRAL": (33.5, 0.03),
    "STORE-TLV": (24.0, 0.02),
    "STORE-HAIFA": (-2.0, 0.01),
}


@pytest.fixture
def service():
    return WeatherService(client=MockWeatherClient())


@pytest.fixture
def timeline():
    """Replace asyncio.sleep with a recorder: no real waiting, but every task still yields."""
    events = []
    real_sleep = asyncio.sleep

    async def recording_sleep(delay):
        events.append("start")
        await real_sleep(0)
        events.append("end")

    with patch("pypharm.async_processing.asyncio.sleep", recording_sleep):
        yield events


@pytest.mark.parametrize("location_id,expected_risk,expected_roles", [
    ("WH-CENTRAL", "DANGER", ["LOGISTICS_MANAGER"]),                      # 33.5 > 30
    ("STORE-TLV", "NORMAL", ["WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"]),  # 24.0
    ("STORE-HAIFA", "DANGER", ["LOGISTICS_MANAGER"]),                     # -2.0 < 0
])
def test_branch_check_classifies_simulated_temperature(service, timeline, location_id, expected_risk, expected_roles):
    result = asyncio.run(check_branch_weather(location_id, service, WEATHER_DATA))

    assert result["location_id"] == location_id
    assert result["risk_level"] == expected_risk
    assert result["required_roles"] == expected_roles


def test_unknown_branch_is_rejected(service, timeline):
    with pytest.raises(ValueError, match="STORE-EILAT"):
        asyncio.run(check_branch_weather("STORE-EILAT", service, WEATHER_DATA))


def test_serial_waits_for_each_check_before_starting_the_next(service, timeline):
    asyncio.run(check_branches_serial(BRANCHES, service, WEATHER_DATA))

    assert timeline == ["start", "end"] * 3


def test_concurrent_starts_all_checks_before_any_finishes(service, timeline):
    asyncio.run(check_branches_concurrent(BRANCHES, service, WEATHER_DATA))

    assert timeline == ["start"] * 3 + ["end"] * 3


def test_serial_and_concurrent_give_identical_results(service, timeline):
    serial = asyncio.run(check_branches_serial(BRANCHES, service, WEATHER_DATA))
    concurrent = asyncio.run(check_branches_concurrent(BRANCHES, service, WEATHER_DATA))

    assert concurrent == serial
    assert [r["temperature"] for r in concurrent] == [33.5, 24.0, -2.0]


def test_concurrent_results_follow_input_order_even_when_finish_order_differs(service):
    finished = []
    real_check = check_branch_weather

    async def tracking_check(location_id, service, weather_data):
        result = await real_check(location_id, service, weather_data)
        finished.append(location_id)
        return result

    # Real (short) waits here, so the finish order is decided by the delays.
    with patch("pypharm.async_processing.check_branch_weather", tracking_check):
        results = asyncio.run(check_branches_concurrent(BRANCHES, service, WEATHER_DATA))

    assert finished == ["STORE-HAIFA", "STORE-TLV", "WH-CENTRAL"]
    assert [r["location_id"] for r in results] == BRANCHES
