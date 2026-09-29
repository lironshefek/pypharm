"""
context_managers.py - Part D: Custom Context Manager.
LocationMaintenance for safe temporary location locking during inventory operations.
"""


class LocationMaintenance:
    """
    Context manager: temporarily locks a location during maintenance/inventory operations.
    Ensures the location is unlocked even if an exception occurs.

    Usage:
        with LocationMaintenance("W1"):
            # Location W1 is locked during this block
            perform_inventory_count()
        # Location W1 is unlocked automatically
    """

    def __init__(self, location_id: str):
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError(f"location_id must be a non-empty string, got: {location_id!r}")
        self.location_id = location_id.strip()
        self._is_locked = False

    def __enter__(self):
        """Lock the location when entering the with block."""
        self._is_locked = True
        print(f"🔒 Location '{self.location_id}' locked for maintenance")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Unlock the location when exiting the with block (even on exception)."""
        self._is_locked = False
        if exc_type:
            print(f"⚠️  Location '{self.location_id}' unlocked (exception occurred: {exc_type.__name__})")
        else:
            print(f"🔓 Location '{self.location_id}' unlocked after maintenance")
        return False  # Don't suppress exceptions

    def is_locked(self) -> bool:
        """Check if location is currently locked."""
        return self._is_locked

    def __str__(self) -> str:
        status = "LOCKED" if self._is_locked else "UNLOCKED"
        return f"LocationMaintenance(location_id={self.location_id!r}, status={status})"

    def __repr__(self) -> str:
        return f"LocationMaintenance(location_id={self.location_id!r}, is_locked={self._is_locked})"
