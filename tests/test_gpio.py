import board
import digitalio

# Test GPIO pin (e.g., GPIO5)
cs = digitalio.DigitalInOut(board.D5)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True
print("GPIO test passed!")

