"""
Physical push-button trigger interface.

Gracefully disables itself on platforms without GPIO support.
"""

import logging

from src.config import BUTTON_PIN

logger = logging.getLogger(__name__)


class ButtonTrigger:
    """Detects rising-edge presses on a physical push button via GPIO."""

    def __init__(self, pin: int = BUTTON_PIN):
        self.button = None
        self._prev = False
        try:
            from gpiozero import Button

            self.button = Button(pin, pull_up=True, bounce_time=0.05)
            logger.info("Hardware button initialized on pin %d.", pin)
        except Exception as e:
            logger.warning("Hardware button unavailable: %s", e)

    def rising_edge(self) -> bool:
        """Return True once per button press (on the rising edge)."""
        if self.button is None:
            return False
        cur = self.button.is_pressed
        edge = cur and not self._prev
        self._prev = cur
        return edge

    @property
    def is_available(self) -> bool:
        """Check if the button hardware is connected and functional."""
        return self.button is not None
