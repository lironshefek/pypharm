"""
tests/test_integration.py - Combined process across both systems (section 6.4).

Each test runs the whole chain: orders + locations -> WeatherService (external
data, replaced by a fake client) -> ApprovalQueue -> managers (employees
subsystem) -> OrderActionAuthorizer -> business report. Every test checks the
result and the state of the components, not only that nothing crashed.
"""

from unittest import mock

import pytest

from pypharm import (
    ApprovalQueue,
    Employee,
    Location,
    OrderActionAuthorizer,
    OrderBatch,
    TransferOrder,
    WeatherService,
    queue_orders_for_approval,
    run_approvers,
)
from pypharm.api_client import MockWeatherClient
from pypharm.exceptions import WeatherCommunicationError
from pypharm.reports import generate_business_report

HAIFA = Location("STORE-HAIFA", "Grand Canyon Branch", "STORE", "Haifa", 32.8193, 34.9927)
TLV = Location("STORE-TLV", "Dizengoff Beauty Boutique", "STORE", "Tel Aviv", 32.0853, 34.7818)
LOCATIONS = {"STORE-HAIFA": HAIFA, "STORE-TLV": TLV}


@pytest.fixture
def aya():
    return Employee("EMP-101", "Aya", "LOGISTICS_MANAGER")


@pytest.fixture
def noa():
    return Employee("EMP-105", "noa", "WAREHOUSE_MANAGER")


@pytest.fixture
def employees(aya, noa):
    return {aya.employee_id: aya, noa.employee_id: noa}


def make_order(order_id, to_location_id):
    return TransferOrder(order_id, "WH-CENTRAL", to_location_id, 1, handled_by_employee_id="EMP-101")


def test_combined_process_succeeds_and_hot_order_is_approved_by_logistics_only(aya, noa, employees):
    # Heat wave in Haifa (35C > 30C -> DANGER); Tel Aviv stays at the normal 24C
    service = WeatherService(client=MockWeatherClient({(HAIFA.latitude, HAIFA.longitude): 35.0}), observers=[])
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)
    to_haifa, to_tlv = make_order("ORD-1", "STORE-HAIFA"), make_order("ORD-2", "STORE-TLV")

    queue_orders_for_approval(queue, [to_haifa, to_tlv], LOCATIONS, service, employees)
    run_approvers(queue, [noa, aya])

    # Result: both shipped; the DANGER order only by the logistics manager
    assert queue.approved_count == 2
    assert ("ORD-1", "Aya", "DANGER") in queue.approval_log
    # State: order status, handler and audit log changed together
    assert to_haifa.status == "IN_TRANSIT" and to_tlv.status == "IN_TRANSIT"
    assert to_haifa.handled_by_employee_id == "EMP-101"
    assert len(authorizer.action_history) == 2
    assert len(queue) == 0
    # Report: nothing left waiting for senior approval
    weather = generate_business_report(OrderBatch([to_haifa, to_tlv]), queue, employees)["weather_approval"]
    assert weather["risk_counts"] == {"NORMAL": 1, "DANGER": 1, "UNKNOWN": 0}
    assert weather["senior_approval_backlog"] == 0


def test_weather_service_failure_blocks_approval_and_changes_nothing(aya, noa, employees):
    failing_client = mock.Mock(source="live", get_weather=mock.Mock(side_effect=WeatherCommunicationError("timeout")))
    observer = mock.Mock()
    service = WeatherService(client=failing_client, observers=[observer])
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)
    order = make_order("ORD-1", "STORE-TLV")

    with mock.patch("pypharm.api_client.time.sleep"):
        queue_orders_for_approval(queue, [order], LOCATIONS, service, employees)
    run_approvers(queue, [noa, aya])

    # Business response: risk UNKNOWN -> nobody may approve, not even the logistics manager
    assert failing_client.get_weather.call_count == 3  # retried, then gave up
    assert queue.risk_by_order() == {"ORD-1": "UNKNOWN"}
    assert queue.approved_count == 0
    assert queue.refusals == {"ALREADY_HANDLED": 0, "NOT_AUTHORIZED": 2}
    # State: the order did not move and nothing was recorded or announced
    assert order.status == "PENDING"
    assert order.handled_by_employee_id == "EMP-101"
    assert authorizer.action_history == []
    assert observer.update.call_count == 0
    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]
    assert weather["blocked_by_weather_failure"] == 1


def test_order_to_unknown_destination_rejects_the_whole_batch(employees):
    client = mock.Mock(wraps=MockWeatherClient())
    service = WeatherService(client=client, observers=[])
    queue = ApprovalQueue()
    valid = make_order("ORD-1", "STORE-TLV")
    broken = make_order("ORD-2", "STORE-EILAT")  # no such location in the catalog

    with pytest.raises(ValueError, match="STORE-EILAT"):
        queue_orders_for_approval(queue, [valid, broken], LOCATIONS, service, employees)

    # All or nothing: the valid order was not queued either, and no weather was requested
    assert queue.risk_by_order() == {}
    assert len(queue) == 0
    assert client.get_weather.call_count == 0
    assert valid.status == "PENDING" and broken.status == "PENDING"
