"""Tests for the shipment approval queue shared by several approver threads."""

import pytest

from pypharm import ApprovalQueue, TransferOrder, run_approvers


def make_orders(count, status="PENDING"):
    return [
        TransferOrder(f"ORD-{i:03d}", "WH-CENTRAL", "STORE-TLV", priority=1, status=status)
        for i in range(1, count + 1)
    ]


@pytest.fixture
def orders():
    return make_orders(6)


def test_approve_next_on_empty_queue_returns_none():
    queue = ApprovalQueue()

    assert queue.approve_next("Aya") is None
    assert queue.approved_count == 0


def test_approve_next_follows_arrival_order(orders):
    queue = ApprovalQueue(orders[:2])

    first = queue.approve_next("Aya")

    assert first.order_id == "ORD-001"
    assert first.status == "IN_TRANSIT"
    assert orders[1].status == "PENDING"
    assert len(queue) == 1


@pytest.mark.parametrize("approvers", [["Aya"], ["Aya", "Noa"], ["Aya", "Noa", "Ruth", "Liron"]])
def test_every_order_is_approved_exactly_once(orders, approvers):
    queue = run_approvers(ApprovalQueue(orders), approvers)

    assert queue.approved_count == 6
    assert sorted(order_id for order_id, _ in queue.approval_log) == [o.order_id for o in orders]
    assert all(order.status == "IN_TRANSIT" for order in orders)
    assert len(queue) == 0


def test_order_queued_twice_is_approved_once(orders):
    # Two branch managers requested the same shipments: every order appears twice.
    queue = ApprovalQueue(orders + orders)

    run_approvers(queue, ["Aya", "Noa", "Ruth"])

    assert queue.approved_count == 6
    approved_ids = [order_id for order_id, _ in queue.approval_log]
    assert len(approved_ids) == len(set(approved_ids))
    assert len(queue) == 0


def test_cancelled_order_is_not_approved():
    pending = make_orders(2)
    cancelled = TransferOrder("ORD-900", "WH-CENTRAL", "STORE-HAIFA", priority=2, status="CANCELLED")
    queue = ApprovalQueue([pending[0], cancelled, pending[1]])

    run_approvers(queue, ["Aya", "Noa"])

    assert queue.approved_count == 2
    assert cancelled.status == "CANCELLED"
    assert "ORD-900" not in [order_id for order_id, _ in queue.approval_log]


def test_many_approvers_on_many_duplicated_orders():
    orders = make_orders(200)
    queue = ApprovalQueue(orders * 3)

    run_approvers(queue, [f"approver-{i}" for i in range(8)], handling_time=0.0001)

    assert queue.approved_count == 200
    assert all(order.status == "IN_TRANSIT" for order in orders)
    assert len(queue) == 0
