"""
business_report.py - Module for generating executive and operational reports.
"""

def generate_business_report(batch) -> dict:
    """
    Calculates operational and business metrics from the OrderBatch.
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

    return {
        "total_orders": total_orders,
        "completion_rate": round(completion_rate, 2),
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "top_source": (top_source, source_counts.get(top_source, 0)),
        "top_destination": (top_destination, destination_counts.get(top_destination, 0)),
        "critical_pending_count": critical_pending_count
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

    print("------------------------------------------------------------\n")