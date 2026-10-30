"""
Asynchronous weather checks for several branches (simulation, no network).

Each branch check is an independent task: it does not need the result of
another check to start. The waiting time of a real API call is simulated with
``await asyncio.sleep(...)`` and the temperatures come from local data.

Two versions run the same tasks on the same data:
- serial: awaits each check before starting the next one;
- concurrent: schedules all checks with ``asyncio.gather`` before collecting
  the results.

Both return one result per branch, in the input order, even when the checks
finish in a different order.
"""

import asyncio
import logging

from .services import WeatherService

logger = logging.getLogger(__name__)

# location_id -> (temperature in Celsius, simulated response time in seconds)
SIMULATED_BRANCH_WEATHER = {
    "WH-CENTRAL": (33.5, 0.3),   # Modiin - hot day, DANGER
    "STORE-TLV": (24.0, 0.2),    # Tel Aviv - NORMAL
    "STORE-HAIFA": (21.5, 0.1),  # Haifa - NORMAL
}


async def check_branch_weather(
    location_id: str,
    service: WeatherService,
    weather_data: dict = SIMULATED_BRANCH_WEATHER,
) -> dict:
    """Simulate one weather request for a branch and classify its risk."""
    if location_id not in weather_data:
        raise ValueError(f"No simulated weather data for location {location_id!r}")

    temperature, delay = weather_data[location_id]
    logger.info(f"Checking weather for {location_id} (simulated wait {delay}s)")
    await asyncio.sleep(delay)

    risk_level = service.classify_risk(temperature)
    logger.info(f"Finished {location_id}: {temperature}°C -> {risk_level}")
    return {
        "location_id": location_id,
        "temperature": temperature,
        "risk_level": risk_level,
        "required_roles": service.get_required_roles(risk_level),
    }


async def check_branches_serial(
    location_ids: list,
    service: WeatherService,
    weather_data: dict = SIMULATED_BRANCH_WEATHER,
) -> list:
    """Check the branches one after another - each check waits for the previous one."""
    results = []
    for location_id in location_ids:
        results.append(await check_branch_weather(location_id, service, weather_data))
    return results


async def check_branches_concurrent(
    location_ids: list,
    service: WeatherService,
    weather_data: dict = SIMULATED_BRANCH_WEATHER,
) -> list:
    """
    Schedule all branch checks first, then collect the results.

    gather() returns the results in the order of the tasks it received,
    so the output follows the input order and not the finish order.
    """
    tasks = [check_branch_weather(location_id, service, weather_data) for location_id in location_ids]
    return list(await asyncio.gather(*tasks))
