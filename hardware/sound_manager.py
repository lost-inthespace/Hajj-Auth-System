# sound_manager.py

import gpiod
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SoundManager:
    # Configuration
    PWM_GPIO_OFFSET = 12
    SUCCESS_HIGH_FREQ = 1800
    SUCCESS_LOW_FREQ = 1400
    FAIL_HIGH_FREQ = 800
    FAIL_LOW_FREQ = 600

    def __init__(self):
        """Initialize GPIO for sound output."""
        self.chip: Optional[gpiod.Chip] = None
        self.line: Optional[gpiod.Line] = None
        try:
            self.chip = gpiod.Chip("gpiochip0")
            self.line = self.chip.get_line(self.PWM_GPIO_OFFSET)
            self.line.request(consumer="software_pwm", type=gpiod.LINE_REQ_DIR_OUT)
            logger.info("Sound manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize sound manager: {e}")
            self.cleanup()

    def _play_tone(self, frequency: int, duration: float, duty_cycle: float = 0.5) -> None:
        """Generate a tone using PWM."""
        if not self.line:
            logger.warning("Cannot play tone: GPIO line not initialized")
            return

        try:
            period = 1.0 / frequency
            high_time = period * duty_cycle
            low_time = period * (1 - duty_cycle)
            end_time = time.time() + duration

            while time.time() < end_time:
                self.line.set_value(1)
                time.sleep(high_time)
                self.line.set_value(0)
                time.sleep(low_time)
        except Exception as e:
            logger.error(f"Error playing tone: {e}")

    def play_success(self) -> None:
        """Play success sound pattern."""
        try:
            logger.debug("Playing success sound")
            # First tone (lower frequency, shorter duration)
            self._play_tone(frequency=self.SUCCESS_LOW_FREQ, duration=0.06)
            time.sleep(0.02)
            # Second tone (higher frequency, slightly longer)
            self._play_tone(frequency=self.SUCCESS_HIGH_FREQ, duration=0.08)
        except Exception as e:
            logger.error(f"Error playing success sound: {e}")

    def play_fail(self) -> None:
        """Play failure sound pattern."""
        try:
            logger.debug("Playing failure sound")
            # First tone (higher frequency)
            self._play_tone(frequency=self.FAIL_HIGH_FREQ, duration=0.1)
            time.sleep(0.02)
            # Second tone (lower frequency, longer duration)
            self._play_tone(frequency=self.FAIL_LOW_FREQ, duration=0.15)
        except Exception as e:
            logger.error(f"Error playing failure sound: {e}")

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        try:
            if self.line:
                self.line.set_value(0)
            logger.info("Sound manager cleaned up")
        except Exception as e:
            logger.error(f"Error during sound manager cleanup: {e}")