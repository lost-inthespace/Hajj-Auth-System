# main.py

import time
from nfc_manager import PN532NFC

def main():
    print("[INFO] Starting PN532 NFC Test...")

    # Create an instance of PN532NFC
    #   - spi_bus=0, spi_device=0 typically map to /dev/spidev0.0 on Raspberry Pi
    #   - debug=True prints debug messages
    nfc = PN532NFC(spi_bus=0, spi_device=0, debug=True)

    while True:
        print("[INFO] Waiting for an NFC tag...")
        uid = nfc.read_nfc(timeout=2.0)
        if uid:
            print(f"[SUCCESS] NFC Tag UID: {uid}")
        else:
            print("[INFO] No tag detected. Retrying...")

        # Sleep 1 second before checking again
        time.sleep(1)

if __name__ == "__main__":
    main()
