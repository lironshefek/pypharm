"""
tests/test_reports.py - Combined business report (Stage 1 orders + Stage 2 weather approvals).

New metric: the senior-approval backlog - DANGER orders still waiting for a
logistics manager - and how many such orders fall on each active logistics
manager. It joins the weather risk (external service), the order status
(core system) and the employees catalog (subsystem).
"""

import pytest

from pypharm import Employee, OrderActionAuthorizer, OrderBatch, TransferOrder
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
    assert weather["available_logistics_managers"] == 1
    assert weather["backlog_per_logistics_manager"] == 2.0


def test_backlog_with_no_active_logistics_manager_is_flagged(approval_day, noa):
    orders, queue = approval_day

    weather = generate_business_report(OrderBatch(orders), queue, {"EMP-105": noa})["weather_approval"]

    assert weather["available_logistics_managers"] == 0
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
        queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    queue.submit(orders[3], "DANGER", DANGER_ROLES, employees)
    for order in orders:
        queue.try_approve(order.order_id, noa)

    weather = generate_business_report(OrderBatch(orders), queue, employees)["weather_approval"]

    # ORD-1 (unknown) and ORD-2 (inactive) were shipped; ORD-4 is still waiting, so not counted
    assert weather["approved_with_integrity_issue"] == 2
    assert weather["integrity_issue_orders"] == ["ORD-1", "ORD-2"]
    # Approval replaced the handler, so its previous assignment is recorded at approval time
    assert orders[0].handled_by_employee_id == "EMP-105"


@pytest.mark.parametrize("approve_first", [False, True])
def test_cancelled_order_is_not_reported_as_shipped_with_an_integrity_issue(noa, employees, approve_first):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-999")
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    if approve_first:
        assert queue.try_approve(order.order_id, noa) == ApprovalQueue.APPROVED
    OrderActionAuthorizer().authorize_and_update_status(order, employees["EMP-101"], "CANCELLED")

    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert order.status == "CANCELLED"
    assert queue.approved_count == int(approve_first)
    assert weather["approved_with_integrity_issue"] == 0
    assert weather["integrity_issue_orders"] == []


def test_deactivating_a_valid_handler_later_does_not_create_a_past_integrity_issue(noa, employees):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-101")
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    queue.try_approve(order.order_id, noa)

    employees["EMP-101"].deactivate()
    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert weather["approved_with_integrity_issue"] == 0
    assert weather["integrity_issue_orders"] == []


def test_activating_an_inactive_handler_later_preserves_the_past_integrity_issue(noa, employees):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-102")
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    queue.try_approve(order.order_id, noa)

    employees["EMP-102"].activate()
    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert weather["approved_with_integrity_issue"] == 1
    assert weather["integrity_issue_orders"] == ["ORD-1"]


def test_creating_a_missing_handler_later_preserves_the_past_integrity_issue(noa, employees):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-999")
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    queue.try_approve(order.order_id, noa)

    employees["EMP-999"] = Employee("EMP-999", "New employee", "WAREHOUSE_WORKER")
    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert weather["approved_with_integrity_issue"] == 1
    assert weather["integrity_issue_orders"] == ["ORD-1"]


@pytest.mark.parametrize(
    "initial_employee_id, employee_id_at_approval, expected_issues",
    [("EMP-999", "EMP-101", 0), ("EMP-101", "EMP-999", 1)],
)
def test_report_uses_the_assignment_at_approval_not_queue_entry(
    noa, employees, initial_employee_id, employee_id_at_approval, expected_issues
):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id=initial_employee_id)
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)

    order.assign_employee(employee_id_at_approval)
    queue.try_approve(order.order_id, noa)
    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert order.handled_by_employee_id == noa.employee_id
    assert weather["approved_with_integrity_issue"] == expected_issues
    assert weather["integrity_issue_orders"] == (["ORD-1"] if expected_issues else [])
    assert queue.approval_records["ORD-1"]["assigned_employee_id"] == employee_id_at_approval


@pytest.mark.parametrize("active_at_approval, expected_issues", [(True, 0), (False, 1)])
def test_report_uses_employee_activity_at_approval_not_queue_entry(noa, employees, active_at_approval, expected_issues):
    employee = employees["EMP-102"]
    employee.is_active = not active_at_approval
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id=employee.employee_id)
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)

    employee.is_active = active_at_approval
    queue.try_approve(order.order_id, noa)
    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert weather["approved_with_integrity_issue"] == expected_issues


@pytest.mark.parametrize("employee_id, expected_unchecked", [(None, 0), ("EMP-101", 1)])
def test_missing_approval_catalog_is_reported_as_unchecked_not_as_an_integrity_issue(
    noa, employees, employee_id, expected_unchecked
):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id=employee_id)
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES)
    queue.try_approve(order.order_id, noa)

    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert weather["approved_with_integrity_issue"] == 0
    assert weather["integrity_unchecked_count"] == expected_unchecked


def test_delivered_order_keeps_the_integrity_issue_recorded_at_approval(noa, employees):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-102")
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    queue.try_approve(order.order_id, noa)
    authorizer.authorize_and_update_status(order, noa, "DELIVERED")

    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    assert weather["approved_with_integrity_issue"] == 1
    assert weather["integrity_issue_orders"] == ["ORD-1"]


def test_generating_report_does_not_change_orders_employees_or_approval_history(noa, employees):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-102")
    authorizer = OrderActionAuthorizer()
    queue = ApprovalQueue(authorizer)
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    queue.try_approve(order.order_id, noa)
    before = (
        order.status, order.handled_by_employee_id,
        {employee_id: (employee.role, employee.is_active) for employee_id, employee in employees.items()},
        queue.approval_records, queue.approval_log, queue.refusals, authorizer.action_history,
    )

    report = generate_business_report(OrderBatch([order]), queue, employees)

    assert report["weather_approval"]["approved_with_integrity_issue"] == 1
    assert (
        order.status, order.handled_by_employee_id,
        {employee_id: (employee.role, employee.is_active) for employee_id, employee in employees.items()},
        queue.approval_records, queue.approval_log, queue.refusals, authorizer.action_history,
    ) == before


def test_logistics_manager_on_leave_cannot_clear_the_backlog(approval_day, employees):
    orders, queue = approval_day
    employees["EMP-101"].start_leave()  # Aya is the only active logistics manager

    weather = generate_business_report(OrderBatch(orders), queue, employees)["weather_approval"]

    assert weather["senior_approval_backlog"] == 2
    assert weather["available_logistics_managers"] == 0
    assert weather["backlog_per_logistics_manager"] is None


def test_order_assigned_to_an_employee_on_leave_is_not_an_integrity_issue(noa, employees):
    order = TransferOrder("ORD-1", "WH-CENTRAL", "STORE-TLV", 1, handled_by_employee_id="EMP-101")
    employees["EMP-101"].start_leave()
    queue = ApprovalQueue()
    queue.submit(order, "NORMAL", NORMAL_ROLES, employees)
    assert queue.try_approve(order.order_id, noa) == ApprovalQueue.APPROVED

    weather = generate_business_report(OrderBatch([order]), queue, employees)["weather_approval"]

    # Aya is on leave, not gone: her order is shipped by noa without an integrity issue
    assert weather["approved_with_integrity_issue"] == 0
    assert weather["integrity_issue_orders"] == []
