import gpiod
import time
import spidev
from adafruit_pn532.spi import PN532_SPI

class SPIWrapper:
    """
    A compatibility layer to wrap spidev.SpiDev and provide methods
    required by Adafruit PN532 library (e.g., try_lock, unlock, write_readinto).
    """
    def __init__(self, bus, device, max_speed_hz=500000):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = max_speed_hz
        self.locked = False

    def try_lock(self):
        """Fake a try_lock method for compatibility."""
        if not self.locked:
            self.locked = True
            return True
        return False

    def unlock(self):
        """Fake an unlock method for compatibility."""
        self.locked = False

    def write(self, buf):
        """Write data to SPI."""
        self.spi.xfer2(buf)

    def readinto(self, buf):
        """Read data from SPI."""
        read_data = self.spi.readbytes(len(buf))
        for i in range(len(buf)):
            buf[i] = read_data[i]

    def write_readinto(self, write_buf, read_buf):
        """
        Perform a full-duplex SPI transaction.
        :param write_buf: Data to write to the SPI bus.
        :param read_buf: Buffer to store data read from the SPI bus.
        """
        read_data = self.spi.xfer2(write_buf)
        for i in range(len(read_buf)):
            read_buf[i] = read_data[i]

    def configure(self, **kwargs):
        """Dummy method for compatibility."""
        pass



class PN532NFC:
    def __init__(self, spi_bus=0, spi_device=0, debug=False):
        """
        Initialize PN532 NFC module using SPI with a compatibility wrapper.
        :param spi_bus: SPI bus number (default: 0)
        :param spi_device: SPI device number (default: 0)
        :param debug: Enable debug mode
        """
        self.debug = debug

        # Debug: Starting Initialization
        if self.debug:
            print(f"[DEBUG] Initializing PN532 with SPI bus: {spi_bus}, SPI device: {spi_device}")

        # Initialize SPI bus using the compatibility wrapper
        try:
            self.spi = SPIWrapper(spi_bus, spi_device)
            if self.debug:
                print("[DEBUG] SPI wrapper initialized successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to initialize SPI wrapper: {e}")
            return

        # Initialize PN532 using the SPI wrapper
        try:
            self.pn532 = PN532_SPI(self.spi, None)
            self.pn532.SAM_configuration()
            if self.debug:
                print("[DEBUG] PN532 initialized successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to initialize PN532: {e}")

    def read_nfc(self, timeout=1.0):
        """
        Read an NFC tag.
        :param timeout: Timeout in seconds
        :return: UID of the NFC tag, or None if no tag is detected
        """
        if self.debug:
            print("[DEBUG] Attempting to read NFC tag...")
        if not hasattr(self, "pn532"):
            print("[ERROR] PN532 is not initialized. Cannot read NFC tag.")
            return None

        try:
            uid = self.pn532.read_passive_target(timeout=timeout)
            if uid:
                uid_str = ''.join([f'{i:02X}' for i in uid])
                if self.debug:
                    print(f"[DEBUG] NFC tag detected with UID: {uid_str}")
                return uid_str
            else:
                if self.debug:
                    print("[DEBUG] No NFC tag detected within timeout.")
                return None
        except Exception as e:
            print(f"[ERROR] NFC read error: {e}")
            return None


# Main entry point
def main():
    print("[INFO] Starting PN532 NFC Test...")
    nfc = PN532NFC(spi_bus=0, spi_device=0, debug=True)

    while True:
        print("[INFO] Waiting for an NFC tag...")
        uid = nfc.read_nfc(timeout=2.0)
        if uid:
            print(f"[SUCCESS] NFC Tag UID: {uid}")
        else:
            print("[INFO] No tag detected. Retrying...")
        time.sleep(1)


if __name__ == "__main__":
    main()
