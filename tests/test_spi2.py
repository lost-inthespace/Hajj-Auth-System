import board
import busio
from digitalio import DigitalInOut
from adafruit_pn532.spi import PN532_SPI

# Set up SPI bus and chip select
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs = DigitalInOut(board.D8)  # Replace D8 with your CS GPIO pin (e.g., GPIO8)

try:
    pn532 = PN532_SPI(spi, cs)
    pn532.SAM_configuration()  # Initialize the PN532 module
    print("PN532 initialized successfully!")
except Exception as e:
    print(f"Error initializing PN532: {e}")
