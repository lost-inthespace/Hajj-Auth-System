#!/usr/bin/env python3
import time
import logging
import base64
from hardware.nfc_pn532 import PN532NFC
from utils.encryption_manager import EncryptionKeyManager
from utils.logger_module import SystemLogger


def setup_logging():
    """Configure detailed logging for debugging"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('nfc_debug')


def read_all_blocks(nfc, uid, num_blocks=64):
    """Try to read all blocks from the card"""
    blocks_data = {}
    for block in range(num_blocks):
        try:
            if nfc.pn532.mifare_classic_authenticate_block(
                    uid, block, 0x60, b"\xFF\xFF\xFF\xFF\xFF\xFF"):
                data = nfc.pn532.mifare_classic_read_block(block)
                if data:
                    blocks_data[block] = {
                        'hex': bytes(data).hex(),
                        'base64': base64.b64encode(bytes(data)).decode('utf-8'),
                        'ascii': ''.join(chr(x) if 32 <= x <= 126 else '.' for x in data)
                    }
        except Exception as e:
            print(f"Error reading block {block}: {str(e)}")
    return blocks_data


def main():
    logger = setup_logging()
    print("Initializing NFC reader...")

    try:
        # Initialize components
        nfc = PN532NFC(spi_bus=0, spi_device=0, debug=True)
        encryption_mgr = EncryptionKeyManager()
        system_logger = SystemLogger()

        print("\nNFC Reader Debug Tool")
        print("====================")
        print("1. Press Ctrl+C to exit")
        print("2. Place a card on the reader")
        print("3. The tool will attempt to read all accessible blocks\n")

        while True:
            try:
                print("\nWaiting for card...")
                uid = nfc.wait_for_card(timeout=0.5)

                if uid:
                    print(f"\nCard detected!")
                    print(f"UID: {[hex(i) for i in uid]}")

                    # Try standard read first
                    print("\nAttempting standard read (block 4)...")
                    data = nfc.read_nfc(timeout=0.1)
                    if data:
                        print(f"Standard read result (base64): {data}")
                        try:
                            # Try to decrypt if possible
                            decrypted = encryption_mgr.decrypt_data(data)
                            print(f"Decrypted: {decrypted}")
                        except Exception as e:
                            print(f"Decryption failed: {e}")

                    # Try reading all blocks
                    print("\nAttempting to read all accessible blocks...")
                    blocks = read_all_blocks(nfc, uid)

                    print("\nBlock contents:")
                    print("==============")
                    for block_num, data in blocks.items():
                        print(f"\nBlock {block_num}:")
                        print(f"  HEX: {data['hex']}")
                        print(f"  B64: {data['base64']}")
                        print(f"  ASCII: {data['ascii']}")

                    # Wait before checking for next card
                    time.sleep(1)

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
                time.sleep(0.5)

    except Exception as e:
        print(f"Initialization error: {str(e)}")
    finally:
        print("Debug session ended")


if __name__ == "__main__":
    main()