from unittest.mock import Mock

import pytest

from pypharm import Location, TransferOrder, WeatherReading, WeatherService
from pypharm.exceptions import WeatherCommunicationError


@pytest.fixture
def location():
    return Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818)


def make_order(employee_id="EMP-101"):
    order = TransferOrder("ORD-TEST", "WH-CENTRAL", "STORE-TLV", 1)
    if employee_id is not None:
        order.assign_employee(employee_id)
    return order


@pytest.mark.parametrize("temperature,expected_events", [(30, 0), (31, 1)])
def test_observers_are_notified_only_for_danger(location, temperature, expected_events):
    observer = Mock()
    service = WeatherService(
        client=Mock(get_weather=Mock(return_value=WeatherReading(temperature))),
        observers=[observer],
    )

    result = service.check_and_classify_for_order(location, make_order())

    assert result["risk_level"] == ("DANGER" if temperature == 31 else "NORMAL")
    assert observer.update.call_count == expected_events
    if expected_events:
        event = observer.update.call_args.args[0]
        assert event.risk_level == "DANGER"
        assert event.order_id == "ORD-TEST"
        assert event.temperature == 31


def test_integrity_observer_alerts_for_missing_employee(location):
    service = WeatherService(
        client=Mock(get_weather=Mock(return_value=WeatherReading(temperature_2m=31)))
    )

    service.check_and_classify_for_order(
        location, make_order("EMP-999"), employees_catalog={}
    )

    assert any("EMP-999" in alert for alert in service.integrity_observer.alerts)


def test_weather_failure_does_not_notify_observers(location):
    observer = Mock()
    service = WeatherService(
        client=Mock(get_weather=Mock(side_effect=WeatherCommunicationError("offline"))),
        observers=[observer],
    )

    result = service.check_and_classify_for_order(location, make_order())

    assert result["risk_level"] == "UNKNOWN"
    assert observer.update.call_count == 0
