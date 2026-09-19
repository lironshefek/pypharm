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