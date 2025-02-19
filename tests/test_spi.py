import board
import busio

# Initialize SPI
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

if spi.try_lock():
    print("SPI bus is working!")
    spi.unlock()
else:
    print("Failed to access SPI bus.")
