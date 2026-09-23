import time
from abc import ABC, abstractmethod


def _require_non_empty_str(value, field_name: str) -> str:
    """Shared validation helper: used by every constructor below instead of
    repeating the same isinstance/strip check in each class."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string, got: {value!r}")
    return value.strip()


class Product(ABC):
    def __init__(self, sku, name, brand, price):
        self.sku = _require_non_empty_str(sku, "SKU")
        self.name = _require_non_empty_str(name, "Name")
        self.brand = _require_non_empty_str(brand, "Brand")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"Price must be a positive number, got: {price}")
        self._price = float(price)

    @property
    def price(self) -> float:
        return self._price

    @price.setter
    def price(self, value):
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"Price must be a positive number, got: {value}")
        self._price = float(value)

    @abstractmethod
    def calculate_handling_cost(self, quantity: int) -> float:
        pass

    @abstractmethod
    def get_storage_requirements(self) -> str:
        pass

    def __str__(self) -> str:
        return f"{self.name} ({self.brand}) - {self._price:.2f} ILS [SKU: {self.sku}]"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(sku={self.sku!r}, name={self.name!r}, brand={self.brand!r}, price={self._price!r})"


class PerishableProduct(Product):
    def __init__(self, sku, name, brand, price, expiry_date, requires_refrigeration):
        super().__init__(sku, name, brand, price)
        self.expiry_date = _require_non_empty_str(expiry_date, "Expiry date")
        if not isinstance(requires_refrigeration, bool):
            raise ValueError(f"Requires refrigeration must be a boolean, got: {requires_refrigeration!r}")
        self.requires_refrigeration = requires_refrigeration

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            sku=data["sku"],
            name=data["name"],
            brand=data["brand"],
            price=data["price"],
            expiry_date=data["expiry_date"],
            requires_refrigeration=data["requires_refrigeration"],
        )

    def calculate_handling_cost(self, quantity: int) -> float:
        base_rate = 2.5
        refrigeration_fee = 5.0 if self.requires_refrigeration else 1.5
        return quantity * (base_rate + refrigeration_fee)

    def get_storage_requirements(self) -> str:
        if self.requires_refrigeration:
            return "Refrigerated: 2-8C, keep away from direct sunlight"
        return "Cool and dry place, check expiration date periodically"

    def __repr__(self) -> str:
        return (
            f"PerishableProduct(sku={self.sku!r}, name={self.name!r}, brand={self.brand!r}, "
            f"price={self._price!r}, expiry_date={self.expiry_date!r}, "
            f"requires_refrigeration={self.requires_refrigeration!r})"
        )


class StandardProduct(Product):
    def __init__(self, sku, name, brand, price, weight_kg):
        super().__init__(sku, name, brand, price)
        if not isinstance(weight_kg, (int, float)) or weight_kg <= 0:
            raise ValueError(f"Weight must be a positive number, got: {weight_kg}")
        self.weight_kg = float(weight_kg)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            sku=data["sku"],
            name=data["name"],
            brand=data["brand"],
            price=data["price"],
            weight_kg=data["weight_kg"],
        )

    def calculate_handling_cost(self, quantity: int) -> float:
        cost_per_kg = 3.0
        return quantity * self.weight_kg * cost_per_kg

    def get_storage_requirements(self) -> str:
        return "Standard shelf storage: Ambient room temperature"

    def __repr__(self) -> str:
        return (
            f"StandardProduct(sku={self.sku!r}, name={self.name!r}, brand={self.brand!r}, "
            f"price={self._price!r}, weight_kg={self.weight_kg!r})"
        )


class Location:
    VALID_LOCATIONS = {"STORE", "WAREHOUSE"}

    def __init__(self, location_id, name, location_type, city):
        self.location_id = _require_non_empty_str(location_id, "Location ID")
        self.name = _require_non_empty_str(name, "Name")
        self.city = _require_non_empty_str(city, "City")

        clean_type = _require_non_empty_str(location_type, "Location type").upper()
        if clean_type not in self.VALID_LOCATIONS:
            raise ValueError(f"Location type must be one of {self.VALID_LOCATIONS}, got: {location_type!r}")
        self.location_type = clean_type

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            location_id=data["location_id"],
            name=data["name"],
            location_type=data["location_type"],
            city=data["city"],
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.location_type}) - {self.city} [ID: {self.location_id}]"

    def __repr__(self) -> str:
        return (
            f"Location(location_id={self.location_id!r}, name={self.name!r}, "
            f"location_type={self.location_type!r}, city={self.city!r})"
        )


class InventoryItem:
    def __init__(self, product, location_id, quantity, min_threshold):
        if not isinstance(product, Product):
            raise ValueError(f"Product must be an instance of Product, got: {type(product).__name__}")
        self.location_id = _require_non_empty_str(location_id, "Location ID")
        if not isinstance(min_threshold, int) or min_threshold < 0:
            raise ValueError(f"Minimum threshold must be a non-negative integer, got: {min_threshold}")
        if not isinstance(quantity, int) or quantity < 0:
            raise ValueError(f"Quantity must be a non-negative integer, got: {quantity}")

        self.product = product
        self.min_threshold = min_threshold
        self._quantity = quantity
        self._reserved = 0
        self._incoming = 0

    @classmethod
    def from_dict(cls, data: dict, product: Product):
        """Alternative constructor. `product` must already be a resolved
        Product instance (looked up by SKU from a product registry),
        since InventoryItem does not own product data itself."""
        return cls(
            product=product,
            location_id=data["location_id"],
            quantity=data["quantity"],
            min_threshold=data["min_threshold"],
        )

    @property
    def quantity(self) -> int:
        return self._quantity

    @property
    def reserved(self) -> int:
        return self._reserved

    @property
    def incoming(self) -> int:
        return self._incoming

    @property
    def available_quantity(self) -> int:
        return self._quantity - self._reserved

    @property
    def is_low_stock(self) -> bool:
        return self._quantity <= self.min_threshold

    def reserve(self, amount: int):
        if amount <= 0 or amount > self.available_quantity:
            raise ValueError(f"Cannot reserve {amount}. Available: {self.available_quantity}")
        self._reserved += amount

    def release_reservation(self, amount: int):
        if amount <= 0 or amount > self._reserved:
            raise ValueError(f"Cannot release {amount}. Reserved: {self._reserved}")
        self._reserved -= amount

    def dispatch_reserved(self, amount: int):
        if amount <= 0 or amount > self._reserved:
            raise ValueError(f"Cannot dispatch {amount}. Reserved: {self._reserved}")
        self._quantity -= amount
        self._reserved -= amount

    def add_incoming(self, amount: int):
        if amount <= 0:
            raise ValueError("Incoming amount must be positive")
        self._incoming += amount

    def receive_incoming(self, amount: int):
        if amount <= 0 or amount > self._incoming:
            raise ValueError(f"Cannot receive {amount}. Incoming: {self._incoming}")
        self._incoming -= amount
        self._quantity += amount

    def reduce_incoming(self, amount: int):
        """Cancel an expected incoming shipment (e.g. when a TransferOrder
        that had added incoming stock gets cancelled before delivery).
        Kept as a public method so callers never touch `_incoming` directly."""
        if amount <= 0 or amount > self._incoming:
            raise ValueError(f"Cannot reduce incoming by {amount}. Incoming: {self._incoming}")
        self._incoming -= amount

    def adjust_quantity(self, amount):
        if not isinstance(amount, int):
            raise ValueError(f"Adjustment amount must be an integer, got: {amount}")
        new_qty = self._quantity + amount
        if new_qty < 0:
            raise ValueError(f"Cannot reduce stock below zero. Current: {self._quantity}, attempted change: {amount}")
        self._quantity = new_qty

    def __str__(self) -> str:
        flag = " [LOW STOCK]" if self.is_low_stock else ""
        return (
            f"{self.product.name} @ {self.location_id}: {self._quantity} on hand, "
            f"{self.available_quantity} available{flag}"
        )

    def __repr__(self) -> str:
        return (
            f"InventoryItem(product={self.product.sku!r}, location_id={self.location_id!r}, "
            f"quantity={self._quantity!r}, reserved={self._reserved!r}, incoming={self._incoming!r}, "
            f"min_threshold={self.min_threshold!r})"
        )


class TransferOrderItem:
    def __init__(self, sku, quantity):
        self.sku = _require_non_empty_str(sku, "SKU")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError(f"Quantity must be a positive integer, got: {quantity!r}")
        self._quantity = quantity

    @property
    def quantity(self):
        return self._quantity

    @quantity.setter
    def quantity(self, value):
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"Quantity must be a positive integer, got: {value!r}")
        self._quantity = value

    @classmethod
    def from_dict(cls, data):
        return cls(
            sku=data["sku"],
            quantity=data["quantity"],
        )

    def __str__(self):
        return f"{self.sku} x {self._quantity}"

    def __repr__(self):
        return f"TransferOrderItem(sku={self.sku!r}, quantity={self._quantity!r})"


class TransferOrder:
    VALID_STATUSES = {"PENDING", "IN_TRANSIT", "DELIVERED", "CANCELLED"}

    def __init__(self, order_id, from_location_id, to_location_id, priority, status="PENDING",
                 created_at=None, handled_by_employee_id=None):
        self.order_id = _require_non_empty_str(order_id, "Order ID")
        self.from_location_id = _require_non_empty_str(from_location_id, "From location ID")
        self.to_location_id = _require_non_empty_str(to_location_id, "To location ID")
        if self.from_location_id == self.to_location_id:
            raise ValueError(f"Source and destination locations cannot be identical: {from_location_id!r}")
        if not isinstance(priority, int) or priority < 1:
            raise ValueError(f"Priority must be a positive integer (lower number = higher urgency), got: {priority}")

        clean_status = _require_non_empty_str(status, "Status").upper()
        if clean_status not in self.VALID_STATUSES:
            raise ValueError(f"Status must be one of {self.VALID_STATUSES}, got: {status!r}")
        self._status = clean_status

        # handled_by_employee_id is optional (None until an employee is assigned),
        # so it only goes through the helper when it is actually provided.
        if handled_by_employee_id is not None:
            handled_by_employee_id = _require_non_empty_str(handled_by_employee_id, "handled_by_employee_id")
        self.handled_by_employee_id = handled_by_employee_id

        self.priority = priority
        self.created_at = created_at if created_at is not None else time.time()
        self._items = []

    def assign_employee(self, employee_id: str):
        """Attach (or reassign) the employee responsible for this order."""
        self.handled_by_employee_id = _require_non_empty_str(employee_id, "employee_id")

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        clean_status = _require_non_empty_str(value, "Status").upper()
        if clean_status not in self.VALID_STATUSES:
            raise ValueError(f"Status must be one of {self.VALID_STATUSES}, got: {value!r}")
        self._status = clean_status

    @property
    def items(self):
        return list(self._items)

    def add_item(self, sku, quantity):
        clean_sku = _require_non_empty_str(sku, "SKU")
        for item in self._items:
            if item.sku == clean_sku:
                item.quantity += quantity
                return
        self._items.append(TransferOrderItem(clean_sku, quantity))

    def remove_item(self, sku):
        clean_sku = sku.strip()
        for item in self._items:
            if item.sku == clean_sku:
                self._items.remove(item)
                break

    def get_total_units(self):
        return sum(item.quantity for item in self._items)

    def __len__(self):
        return len(self._items)

    def __lt__(self, other):
        if not isinstance(other, TransferOrder):
            return NotImplemented
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at

    @classmethod
    def from_dict(cls, data):
        order = cls(
            order_id=data["order_id"],
            from_location_id=data["from_location_id"],
            to_location_id=data["to_location_id"],
            priority=data.get("priority", 3),
            status=data.get("status", "PENDING"),
            created_at=data.get("created_at"),
            handled_by_employee_id=data.get("handled_by_employee_id"),
        )
        for item_data in data.get("items", []):
            order.add_item(item_data["sku"], item_data["quantity"])
        return order

    def __str__(self):
        handler = self.handled_by_employee_id or "unassigned"
        return (
            f"Order {self.order_id}: {self.from_location_id} -> {self.to_location_id} "
            f"| Priority: {self.priority} | Status: {self.status} | Types: {len(self._items)} "
            f"| Handled by: {handler}"
        )

    def __repr__(self):
        return (
            f"TransferOrder(order_id={self.order_id!r}, from_location_id={self.from_location_id!r}, "
            f"to_location_id={self.to_location_id!r}, priority={self.priority!r}, "
            f"status={self._status!r}, created_at={self.created_at!r}, "
            f"handled_by_employee_id={self.handled_by_employee_id!r})"
        )


class Employee:
    VALID_ROLES = {"WAREHOUSE_WORKER", "LOGISTICS_MANAGER", "PHARMACIST", "CASHIER"}

    def __init__(self, employee_id, name, role, is_active=True):
        self.employee_id = _require_non_empty_str(employee_id, "Employee ID")
        self.name = _require_non_empty_str(name, "Name")
        if not isinstance(is_active, bool):
            raise ValueError(f"is_active must be a boolean, got: {is_active!r}")
        self.is_active = is_active

        clean_role = _require_non_empty_str(role, "Role").upper()
        if clean_role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role: {role!r}. Must be one of {self.VALID_ROLES}")
        self._role = clean_role

    @property
    def role(self) -> str:
        return self._role

    @role.setter
    def role(self, value):
        clean_role = _require_non_empty_str(value, "Role").upper()
        if clean_role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role: {value!r}. Must be one of {self.VALID_ROLES}")
        self._role = clean_role

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            employee_id=data["employee_id"],
            name=data["name"],
            role=data["role"],
            is_active=data.get("is_active", True),
        )

    def __str__(self) -> str:
        status_str = "ACTIVE" if self.is_active else "INACTIVE"
        return f"{self.name} ({self._role}) [{self.employee_id}] - {status_str}"

    def __repr__(self) -> str:
        return (
            f"Employee(employee_id={self.employee_id!r}, name={self.name!r}, "
            f"role={self._role!r}, is_active={self.is_active!r})"
        )


class OrderActionAuthorizer:
    """Central place for order-related authorization rules.
    Simplified: permissions are fixed (no configurable permissions_map),
    since the assignment only requires the operations below, not
    runtime-configurable rules."""

    PERMISSIONS = {
        "UPDATE_STATUS": {"WAREHOUSE_WORKER", "LOGISTICS_MANAGER"},
        "CANCEL_ORDER": {"LOGISTICS_MANAGER"},
    }

    def is_authorized(self, employee, action_name) -> bool:
        if not isinstance(employee, Employee):
            raise ValueError(f"Must provide a valid Employee instance, got: {type(employee).__name__}")
        if not employee.is_active:
            return False

        allowed_roles = self.PERMISSIONS.get(action_name, set())
        return employee.role in allowed_roles

    def authorize_and_update_status(self, order, employee, new_status):
        if not isinstance(employee, Employee):
            raise ValueError(f"Must provide a valid Employee instance, got: {type(employee).__name__}")

        if not employee.is_active:
            raise PermissionError(
                f"Action denied: Employee {employee.employee_id!r} is inactive."
            )

        if not self.is_authorized(employee, "UPDATE_STATUS"):
            raise PermissionError(
                f"Permission denied: Employee {employee.name!r} with role {employee.role!r} "
                f"is not authorized to update order statuses."
            )

        order.status = new_status
        # Real link between the Employee subsystem and the central model:
        # updating a TransferOrder's status now records who did it.
        order.assign_employee(employee.employee_id)
        return True

    def validate_employees_integrity(self, orders, employees_catalog) -> tuple:
        errors = []
        for order in orders:
            emp_id = order.handled_by_employee_id
            if emp_id is not None:
                if emp_id not in employees_catalog:
                    errors.append(
                        f"Integrity Error: Order {order.order_id!r} references unknown employee {emp_id!r}."
                    )
                elif not employees_catalog[emp_id].is_active:
                    errors.append(
                        f"Integrity Error: Order {order.order_id!r} references inactive employee {emp_id!r}."
                    )
        return len(errors) == 0, errors

    def __repr__(self) -> str:
        return f"OrderActionAuthorizer(actions={list(self.PERMISSIONS.keys())!r})"