"""
services.py - Weather classification and approval logic.
Business logic for determining required approval based on weather conditions.
"""

import logging

from .api_client import MockWeatherClient, WeatherAPIClient, get_weather_with_retry
from .config import WeatherConfig
from .exceptions import WeatherAPIException
from .observers import (
    ApprovalEventPublisher,
    ApprovalRequiredEvent,
    AuditLogObserver,
    IntegrityAlertObserver,
)
from .weather import WeatherReading

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Classify weather conditions and determine required approval roles.
    """

    # Temperature thresholds
    MIN_NORMAL_TEMP = 0  # Celsius
    MAX_NORMAL_TEMP = 30  # Celsius

    # Risk level used when the weather could not be checked
    UNKNOWN_RISK = "UNKNOWN"

    def __init__(self, config: WeatherConfig = None, client=None, observers=None):
        """
        Args:
            config: WeatherConfig instance
            client: Object with get_weather(lat, lon). If not given, chosen by
                    WEATHER_MODE: WeatherAPIClient in live mode, MockWeatherClient otherwise.
        """
        self.config = config or WeatherConfig()
        if client is None:
            client = WeatherAPIClient(self.config) if self.config.is_live_mode() else MockWeatherClient()
        self.client = client
        self.source = "live" if isinstance(client, WeatherAPIClient) else "mock"
        default_observers = [AuditLogObserver(), IntegrityAlertObserver()]
        self.approval_events = ApprovalEventPublisher(
            default_observers if observers is None else observers
        )

    def classify_risk(self, temperature: float) -> str:
        """
        Classify weather risk based on temperature.

        Args:
            temperature: Current temperature in Celsius

        Returns:
            "NORMAL" if 0-30°C (inclusive)
            "DANGER" if <0°C or >30°C
        """
        if self.MIN_NORMAL_TEMP <= temperature <= self.MAX_NORMAL_TEMP:
            return "NORMAL"
        return "DANGER"

    def get_required_roles(self, risk_level: str) -> list:
        """
        Get the required employee roles to approve shipment.

        Args:
            risk_level: "NORMAL" or "DANGER"

        Returns:
            List of roles that can approve:
            - NORMAL: ["WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"] (both can approve)
            - DANGER: ["LOGISTICS_MANAGER"] (only senior manager)
            - anything else (e.g. UNKNOWN after an API failure): [] (nobody)
        """
        if risk_level == "NORMAL":
            return ["WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"]
        if risk_level == "DANGER":
            return ["LOGISTICS_MANAGER"]
        return []

    def check_and_classify_for_order(self, location, order=None, employees_catalog=None) -> dict:
        """
        Check weather at destination and determine required approval.

        Args:
            location: Location object with latitude, longitude

        Returns:
            Dictionary with:
                - temperature: Current temperature
                - risk_level: "NORMAL" or "DANGER"
                - required_roles: List of roles that can approve
                - weather_reading: WeatherReading object (None on failure)
                - source: "live" or "mock"
                - error: None, or the failure description

        On any weather failure the order must not move forward: the result has
        risk_level UNKNOWN and no approval roles, so the order stays PENDING.
        """
        logger.info(f"Checking weather for {location.city}")

        # Get weather data (with retry for transient failures only)
        try:
            weather_reading = get_weather_with_retry(
                location.latitude,
                location.longitude,
                self.config,
                self.client,
            )
        except WeatherAPIException as e:
            logger.error(
                f"Weather check failed for {location.city} ({type(e).__name__}); "
                f"shipment cannot be approved, order stays PENDING"
            )
            return {
                "temperature": None,
                "risk_level": self.UNKNOWN_RISK,
                "required_roles": [],
                "weather_reading": None,
                "source": self.source,
                "error": f"{type(e).__name__}: {e}",
            }

        # Classify risk
        risk_level = self.classify_risk(weather_reading.temperature_2m)
        logger.info(f"Weather risk: {risk_level}")

        # Only dangerous weather raises an approval event and notifies observers.
        if risk_level == "DANGER":
            self.approval_events.publish(
                ApprovalRequiredEvent(
                    order_id=getattr(order, "order_id", None),
                    temperature=weather_reading.temperature_2m,
                    risk_level=risk_level,
                    employee_id=getattr(order, "handled_by_employee_id", None),
                    order=order,
                    employees_catalog=employees_catalog,
                )
            )

        # Get required roles
        required_roles = self.get_required_roles(risk_level)
        logger.info(f"Approval roles: {', '.join(required_roles)}")

        return {
            "temperature": weather_reading.temperature_2m,
            "risk_level": risk_level,
            "required_roles": required_roles,
            "weather_reading": weather_reading,
            "source": self.source,
            "error": None,
        }

    def can_approve(self, employee_role: str, risk_level: str) -> bool:
        """
        Check if employee with given role can approve shipment at risk level.

        Args:
            employee_role: Employee's role (e.g., "WAREHOUSE_MANAGER")
            risk_level: Weather risk level ("NORMAL" or "DANGER")

        Returns:
            True if employee can approve, False otherwise
        """
        required_roles = self.get_required_roles(risk_level)
        result = employee_role in required_roles
        logger.debug(f"Can {employee_role} approve {risk_level}? {result}")
        return result
