"""
repository.py - Part D: Read and validate transfer orders from JSONL file.
"""

import json
from .models import Employee, Location, PerishableProduct, StandardProduct, TransferOrder


SAMPLE_ENTITY_TYPES = {
    "perishable_product": PerishableProduct,
    "standard_product": StandardProduct,
    "location": Location,
    "employee": Employee,
}


def load_sample_data_from_jsonl(filepath: str) -> list:
    objects = []
    identifiers = set()
    identifier_fields = {
        "perishable_product": "sku",
        "standard_product": "sku",
        "location": "location_id",
        "employee": "employee_id",
    }

    with open(filepath, encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record must be a JSON object")
                entity_type = record.get("entity_type")
                model = SAMPLE_ENTITY_TYPES.get(entity_type)
                if model is None:
                    raise ValueError(f"unknown entity_type {entity_type!r}")
                obj = model.from_dict(record)
                identifier = getattr(obj, identifier_fields[entity_type])
                product_types = ("perishable_product", "standard_product")
                identifier_group = "product" if entity_type in product_types else entity_type
                key = (identifier_group, identifier)
                if key in identifiers:
                    raise ValueError(f"duplicate {entity_type} identifier {identifier!r}")
                identifiers.add(key)
                objects.append(obj)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{filepath}:{line_number}: invalid record: {exc}") from exc

    return objects


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

            if not isinstance(record, dict):
                print(f"Line {line_number}: Expected a JSON object")
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
                order = TransferOrder.from_dict(record)
                orders.append(order)
            except (KeyError, TypeError, ValueError) as e:
                print(f"Line {line_number}: Could not create order - {e}")
                continue

    print(f"Loaded {len(orders)} transfer orders")
    return orders
