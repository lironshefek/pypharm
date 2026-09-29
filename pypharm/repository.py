"""
repository.py - Part D: Read and validate transfer orders from JSONL file.
"""

import json
from .models import TransferOrder


def load_transfer_orders_from_jsonl(filepath: str) -> list[TransferOrder]:
    """
    Read transfer orders from inventory_data.jsonl file.

    - Reads line by line (lazy evaluation)
    - Converts JSON to TransferOrder objects
    - Checks for errors (missing fields, invalid values, duplicates)
    - Returns list of valid orders
    """
    orders = []
    seen_order_ids = set()

    # Open file and read line by line
    with open(filepath, encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            # Parse JSON from line
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"Line {line_number}: Invalid JSON format")
                continue

            # Skip if not a transfer_order
            if record.get("entity_type") != "transfer_order":
                continue

            # Get the fields we need
            order_id = record.get("order_id")
            from_loc = record.get("from_location_id")
            to_loc = record.get("to_location_id")
            status = record.get("status")
            priority = record.get("priority")

            # Check for missing fields
            if not order_id or not from_loc or not to_loc or not status or priority is None:
                print(f"Line {line_number}: Missing required fields")
                continue

            # Check for duplicate order_id
            if order_id in seen_order_ids:
                print(f"Line {line_number}: Duplicate order_id '{order_id}'")
                continue
            seen_order_ids.add(order_id)

            # Check if status is valid
            valid_statuses = ["PENDING", "IN_TRANSIT", "DELIVERED", "CANCELLED"]
            if status not in valid_statuses:
                print(f"Line {line_number}: Invalid status '{status}'")
                continue

            # Check if priority is valid
            if not isinstance(priority, int) or priority < 1 or priority > 5:
                print(f"Line {line_number}: Invalid priority '{priority}'")
                continue

            # Create TransferOrder object
            try:
                order = TransferOrder(
                    order_id=order_id,
                    from_location_id=from_loc,
                    to_location_id=to_loc,
                    status=status,
                    priority=priority
                )
                orders.append(order)
            except Exception as e:
                print(f"Line {line_number}: Could not create order - {e}")
                continue

    print(f"✓ Loaded {len(orders)} transfer orders")
    return orders
