import board
import busio
from digitalio import DigitalInOut
from adafruit_pn532.spi import PN532_SPI

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs = DigitalInOut(board.D8)  # Replace with your CS pin

try:
    pn532 = PN532_SPI(spi, cs, debug=True)
    pn532.SAM_configuration()  # Configure the PN532
    print("PN532 initialized successfully.")
except Exception as e:
    print(f"Failed to initialize PN532: {e}")
