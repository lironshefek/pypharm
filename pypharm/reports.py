"""
business_report.py - Module for generating executive and operational reports.
"""

def generate_business_report(batch, approval_queue=None, employees_catalog=None) -> dict:
    """
    Calculates operational and business metrics from the OrderBatch.
    When an approval queue is given, adds the Stage 2 weather-approval section.
    """
    total_orders = batch.count()
    if total_orders == 0:
        return {"error": "No orders found in the batch to generate report."}

    # Dictionaries for aggregating metrics
    status_counts = {}
    priority_counts = {}
    destination_counts = {}
    source_counts = {}
    critical_pending_count = 0

    # Iterate through all orders in the batch
    for order in batch:
        # Aggregate by status
        status = order.status
        status_counts[status] = status_counts.get(status, 0) + 1

        # Aggregate by priority
        priority = order.priority
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

        # Aggregate by destination and source
        to_loc = order.to_location_id
        destination_counts[to_loc] = destination_counts.get(to_loc, 0) + 1

        from_loc = order.from_location_id
        source_counts[from_loc] = source_counts.get(from_loc, 0) + 1

        # Track critical orders that are still pending
        if priority == 1 and status == "PENDING":
            critical_pending_count += 1

    # Calculate completion rate
    delivered_count = status_counts.get("DELIVERED", 0)
    completion_rate = (delivered_count / total_orders) * 100

    # Determine top source and destination
    top_source = max(source_counts, key=source_counts.get) if source_counts else None
    top_destination = max(destination_counts, key=destination_counts.get) if destination_counts else None

    report = {
        "total_orders": total_orders,
        "completion_rate": round(completion_rate, 2),
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "top_source": (top_source, source_counts.get(top_source, 0)),
        "top_destination": (top_destination, destination_counts.get(top_destination, 0)),
        "critical_pending_count": critical_pending_count
    }

    if approval_queue is not None:
        report["weather_approval"] = _weather_approval_summary(batch, approval_queue, employees_catalog or {})

    return report


def _weather_approval_summary(batch, approval_queue, employees_catalog: dict) -> dict:
    """
    Stage 2 section: joins the weather risk (external service), the order status
    (core system) and the employees catalog (subsystem).

    New metric - senior-approval backlog: DANGER orders still PENDING can be
    approved only by a logistics manager, so the backlog per active logistics
    manager shows whether the approvals can be cleared or more staff is needed.
    """
    risk_by_order = approval_queue.risk_by_order()
    queued = [(order, risk_by_order[order.order_id]) for order in batch if order.order_id in risk_by_order]

    risk_counts = {"NORMAL": 0, "DANGER": 0, "UNKNOWN": 0}
    for _, risk in queued:
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    def pending_with(risk_level):
        return sum(1 for order, risk in queued if risk == risk_level and order.status == "PENDING")

    senior_backlog = pending_with("DANGER")
    active_logistics_managers = sum(
        1 for employee in employees_catalog.values()
        if employee.role == "LOGISTICS_MANAGER" and employee.is_active
    )

    return {
        "risk_counts": risk_counts,
        "approved_count": approval_queue.approved_count,
        "refusals": approval_queue.refusals,
        "senior_approval_backlog": senior_backlog,
        "blocked_by_weather_failure": pending_with("UNKNOWN"),
        "active_logistics_managers": active_logistics_managers,
        "backlog_per_logistics_manager": (
            senior_backlog / active_logistics_managers if active_logistics_managers else None
        ),
    }


def print_business_report(report_data: dict) -> None:
    """
    Prints the operational and business metrics in a structured format.
    """
    if "error" in report_data:
        print(report_data["error"])
        return

    total = report_data["total_orders"]

    print("\n------------------------------------------------------------")
    print("           Executive & Operational Report - PyPharm")
    print("------------------------------------------------------------")

    print("\n1. Key Performance Indicators (KPIs):")
    print(f"   - Total orders in system: {total}")
    print(f"   - Completion rate: {report_data['completion_rate']}%")

    print("\n2. Status Breakdown:")
    for status, count in report_data["status_counts"].items():
        percentage = (count / total) * 100
        print(f"   - {status}: {count} orders ({percentage:.1f}%)")

    print("\n3. Priority Breakdown:")
    for priority, count in sorted(report_data["priority_counts"].items()):
        priority_label = "Critical (1)" if priority == 1 else f"Regular ({priority})"
        print(f"   - Priority {priority_label}: {count} orders")

    print("\n4. Inventory Flow Analysis:")
    src_name, src_count = report_data["top_source"]
    dest_name, dest_count = report_data["top_destination"]
    print(f"   - Most active source location: {src_name} ({src_count} outbound shipments)")
    print(f"   - Highest demand destination: {dest_name} ({dest_count} incoming orders)")

    print("\n5. Operational Risk Alert:")
    critical_pending = report_data["critical_pending_count"]
    if critical_pending > 0:
        print(f"   [WARNING] {critical_pending} critical orders are still in PENDING status!")
        print("   Recommendation: Prioritize processing at source location immediately.")
    else:
        print("   [OK] No delays detected for critical orders.")

    weather = report_data.get("weather_approval")
    if weather is not None:
        print("\n6. Weather-Based Shipment Approval (Stage 2):")
        risks = weather["risk_counts"]
        print(f"   - Orders by destination weather: NORMAL {risks['NORMAL']}, "
              f"DANGER {risks['DANGER']}, UNKNOWN {risks['UNKNOWN']}")
        print(f"   - Approved: {weather['approved_count']} | "
              f"Refused - already approved: {weather['refusals']['ALREADY_HANDLED']}, "
              f"role not allowed: {weather['refusals']['NOT_AUTHORIZED']}")
        print(f"   - Blocked by weather-service failure (nobody may approve): "
              f"{weather['blocked_by_weather_failure']}")
        print(f"   - Senior-approval backlog (DANGER orders waiting for a logistics manager): "
              f"{weather['senior_approval_backlog']}")
        per_manager = weather["backlog_per_logistics_manager"]
        if weather["senior_approval_backlog"] == 0:
            print("   [OK] No hot/cold-weather orders are waiting for senior approval.")
        elif per_manager is None:
            print("   [WARNING] No active logistics manager - these orders cannot be shipped.")
            print("   Recommendation: assign or activate a logistics manager.")
        else:
            print(f"   - Backlog per active logistics manager: {per_manager:.1f} "
                  f"({weather['active_logistics_managers']} active)")

    print("------------------------------------------------------------\n")