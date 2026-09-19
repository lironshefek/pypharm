from abc import ABC, abstractmethod


class Product(ABC):
    def __init__(self, sku, name, brand, price):
        if not isinstance(sku, str) or not sku.strip():
            raise ValueError(f"SKU must be a non-empty string, got: {sku!r}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Name must be a non-empty string, got: {name!r}")
        if not isinstance(brand, str) or not brand.strip():
            raise ValueError(f"Brand must be a non-empty string, got: {brand!r}")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"Price must be a positive number, got: {price}")

        self.sku = sku.strip()
        self.name = name.strip()
        self.brand = brand.strip()
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
        if not isinstance(expiry_date, str) or not expiry_date.strip():
            raise ValueError(f"Expiry date must be a non-empty string, got: {expiry_date!r}")
        if not isinstance(requires_refrigeration, bool):
            raise ValueError(f"Requires refrigeration must be a boolean, got: {requires_refrigeration!r}")

        self.expiry_date = expiry_date.strip()
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
            return "Refrigerated: 2-8°C, keep away from direct sunlight"
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
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError(f"Location ID must be a non-empty string, got: {location_id!r}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Name must be a non-empty string, got: {name!r}")
        if not isinstance(city, str) or not city.strip():
            raise ValueError(f"City must be a non-empty string, got: {city!r}")
        if not isinstance(location_type, str) or location_type.strip().upper() not in self.VALID_LOCATIONS:
                    raise ValueError(f"Location type must be one of {self.VALID_LOCATIONS}, got: {location_type!r}")

        self.location_id = location_id.strip()
        self.name = name.strip()
        self.city = city.strip()
        self.location_type = location_type

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
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError(f"Location ID must be a non-empty string, got: {location_id!r}")
        if not isinstance(min_threshold, int) or min_threshold < 0:
            raise ValueError(f"Minimum threshold must be a non-negative integer, got: {min_threshold}")

        self.product = product
        self.location_id = location_id.strip()
        self.min_threshold = min_threshold
        self.quantity = quantity

    @property
    def quantity(self) -> int:
        return self._quantity

    @quantity.setter
    def quantity(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"Quantity must be a non-negative integer, got: {value}")
        self._quantity = value

    @property
    def is_low_stock(self) -> bool:
        return self._quantity <= self.min_threshold

    def adjust_quantity(self, amount):
        if not isinstance(amount, int):
            raise ValueError(f"Adjustment amount must be an integer, got: {amount}")
        new_qty = self._quantity + amount
        if new_qty < 0:
            raise ValueError(f"Cannot reduce stock below zero. Current: {self._quantity}, attempted change: {amount}")
        self._quantity = new_qty

    def __repr__(self) -> str:
        return (
            f"InventoryItem(product={self.product.sku!r}, location_id={self.location_id!r}, "
            f"quantity={self._quantity!r}, min_threshold={self.min_threshold!r})"
        )  
      
class TransferOrderItem:
    def __init__(self, sku, quantity):
        if not isinstance(sku, str) or not sku.strip():
            raise ValueError(f"SKU must be a non-empty string, got: {sku!r}")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError(f"Quantity must be a positive integer, got: {quantity!r}")

        self.sku = sku.strip()
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

    def __init__(self, order_id, from_location_id, to_location_id, priority, status="PENDING"):
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError(f"Order ID must be a non-empty string, got: {order_id!r}")
        if not isinstance(from_location_id, str) or not from_location_id.strip():
            raise ValueError(f"From location ID must be a non-empty string, got: {from_location_id!r}")
        if not isinstance(to_location_id, str) or not to_location_id.strip():
            raise ValueError(f"To location ID must be a non-empty string, got: {to_location_id!r}")
        if from_location_id.strip() == to_location_id.strip():
            raise ValueError(f"Source and destination locations cannot be identical: {from_location_id!r}")
        if not isinstance(priority, int) or priority < 1:
            raise ValueError(f"Priority must be a positive integer (lower number = higher urgency), got: {priority}")
        if not isinstance(status, str) or status.strip().upper() not in self.VALID_STATUSES:
            raise ValueError(f"Status must be one of {self.VALID_STATUSES}, got: {status!r}")

        self.order_id = order_id.strip()
        self.from_location_id = from_location_id.strip()
        self.to_location_id = to_location_id.strip()
        self.priority = priority
        self._status = status.strip().upper()
        self._items = []

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if not isinstance(value, str) or value.strip().upper() not in self.VALID_STATUSES:
            raise ValueError(f"Status must be one of {self.VALID_STATUSES}, got: {value!r}")
        self._status = value.strip().upper()

    @property
    def items(self):
        return list(self._items)

    def add_item(self, sku, quantity):
        if not isinstance(sku, str) or not sku.strip():
            raise ValueError(f"SKU must be a non-empty string, got: {sku!r}")
        clean_sku = sku.strip()
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
        return self.priority < other.priority

    @classmethod
    def from_dict(cls, data):
        order = cls(
            order_id=data["order_id"],
            from_location_id=data["from_location_id"],
            to_location_id=data["to_location_id"],
            priority=data.get("priority", 3),
            status=data.get("status", "PENDING"),
        )
        for item_data in data.get("items", []):
            order.add_item(item_data["sku"], item_data["quantity"])
        return order

    def __str__(self):
        return (
            f"Order {self.order_id}: {self.from_location_id} -> {self.to_location_id} "
            f"| Priority: {self.priority} | Status: {self.status} | Types: {len(self._items)}"
        )

    def __repr__(self):
        return (
            f"TransferOrder(order_id={self.order_id!r}, from_location_id={self.from_location_id!r}, "
            f"to_location_id={self.to_location_id!r}, priority={self.priority!r}, status={self._status!r})"
        )

class Employee:
    VALID_ROLES = {"WAREHOUSE_WORKER", "LOGISTICS_MANAGER", "PHARMACIST", "CASHIER"}

    def __init__(self, employee_id, name, role, is_active=True):
        if not isinstance(employee_id, str) or not employee_id.strip():
            raise ValueError(f"Employee ID must be a non-empty string, got: {employee_id!r}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Name must be a non-empty string, got: {name!r}")
        if not isinstance(is_active, bool):
            raise ValueError(f"is_active must be a boolean, got: {is_active!r}")

        self.employee_id = employee_id.strip()
        self.name = name.strip()
        self.is_active = is_active
        self._role = role

    @property
    def role(self) -> str:
        return self._role

    @role.setter
    def role(self, value):
        if not isinstance(value, str) or value.strip().upper() not in self.VALID_ROLES:
            raise ValueError(
                f"Invalid role: {value!r}. Must be one of {self.VALID_ROLES}"
            )
        self._role = value.strip().upper()

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
    DEFAULT_PERMISSIONS = {
        "UPDATE_STATUS": {"WAREHOUSE_WORKER", "LOGISTICS_MANAGER"},
        "CANCEL_ORDER": {"LOGISTICS_MANAGER"},
    }

    def __init__(self, permissions_map=None):
        if permissions_map is None:
            self._permissions = {
                action: set(roles) for action, roles in self.DEFAULT_PERMISSIONS.items()
            }
        else:
            if not isinstance(permissions_map, dict):
                raise ValueError("Permissions map must be a dictionary")
            self._permissions = {
                action: set(roles) for action, roles in permissions_map.items()
            }

    @property
    def permissions(self):
        return {action: set(roles) for action, roles in self._permissions.items()}

    def is_authorized(self, employee, action_name) -> bool:
        if not isinstance(employee, Employee):
            raise ValueError(f"Must provide a valid Employee instance, got: {type(employee).__name__}")
        if not employee.is_active:
            return False

        allowed_roles = self._permissions.get(action_name, set())
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
        return True

    def validate_employees_integrity(self, orders, employees_catalog) -> tuple:
        errors = []
        for order in orders:
            emp_id = getattr(order, "handled_by_employee_id", None)
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
        return f"OrderActionAuthorizer(actions={list(self._permissions.keys())!r})"