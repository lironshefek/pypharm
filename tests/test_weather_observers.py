from unittest.mock import Mock, patch

import pytest

from pypharm import Employee, Location, TransferOrder, WeatherReading, WeatherService
from pypharm.observers import AuditLogObserver, IntegrityAlertObserver
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
    integrity = IntegrityAlertObserver()
    service = WeatherService(
        client=Mock(get_weather=Mock(return_value=WeatherReading(temperature_2m=31))),
        observers=[integrity],
    )

    service.check_and_classify_for_order(
        location, make_order("EMP-999"), employees_catalog={}
    )

    assert any("EMP-999" in alert for alert in integrity.alerts)


def test_weather_failure_does_not_notify_observers(location):
    observer = Mock()
    service = WeatherService(
        client=Mock(get_weather=Mock(side_effect=WeatherCommunicationError("offline"))),
        observers=[observer],
    )

    with patch("pypharm.api_client.time.sleep"):
        result = service.check_and_classify_for_order(location, make_order())

    assert result["risk_level"] == "UNKNOWN"
    assert observer.update.call_count == 0


def test_one_danger_event_reaches_both_observers(location, caplog):
    # The same two reactors the service uses by default, passed in from outside
    integrity = IntegrityAlertObserver()
    service = WeatherService(
        client=Mock(get_weather=Mock(return_value=WeatherReading(temperature_2m=35))),
        observers=[AuditLogObserver(), integrity],
    )

    with caplog.at_level("WARNING", logger="pypharm.observers"):
        service.check_and_classify_for_order(
            location, make_order("EMP-999"), employees_catalog={}
        )

    # Reactor 1: the audit log recorded the approval request
    audit_records = [r for r in caplog.records if "Approval required" in r.getMessage()]
    assert len(audit_records) == 1
    assert "order=ORD-TEST" in audit_records[0].getMessage()
    assert "risk=DANGER" in audit_records[0].getMessage()

    # Reactor 2: the integrity check flagged the unknown employee
    assert len(integrity.alerts) == 1
    assert "EMP-999" in integrity.alerts[0]


def test_integrity_check_uses_the_catalog_sent_with_the_event(location):
    # The observer starts with no catalog; the service passes the real one in the event
    integrity = IntegrityAlertObserver()
    service = WeatherService(
        client=Mock(get_weather=Mock(return_value=WeatherReading(temperature_2m=35))),
        observers=[integrity],
    )
    catalog = {"EMP-101": Employee("EMP-101", "Aya", "LOGISTICS_MANAGER")}

    service.check_and_classify_for_order(location, make_order("EMP-101"), employees_catalog=catalog)

    assert integrity.alerts == []
