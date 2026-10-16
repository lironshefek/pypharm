"""
services.py - Weather classification and approval logic.
Business logic for determining required approval based on weather conditions.
"""

import logging

from .api_client import get_weather_with_retry
from .config import WeatherConfig
from .weather import WeatherReading

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Classify weather conditions and determine required approval roles.
    """

    # Temperature thresholds
    MIN_NORMAL_TEMP = 0  # Celsius
    MAX_NORMAL_TEMP = 30  # Celsius

    def __init__(self, config: WeatherConfig = None):
        self.config = config or WeatherConfig()

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
        """
        if risk_level == "NORMAL":
            return ["WAREHOUSE_MANAGER", "LOGISTICS_MANAGER"]
        # DANGER
        return ["LOGISTICS_MANAGER"]

    def check_and_classify_for_order(self, location) -> dict:
        """
        Check weather at destination and determine required approval.

        Args:
            location: Location object with latitude, longitude

        Returns:
            Dictionary with:
                - temperature: Current temperature
                - risk_level: "NORMAL" or "DANGER"
                - required_roles: List of roles that can approve
                - weather_reading: WeatherReading object

        Raises:
            WeatherCommunicationError: On network issues (after retries)
            WeatherHTTPError: On HTTP errors
            WeatherJSONError: On JSON errors
            WeatherDataError: On data validation errors
        """
        logger.info(f"Checking weather for {location.city}")

        # Get weather data from API (with retry for transient failures only)
        weather_reading = get_weather_with_retry(
            location.latitude,
            location.longitude,
            self.config
        )

        # Classify risk
        risk_level = self.classify_risk(weather_reading.temperature_2m)
        logger.info(f"Weather risk: {risk_level}")

        # Get required roles
        required_roles = self.get_required_roles(risk_level)
        logger.info(f"Approval roles: {', '.join(required_roles)}")

        return {
            "temperature": weather_reading.temperature_2m,
            "risk_level": risk_level,
            "required_roles": required_roles,
            "weather_reading": weather_reading,
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
