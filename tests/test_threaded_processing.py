"""Tests for the shipment approval queue shared by several manager threads."""

import pytest

from pypharm import (
    ApprovalQueue,
    Employee,
    Location,
    TransferOrder,
    WeatherService,
    queue_orders_for_approval,
    run_approvers,
)
from pypharm.api_client import MockWeatherClient

# Approval rules defined by the team: NORMAL - warehouse or logistics manager,
# DANGER - logistics manager only, UNKNOWN (weather check failed) - nobody.
NORMAL_ROLES = ["WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"]
DANGER_ROLES = ["LOGISTICS_MANAGER"]
UNKNOWN_ROLES = []

APPROVED = ApprovalQueue.APPROVED
ALREADY_HANDLED = ApprovalQueue.ALREADY_HANDLED
NOT_AUTHORIZED = ApprovalQueue.NOT_AUTHORIZED


def make_order(order_id, to_location_id="STORE-TLV"):
    return TransferOrder(order_id, "WH-CENTRAL", to_location_id, priority=1)


@pytest.fixture
def aya():
    return Employee("EMP-101", "Aya", "LOGISTICS_MANAGER")


@pytest.fixture
def noa():
    return Employee("EMP-105", "noa", "WAREHOUSE_MANAGER")


def test_order_already_waiting_cannot_be_submitted_again():
    order = make_order("ORD-001")
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES)

    with pytest.raises(ValueError, match="ORD-001 is already waiting"):
        queue.submit(order, "NORMAL", NORMAL_ROLES)
    assert len(queue) == 1


@pytest.mark.parametrize("manager_name,risk_level,roles,expected", [
    ("noa", "NORMAL", NORMAL_ROLES, APPROVED),
    ("aya", "NORMAL", NORMAL_ROLES, APPROVED),
    ("aya", "DANGER", DANGER_ROLES, APPROVED),
    ("noa", "DANGER", DANGER_ROLES, NOT_AUTHORIZED),
    ("aya", "UNKNOWN", UNKNOWN_ROLES, NOT_AUTHORIZED),
])
def test_manager_may_approve_only_her_risk_levels(request, manager_name, risk_level, roles, expected):
    manager = request.getfixturevalue(manager_name)
    order = make_order("ORD-001")
    queue = ApprovalQueue()
    queue.submit(order, risk_level, roles)

    assert queue.try_approve("ORD-001", manager) == expected

    if expected == APPROVED:
        assert order.status == "IN_TRANSIT"
        assert len(queue) == 0
    else:
        assert order.status == "PENDING"
        assert len(queue) == 1


def test_inactive_logistics_manager_is_refused():
    retired = Employee("EMP-200", "Dana", "LOGISTICS_MANAGER", is_active=False)
    order = make_order("ORD-001")
    queue = ApprovalQueue()
    queue.submit(order, "DANGER", DANGER_ROLES)

    assert queue.try_approve("ORD-001", retired) == NOT_AUTHORIZED
    assert order.status == "PENDING"


def test_second_approval_of_the_same_order_is_refused(aya, noa):
    order = make_order("ORD-001")
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES)

    assert queue.try_approve("ORD-001", noa) == APPROVED
    assert queue.try_approve("ORD-001", aya) == ALREADY_HANDLED

    assert queue.approval_log == [("ORD-001", "noa", "NORMAL")]
    assert order.handled_by_employee_id == "EMP-105"


def test_many_managers_racing_for_one_order_approve_it_once():
    order = make_order("ORD-777")
    queue = ApprovalQueue()
    queue.submit(order, "DANGER", DANGER_ROLES)
    managers = [Employee(f"EMP-{i}", f"manager-{i}", "LOGISTICS_MANAGER") for i in range(10)]

    run_approvers(queue, managers, review_time=0.001)

    assert queue.approved_count == 1
    assert queue.refusals == {ALREADY_HANDLED: 9, NOT_AUTHORIZED: 0}
    assert order.status == "IN_TRANSIT"


def test_two_managers_on_mixed_risk_orders(aya, noa):
    normal = [make_order(f"ORD-N{i}") for i in range(4)]
    danger = [make_order(f"ORD-D{i}") for i in range(2)]
    unknown = make_order("ORD-U0")
    queue = ApprovalQueue()
    for order in normal:
        queue.submit(order, "NORMAL", NORMAL_ROLES)
    for order in danger:
        queue.submit(order, "DANGER", DANGER_ROLES)
    queue.submit(unknown, "UNKNOWN", UNKNOWN_ROLES)

    run_approvers(queue, [aya, noa], review_time=0.001)

    # 7 orders x 2 managers = 14 attempts, 6 of them approve.
    assert queue.approved_count == 6
    assert sum(queue.refusals.values()) == 8
    assert all(order.status == "IN_TRANSIT" for order in normal + danger)
    assert unknown.status == "PENDING"
    assert queue.pending_ids() == ["ORD-U0"]
    assert all(name == "Aya" for _, name, risk in queue.approval_log if risk == "DANGER")


def test_many_managers_on_many_orders():
    orders = [make_order(f"ORD-{i:03d}") for i in range(200)]
    queue = ApprovalQueue()
    for order in orders:
        queue.submit(order, "NORMAL", NORMAL_ROLES)
    managers = [
        Employee(f"EMP-{i}", f"manager-{i}", "WAREHOUSE_MANAGER" if i % 2 else "LOGISTICS_MANAGER")
        for i in range(8)
    ]

    run_approvers(queue, managers)

    assert queue.approved_count == 200
    assert queue.refusals[ALREADY_HANDLED] == 200 * 7
    assert all(order.status == "IN_TRANSIT" for order in orders)


def test_weather_at_destination_decides_who_may_approve(aya, noa):
    haifa = Location("STORE-HAIFA", "Grand Canyon Branch", "STORE", "Haifa", 32.8193, 34.9927)
    tlv = Location("STORE-TLV", "Dizengoff", "STORE", "Tel Aviv", 32.0853, 34.7818)
    heat_wave = MockWeatherClient({(32.8193, 34.9927): 35.0})  # Haifa DANGER, Tel Aviv stays 24.0
    service = WeatherService(client=heat_wave, observers=[])
    to_haifa, to_tlv = make_order("ORD-1", "STORE-HAIFA"), make_order("ORD-2", "STORE-TLV")
    queue = ApprovalQueue()

    queue_orders_for_approval(queue, [to_haifa, to_tlv], {"STORE-HAIFA": haifa, "STORE-TLV": tlv}, service)

    assert queue.try_approve("ORD-1", noa) == NOT_AUTHORIZED
    assert queue.try_approve("ORD-2", noa) == APPROVED
    assert queue.try_approve("ORD-1", aya) == APPROVED
    assert queue.approval_log == [("ORD-2", "noa", "NORMAL"), ("ORD-1", "Aya", "DANGER")]


def test_order_with_unknown_destination_is_rejected():
    order = make_order("ORD-9", "STORE-EILAT")

    with pytest.raises(ValueError, match="unknown destination 'STORE-EILAT'"):
        queue_orders_for_approval(ApprovalQueue(), [order], {}, WeatherService(client=MockWeatherClient()))
