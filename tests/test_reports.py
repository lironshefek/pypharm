"""
tests/test_reports.py - Combined business report (Stage 1 orders + Stage 2 weather approvals).

New metric: the senior-approval backlog - DANGER orders still waiting for a
logistics manager - and how many such orders fall on each active logistics
manager. It joins the weather risk (external service), the order status
(core system) and the employees catalog (subsystem).
"""

import pytest

from pypharm import Employee, OrderBatch, TransferOrder
from pypharm.reports import generate_business_report
from pypharm.threaded_processing import ApprovalQueue

NORMAL_ROLES = ["WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"]
DANGER_ROLES = ["LOGISTICS_MANAGER"]


def make_order(order_id):
    return TransferOrder(order_id, "WH-CENTRAL", "STORE-TLV", 1)


@pytest.fixture
def noa():
    return Employee("EMP-105", "noa", "WAREHOUSE_MANAGER")


@pytest.fixture
def employees(noa):
    return {
        "EMP-101": Employee("EMP-101", "Aya", "LOGISTICS_MANAGER"),
        "EMP-102": Employee("EMP-102", "Dana", "LOGISTICS_MANAGER", is_active=False),
        "EMP-105": noa,
    }


@pytest.fixture
def approval_day(noa):
    """Two hot-weather orders, one normal and one whose weather check failed."""
    orders = [make_order("ORD-1"), make_order("ORD-2"), make_order("ORD-3"), make_order("ORD-4")]
    queue = ApprovalQueue()
    queue.submit(orders[0], "DANGER", DANGER_ROLES)
    queue.submit(orders[1], "DANGER", DANGER_ROLES)
    queue.submit(orders[2], "NORMAL", NORMAL_ROLES)
    queue.submit(orders[3], "UNKNOWN", [])
    # Only the warehouse manager is at work: she may approve the normal order only
    for order in orders:
        queue.try_approve(order.order_id, noa)
    return orders, queue


def test_report_combines_weather_risk_with_order_status(approval_day, employees):
    orders, queue = approval_day

    report = generate_business_report(OrderBatch(orders), queue, employees)

    weather = report["weather_approval"]
    assert weather["risk_counts"] == {"NORMAL": 1, "DANGER": 2, "UNKNOWN": 1}
    assert weather["approved_count"] == 1
    assert weather["refusals"] == {"ALREADY_HANDLED": 0, "NOT_AUTHORIZED": 3}
    # Stage 1 KPIs still describe the same orders after the approvals
    assert report["total_orders"] == 4
    assert report["status_counts"] == {"PENDING": 3, "IN_TRANSIT": 1}


def test_senior_approval_backlog_per_active_logistics_manager(approval_day, employees):
    orders, queue = approval_day

    weather = generate_business_report(OrderBatch(orders), queue, employees)["weather_approval"]

    # ORD-1 and ORD-2 are DANGER and still PENDING -> they wait for a logistics manager
    assert weather["senior_approval_backlog"] == 2
    # ORD-4 cannot be approved by anyone until the weather check succeeds
    assert weather["blocked_by_weather_failure"] == 1
    # Dana is inactive, so only Aya can clear the backlog
    assert weather["active_logistics_managers"] == 1
    assert weather["backlog_per_logistics_manager"] == 2.0


def test_backlog_with_no_active_logistics_manager_is_flagged(approval_day, noa):
    orders, queue = approval_day

    weather = generate_business_report(OrderBatch(orders), queue, {"EMP-105": noa})["weather_approval"]

    assert weather["active_logistics_managers"] == 0
    assert weather["backlog_per_logistics_manager"] is None


def test_report_without_approval_data_keeps_stage_1_shape():
    report = generate_business_report(OrderBatch([make_order("ORD-1")]))

    assert "weather_approval" not in report
    assert report["total_orders"] == 1


def test_report_counts_orders_approved_despite_an_integrity_issue(noa, employees):
    # Assigned employees: unknown, inactive (Dana), valid (Aya), unknown again
    orders = [
        TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-999"),
        TransferOrder("ORD-2", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-102"),
        TransferOrder("ORD-3", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-101"),
        TransferOrder("ORD-4", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-999"),
    ]
    queue = ApprovalQueue()
    for order in orders[:3]:
        queue.submit(order, "NORMAL", NORMAL_ROLES)
    queue.submit(orders[3], "DANGER", DANGER_ROLES)
    for order in orders:
        queue.try_approve(order.order_id, noa)

    weather = generate_business_report(OrderBatch(orders), queue, employees)["weather_approval"]

    # ORD-1 (unknown) and ORD-2 (inactive) were shipped; ORD-4 is still waiting, so not counted
    assert weather["approved_with_integrity_issue"] == 2
    assert weather["integrity_issue_orders"] == ["ORD-1", "ORD-2"]
    # Approval replaced the handler, which is why the original assignment must be remembered
    assert orders[0].handled_by_employee_id == "EMP-105"
