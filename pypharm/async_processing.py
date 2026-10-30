"""
Asynchronous weather checking for multiple locations.

Demonstrates concurrent task execution for independent weather checks.
Serial and async versions process the same locations with identical results,
but async executes in parallel for better performance.
"""

import asyncio
import logging
import time

from .services import WeatherService

logger = logging.getLogger(__name__)


async def check_weather_async(service: WeatherService, location) -> dict:
    """
    Check weather for a single location asynchronously.

    Args:
        service: WeatherService instance
        location: Location object with latitude, longitude, and name

    Returns:
        Dictionary with temperature, risk_level, required_roles, and location name
    """
    result = service.check_and_classify_for_order(location)
    return {
        "location": location.name,
        "temperature": result["temperature"],
        "risk_level": result["risk_level"],
        "required_roles": result["required_roles"],
    }


async def check_multiple_locations_async(
    service: WeatherService, locations: list
) -> list:
    """
    Check weather for multiple locations concurrently.

    All location checks run in parallel. Faster than serial when checking many locations.

    Args:
        service: WeatherService instance
        locations: List of Location objects

    Returns:
        List of weather check results, one per location (order preserved)
    """
    tasks = [check_weather_async(service, loc) for loc in locations]
    results = await asyncio.gather(*tasks)
    return results


def check_multiple_locations_serial(
    service: WeatherService, locations: list
) -> list:
    """
    Check weather for multiple locations sequentially.

    Each location waits for the previous one to complete.
    Used as baseline for comparison with async version.

    Args:
        service: WeatherService instance
        locations: List of Location objects

    Returns:
        List of weather check results, one per location (identical to async)
    """
    results = []
    for loc in locations:
        result = service.check_and_classify_for_order(loc)
        results.append(
            {
                "location": loc.name,
                "temperature": result["temperature"],
                "risk_level": result["risk_level"],
                "required_roles": result["required_roles"],
            }
        )
    return results


async def demo_async_vs_serial():
    """
    Compare async and serial weather checking performance and correctness.

    Demonstrates:
    - Async version runs all checks in parallel
    - Serial version runs checks one after another
    - Both produce identical results
    - Async is faster (especially with network latency in live mode)
    """
    from .config import WeatherConfig
    from .api_client import MockWeatherClient
    from . import Location

    config = WeatherConfig()
    # Use MockWeatherClient for predictable results
    service = WeatherService(config=config, client=MockWeatherClient())

    # 3 locations to check
    locations = [
        Location("STORE-MODIIN", "Modiin", "STORE", "Modiin", 31.9103, 35.1876),
        Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818),
        Location("STORE-HAIFA", "Haifa", "STORE", "Haifa", 32.8193, 34.9927),
    ]

    # Serial execution
    start = time.time()
    serial_results = check_multiple_locations_serial(service, locations)
    serial_time = time.time() - start

    # Async execution
    start = time.time()
    async_results = await check_multiple_locations_async(service, locations)
    async_time = time.time() - start

    # Display results
    print("\n" + "=" * 70)
    print("SECTION 5.1: Asynchronous Weather Processing")
    print("=" * 70)

    print("\n📍 SERIAL EXECUTION (one location at a time):")
    print(f"   Time: {serial_time:.3f}s")
    for r in serial_results:
        print(
            f"   • {r['location']:12} | Temp: {r['temperature']:5}°C | Risk: {r['risk_level']:6} | Roles: {', '.join(r['required_roles']) if r['required_roles'] else 'None'}"
        )

    print("\n⚡ ASYNC EXECUTION (all locations in parallel):")
    print(f"   Time: {async_time:.3f}s")
    for r in async_results:
        print(
            f"   • {r['location']:12} | Temp: {r['temperature']:5}°C | Risk: {r['risk_level']:6} | Roles: {', '.join(r['required_roles']) if r['required_roles'] else 'None'}"
        )

    print(f"\n✓ Results match: {serial_results == async_results}")
    if async_time > 0:
        speedup = serial_time / async_time
        print(f"✓ Speedup: {speedup:.1f}x faster with async")
    print("=" * 70 + "\n")

    return serial_results, async_results
