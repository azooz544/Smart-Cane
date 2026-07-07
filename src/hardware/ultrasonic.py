"""
Ultrasonic distance sensor interface (HC-SR04).

Gracefully disables itself on platforms without GPIO support
(e.g., Windows/macOS development machines).
"""

import logging

from src.config import (
    ULTRASONIC_TRIGGER_PIN,
    ULTRASONIC_ECHO_PIN,
    ULTRASONIC_MAX_DISTANCE_M,
)

logger = logging.getLogger(__name__)


class UltrasonicSensor:
    """Reads distance from an HC-SR04 ultrasonic sensor via GPIO."""

    def __init__(
        self,
        trigger_pin: int = ULTRASONIC_TRIGGER_PIN,
        echo_pin: int = ULTRASONIC_ECHO_PIN,
        max_distance: float = ULTRASONIC_MAX_DISTANCE_M,
    ):
        self.sensor = None
        try:
            from gpiozero import DistanceSensor

            self.sensor = DistanceSensor(
                echo=echo_pin,
                trigger=trigger_pin,
                max_distance=max_distance,
            )
            logger.info("Ultrasonic sensor initialized (trigger=%d, echo=%d).", trigger_pin, echo_pin)
        except Exception as e:
            logger.warning("Ultrasonic sensor unavailable: %s", e)

    def read_cm(self) -> float | None:
        """Return distance in centimeters, or None if sensor is unavailable."""
        if self.sensor is None:
            return None
        try:
            return round(self.sensor.distance * 100.0, 1)
        except Exception:
            return None

    @property
    def is_available(self) -> bool:
        """Check if the sensor hardware is connected and functional."""
        return self.sensor is not None
