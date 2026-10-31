"""Invalid numeric weather data must block approval without a retry."""

from unittest import mock

import pytest
import requests

from pypharm import (
    ApprovalQueue,
    Employee,
    Location,
    OrderActionAuthorizer,
    OrderBatch,
    TransferOrder,
    WeatherAPIClient,
    WeatherDataError,
    WeatherReading,
    WeatherService,
    get_weather_with_retry,
    queue_orders_for_approval,
    run_approvers,
)
from pypharm.reports import generate_business_report


INVALID_PAYLOADS = [
    pytest.param('{"current":{"temperature_2m":1e309}}', id="temperature"),
    pytest.param('{"current":{"temperature_2m":20,"rain":1e309}}', id="rain"),
    pytest.param('{"current":{"temperature_2m":20,"weather_code":1e309}}', id="weather_code"),
]


def make_response(payload):
    response = requests.Response()
    response.status_code = 200
    response._content = payload.encode("utf-8")
    response.headers["Content-Type"] = "application/json"
    return response


@pytest.mark.parametrize("field", ["temperature_2m", "rain", "weather_code"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "negative_inf"])
def test_weather_reading_rejects_nonfinite_fields(field, value):
    fields = {"temperature_2m": 20.0, field: value}

    with pytest.raises(ValueError, match=field):
        WeatherReading(**fields)


def test_weather_reading_rejects_a_temperature_too_large_to_convert():
    with pytest.raises(ValueError, match="temperature_2m"):
        WeatherReading(temperature_2m=10 ** 400)


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_invalid_numeric_api_data_raises_a_domain_error_without_retry(payload):
    with mock.patch("pypharm.api_client.requests.get", return_value=make_response(payload)) as get:
        with mock.patch("pypharm.api_client.time.sleep") as sleep:
            with pytest.raises(WeatherDataError):
                get_weather_with_retry(32.0853, 34.7818)

    get.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_invalid_numeric_weather_blocks_the_full_approval_flow(payload):
    location = Location("STORE-TLV", "Store", "STORE", "Tel Aviv", 32.0853, 34.7818)
    managers = [
        Employee("EMP-105", "Noa", "WAREHOUSE_MANAGER"),
        Employee("EMP-101", "Aya", "LOGISTICS_MANAGER"),
    ]
    employees = {employee.employee_id: employee for employee in managers}
    order = TransferOrder("ORD-INVALID", "WH-CENTRAL", location.location_id, 1,
                          handled_by_employee_id="EMP-101")
    observer = mock.Mock()
    service = WeatherService(client=WeatherAPIClient(), observers=[observer])
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)

    with mock.patch("pypharm.api_client.requests.get", return_value=make_response(payload)) as get:
        with mock.patch("pypharm.api_client.time.sleep") as sleep:
            queue_orders_for_approval(queue, [order], {location.location_id: location}, service, employees)
    run_approvers(queue, managers)

    get.assert_called_once()
    sleep.assert_not_called()
    observer.update.assert_not_called()
    assert queue.risk_by_order() == {"ORD-INVALID": "UNKNOWN"}
    assert order.status == "PENDING"
    assert order.handled_by_employee_id == "EMP-101"
    assert queue.approved_count == 0
    assert queue.refusals == {"ALREADY_HANDLED": 0, "NOT_AUTHORIZED": 2}
    assert authorizer.action_history == []
    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]
    assert weather["blocked_by_weather_failure"] == 1
