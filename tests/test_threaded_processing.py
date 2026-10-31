"""Tests for the shipment approval queue shared by several manager threads."""

import threading
from unittest.mock import Mock

import pytest

from pypharm import (
    ApprovalQueue,
    Employee,
    Location,
    OrderActionAuthorizer,
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


class SlowAuthorizer(OrderActionAuthorizer):
    """Pauses in the middle of approving one chosen order until the test releases it."""

    def __init__(self, slow_order_id):
        super().__init__()
        self.slow_order_id = slow_order_id
        self.inside = threading.Event()
        self.release = threading.Event()

    def authorize_and_update_status(self, order, employee, new_status):
        if order.order_id == self.slow_order_id:
            self.inside.set()
            assert self.release.wait(timeout=5)
        super().authorize_and_update_status(order, employee, new_status)


@pytest.fixture
def two_orders_mid_approval(aya):
    """ORD-A is in the middle of being approved by Aya (its lock is held)."""
    authorizer = SlowAuthorizer("ORD-A")
    queue = ApprovalQueue(authorizer)
    queue.submit(make_order("ORD-A"), "NORMAL", NORMAL_ROLES)
    queue.submit(make_order("ORD-B"), "NORMAL", NORMAL_ROLES)
    aya_thread = threading.Thread(target=queue.try_approve, args=("ORD-A", aya))
    aya_thread.start()
    assert authorizer.inside.wait(timeout=5)
    yield queue, authorizer
    authorizer.release.set()
    aya_thread.join()


def test_different_order_is_approved_without_waiting(two_orders_mid_approval, noa):
    queue, authorizer = two_orders_mid_approval
    results = []
    noa_thread = threading.Thread(target=lambda: results.append(queue.try_approve("ORD-B", noa)))

    noa_thread.start()
    noa_thread.join(timeout=1)

    assert not noa_thread.is_alive()  # finished while Aya is still in the middle of ORD-A
    assert results == [APPROVED]


def test_same_order_waits_and_is_then_refused(two_orders_mid_approval, noa):
    queue, authorizer = two_orders_mid_approval
    results = []
    noa_thread = threading.Thread(target=lambda: results.append(queue.try_approve("ORD-A", noa)))

    noa_thread.start()
    noa_thread.join(timeout=0.2)
    assert noa_thread.is_alive()  # waiting for ORD-A's lock

    authorizer.release.set()
    noa_thread.join(timeout=5)
    assert results == [ALREADY_HANDLED]
    assert queue.approval_log == [("ORD-A", "Aya", "NORMAL")]


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


def test_unknown_order_is_rechecked_in_the_same_queue(aya, noa):
    order = make_order("ORD-1", "STORE-HAIFA")
    queue = ApprovalQueue()
    queue.submit(order, "UNKNOWN", UNKNOWN_ROLES)
    assert queue.try_approve("ORD-1", aya) == NOT_AUTHORIZED  # no weather check yet

    # The weather service is back: the same order gets its real risk
    queue.submit(order, "DANGER", DANGER_ROLES)

    assert queue.risk_by_order() == {"ORD-1": "DANGER"}
    assert len(queue) == 1  # still one order, not two
    assert queue.try_approve("ORD-1", noa) == NOT_AUTHORIZED
    assert queue.try_approve("ORD-1", aya) == APPROVED
    assert order.status == "IN_TRANSIT"


def test_order_with_a_known_risk_is_not_rechecked():
    order = make_order("ORD-1")
    queue = ApprovalQueue()
    queue.submit(order, "DANGER", DANGER_ROLES)

    with pytest.raises(ValueError, match="ORD-1 is already waiting"):
        queue.submit(order, "NORMAL", NORMAL_ROLES)
    assert queue.risk_by_order() == {"ORD-1": "DANGER"}


def test_recheck_through_the_weather_service_updates_the_risk(aya):
    haifa = Location("STORE-HAIFA", "Grand Canyon Branch", "STORE", "Haifa", 32.8193, 34.9927)
    order = make_order("ORD-1", "STORE-HAIFA")
    queue = ApprovalQueue()
    queue.submit(order, "UNKNOWN", UNKNOWN_ROLES)
    heat_wave = WeatherService(client=MockWeatherClient({(32.8193, 34.9927): 35.0}), observers=[])

    queue_orders_for_approval(queue, [order], {"STORE-HAIFA": haifa}, heat_wave)

    assert queue.risk_by_order() == {"ORD-1": "DANGER"}
    assert queue.try_approve("ORD-1", aya) == APPROVED


@pytest.mark.parametrize("replacement_destination", ["STORE-HAIFA", "STORE-TLV"])
def test_recheck_rejects_another_order_object_before_requesting_weather(replacement_destination):
    original = make_order("ORD-1", "STORE-HAIFA")
    replacement = make_order("ORD-1", replacement_destination)
    fresh = make_order("ORD-2", "STORE-TLV")
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)
    queue.submit(original, "UNKNOWN", UNKNOWN_ROLES)
    client = Mock(wraps=MockWeatherClient())
    service = WeatherService(client=client, observers=[])
    locations = {
        "STORE-HAIFA": Location("STORE-HAIFA", "Haifa", "STORE", "Haifa", 32.8193, 34.9927),
        "STORE-TLV": Location("STORE-TLV", "Tel Aviv", "STORE", "Tel Aviv", 32.0853, 34.7818),
    }

    with pytest.raises(ValueError, match="same object"):
        queue_orders_for_approval(queue, [fresh, replacement], locations, service)

    client.get_weather.assert_not_called()
    assert queue.risk_by_order() == {"ORD-1": "UNKNOWN"}
    assert all(order.status == "PENDING" for order in [original, replacement, fresh])
    assert queue.approved_count == 0
    assert queue.approval_records == {}
    assert authorizer.action_history == []


def test_recheck_rejects_a_changed_destination_before_requesting_weather():
    order = make_order("ORD-1", "STORE-TLV")
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)
    queue.submit(order, "UNKNOWN", UNKNOWN_ROLES)
    order.to_location_id = "STORE-HAIFA"
    haifa = Location("STORE-HAIFA", "Haifa", "STORE", "Haifa", 32.8193, 34.9927)
    client = Mock(wraps=MockWeatherClient())
    service = WeatherService(client=client, observers=[])

    with pytest.raises(ValueError, match="destination changed"):
        queue_orders_for_approval(queue, [order], {"STORE-HAIFA": haifa}, service)

    client.get_weather.assert_not_called()
    assert queue.risk_by_order() == {"ORD-1": "UNKNOWN"}
    assert order.status == "PENDING"
    assert queue.approved_count == 0
    assert queue.approval_records == {}
    assert authorizer.action_history == []


def test_approval_rejects_a_changed_destination_instead_of_using_old_weather(noa):
    order = make_order("ORD-1", "STORE-TLV")
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)
    queue.submit(order, "NORMAL", NORMAL_ROLES)
    order.to_location_id = "STORE-HAIFA"

    with pytest.raises(ValueError, match="destination changed"):
        queue.try_approve("ORD-1", noa)

    assert queue.risk_by_order() == {"ORD-1": "NORMAL"}
    assert order.status == "PENDING"
    assert order.handled_by_employee_id is None
    assert queue.approved_count == 0
    assert queue.refusals == {ALREADY_HANDLED: 0, NOT_AUTHORIZED: 0}
    assert queue.approval_records == {}
    assert authorizer.action_history == []


def test_approval_records_the_repaired_assignment_and_retains_catalog_on_recheck(aya, noa):
    order = make_order("ORD-1")
    order.assign_employee("EMP-MISSING")
    queue = ApprovalQueue()
    queue.submit(order, "UNKNOWN", UNKNOWN_ROLES, {noa.employee_id: noa})
    order.assign_employee(noa.employee_id)
    queue.submit(order, "DANGER", DANGER_ROLES)

    assert queue.try_approve("ORD-1", aya) == APPROVED

    assert order.handled_by_employee_id == aya.employee_id
    assert queue.approval_records == {
        "ORD-1": {"assigned_employee_id": noa.employee_id, "integrity_issue": False}
    }


def test_recheck_can_supply_a_catalog_for_the_approval_snapshot(aya, noa):
    order = make_order("ORD-1")
    order.assign_employee(noa.employee_id)
    queue = ApprovalQueue()
    queue.submit(order, "UNKNOWN", UNKNOWN_ROLES)
    queue.submit(order, "DANGER", DANGER_ROLES, {noa.employee_id: noa})

    assert queue.try_approve("ORD-1", aya) == APPROVED
    assert queue.approval_records["ORD-1"]["integrity_issue"] is False


def test_approval_records_are_historical_and_cannot_be_mutated_through_a_copy(aya, noa):
    order = make_order("ORD-1")
    order.assign_employee(noa.employee_id)
    noa.deactivate()
    queue = ApprovalQueue()
    queue.submit(order, "DANGER", DANGER_ROLES, {noa.employee_id: noa})
    assert queue.try_approve("ORD-1", aya) == APPROVED

    records = queue.approval_records
    records["ORD-1"]["integrity_issue"] = False
    records.clear()
    noa.activate()
    order.assign_employee("EMP-OTHER")

    assert queue.approval_records == {
        "ORD-1": {"assigned_employee_id": noa.employee_id, "integrity_issue": True}
    }


@pytest.mark.parametrize("assigned_employee_id,expected_issue", [(None, False), ("EMP-MISSING", None)])
def test_approval_snapshot_marks_an_unchecked_assignment_explicitly(aya, assigned_employee_id, expected_issue):
    order = make_order("ORD-1")
    if assigned_employee_id is not None:
        order.assign_employee(assigned_employee_id)
    queue = ApprovalQueue()
    queue.submit(order, "DANGER", DANGER_ROLES)

    assert queue.try_approve("ORD-1", aya) == APPROVED
    assert queue.approval_records == {
        "ORD-1": {"assigned_employee_id": assigned_employee_id, "integrity_issue": expected_issue}
    }
