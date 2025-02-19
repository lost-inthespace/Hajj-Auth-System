"""
nfc_pn532.py

Module for interacting with the PN532 NFC reader via SPI.
"""

import time
import json
import os
import spidev
import base64
import logging
from typing import Optional, List, Any, Union, Dict
from adafruit_pn532.spi import PN532_SPI

logger = logging.getLogger(__name__)

MIFARE_CMD_AUTH_KEYA = 0x60
DEFAULT_KEY = b"\xFF\xFF\xFF\xFF\xFF\xFF"


class SPIWrapper:
    """
    A simple wrapper for the spidev SPI interface.
    """
    def __init__(self, bus: int, device: int, max_speed_hz: int = 500000, spi_mode: int = 0) -> None:
        """
        Initialize the SPI interface.

        :param bus: SPI bus number.
        :param device: SPI device number.
        :param max_speed_hz: Maximum speed for SPI communication.
        :param spi_mode: SPI mode.
        """
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = max_speed_hz
        self.spi.mode = spi_mode
        self.locked = False

    def try_lock(self) -> bool:
        """
        Attempt to acquire the SPI lock.

        :return: True if the lock was acquired, False otherwise.
        """
        if not self.locked:
            self.locked = True
            return True
        return False

    def unlock(self) -> None:
        """
        Release the SPI lock.
        """
        self.locked = False

    def write(self, buf: List[int]) -> None:
        """
        Write data to the SPI bus.

        :param buf: List of integers representing the data to write.
        """
        self.spi.xfer2(buf)

    def readinto(self, buf: bytearray) -> None:
        """
        Read bytes from the SPI bus into a provided buffer.

        :param buf: A bytearray to hold the read bytes.
        """
        read_data = self.spi.readbytes(len(buf))
        for i in range(len(buf)):
            buf[i] = read_data[i]

    def write_readinto(self, write_buf: List[int], read_buf: bytearray) -> None:
        """
        Write data and simultaneously read data from the SPI bus.

        :param write_buf: List of integers to write.
        :param read_buf: Bytearray to hold the data read.
        """
        read_data = self.spi.xfer2(write_buf)
        for i in range(len(read_buf)):
            read_buf[i] = read_data[i]

    def configure(self, **kwargs) -> None:
        """
        Placeholder for SPI configuration.

        Accepts keyword arguments for any future configuration needs.
        """
        pass


class PN532NFC:
    """
    Class to interface with the PN532 NFC reader via SPI.

    The initialization remains unchanged.
    """
    def __init__(self, spi_bus: int = 0, spi_device: int = 0, debug: bool = False) -> None:
        """
        Initialize the NFC reader and SPI interface.

        :param spi_bus: SPI bus number.
        :param spi_device: SPI device number.
        :param debug: Enable debugging mode if True.
        """
        self.debug = debug
        self.storage_path = "nfc_data"
        os.makedirs(self.storage_path, exist_ok=True)
        try:
            self.spi = SPIWrapper(spi_bus, spi_device)
            # The PN532_SPI initialization is kept unchanged.
            self.pn532 = PN532_SPI(self.spi, None)
            self.pn532.SAM_configuration()
            ic_version = self.pn532.firmware_version
            logger.info(f"Found PN532 with firmware version: {[hex(i) for i in ic_version]}")
        except Exception as e:
            logger.exception("Initialization Error in PN532NFC")
            raise

    def wait_for_card(self, timeout: float) -> Optional[List[int]]:
        """
        Wait for an NFC card to be detected.

        :param timeout: Maximum time in seconds to wait for a card.
        :return: UID of the detected card as a list of integers or None if timeout is reached.
        """
        logger.debug("Waiting for card...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            uid = self.pn532.read_passive_target(timeout=0.5)
            if uid:
                logger.info(f"Card detected! UID: {[hex(i) for i in uid]}")
                return uid
            time.sleep(0.1)
        logger.debug("Card detection timeout")
        return None

    def read_nfc(self, timeout: float) -> Optional[str]:
        """
        Read data from an NFC card.

        :param timeout: Maximum time in seconds to wait for a card.
        :return: Base64-encoded string of the card's block data or None on failure.
        """
        try:
            uid = self.wait_for_card(timeout)
            if not uid:
                return None

            if not self.pn532.mifare_classic_authenticate_block(
                    uid, 4, MIFARE_CMD_AUTH_KEYA, DEFAULT_KEY):
                logger.error("Authentication failed while reading NFC data")
                return None

            data = self.pn532.mifare_classic_read_block(4)
            if data:
                raw_data = base64.b64encode(bytes(data)).decode('utf-8')
                logger.info(f"Read data (base64): {raw_data}")
                return raw_data
            return None

        except Exception as e:
            logger.exception("Error during NFC read operation")
            return None

    def write_block(self, block_number: int, data: Union[str, bytes]) -> bool:
        """
        Write data to a specific block on the NFC card.

        :param block_number: The block number to write to.
        :param data: Data to write (either a string or bytes).
        :return: True if the write operation is successful, False otherwise.
        """
        try:
            logger.info(f"Waiting for card to write block {block_number}...")
            uid = self.wait_for_card(timeout=5)
            if not uid:
                return False

            # Convert string data to bytes if necessary.
            if isinstance(data, str):
                data = data.encode('utf-8')
            # Ensure data is exactly 16 bytes.
            data = data[:16].ljust(16, b'\x00')

            if not self.pn532.mifare_classic_authenticate_block(uid, block_number, MIFARE_CMD_AUTH_KEYA, DEFAULT_KEY):
                logger.error("Authentication failed while writing NFC data")
                return False

            success = self.pn532.mifare_classic_write_block(block_number, list(data))
            logger.info(f"Write {'successful' if success else 'failed'} for block {block_number}")
            return success

        except Exception as e:
            logger.exception("Error during NFC write operation")
            return False

    def save_card_data(self, uid: List[int], block_data: List[int], encrypted_data: Optional[str] = None) -> None:
        """
        Save NFC card data to a JSON file.

        :param uid: UID of the card.
        :param block_data: Data read from the card block.
        :param encrypted_data: Encrypted data (if any) stored on the card.
        """
        data = {
            "uid": [hex(i) for i in uid],
            "raw_block_data": base64.b64encode(bytes(block_data)).decode('utf-8'),
            "encrypted_data": encrypted_data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        filename = f"card_{'-'.join(hex(i)[2:] for i in uid)}.json"
        filepath = os.path.join(self.storage_path, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved card data to {filepath}")
        except IOError as e:
            logger.error(f"Failed to save card data to {filepath}: {e}")

    def get_card_data(self, uid: List[int]) -> Optional[Dict[str, Any]]:
        """
        Retrieve saved NFC card data from a JSON file.

        :param uid: UID of the card.
        :return: A dictionary of the card data or None if not found.
        """
        filename = f"card_{'-'.join(hex(i)[2:] for i in uid)}.json"
        filepath = os.path.join(self.storage_path, filename)
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Card data file not found: {filepath}")
            return None


class AdminNFC:
    def __init__(self, logger, encryption_manager, pn532_nfc):
        self.logger = logger
        self.encryption_manager = encryption_manager
        self.pn532_nfc = pn532_nfc
        self.logged_in_username = None

    def write_nfc_data(self, data):
        """Write encrypted data to NFC card and update database."""
        if not self.logged_in_username:
            self.logger.log_admin(None, "WriteNFC", success=False, message="No admin logged in")
            return False

        try:
            encrypted = self.encryption_manager.encrypt_data(data)
            encrypted_bytes = base64.b64decode(encrypted)

            uid = self.pn532_nfc.wait_for_card(timeout=5)
            if not uid:
                self.logger.log_admin(self.logged_in_username, "WriteNFC", success=False,
                                      message="No card detected")
                return False

            # Write encrypted data to card
            if not self._write_mifare_classic_block(uid, 4, encrypted_bytes[:16]):
                return False

            # Log success and update database
            self.logger.log_admin(self.logged_in_username, f"WriteNFC[{data}]", success=True)
            return encrypted  # Return encrypted data for database storage

        except Exception as e:
            self.logger.log_admin(self.logged_in_username, "WriteNFC", success=False,
                                  message=str(e))
            return False

    def read_nfc_data(self):
        """Read and decrypt NFC card data."""
        if not self.logged_in_username:
            self.logger.log_admin(None, "ReadNFC", success=False, message="No admin logged in")
            return None

        try:
            uid = self.pn532_nfc.wait_for_card(timeout=5)
            if not uid:
                return None

            block_data = self._read_mifare_classic_block(uid, 4)
            if not block_data:
                return None

            # Convert to base64 and decrypt
            raw_data = base64.b64encode(bytes(block_data)).decode('utf-8')
            decrypted = self.encryption_manager.decrypt_data(raw_data)

            self.logger.log_admin(self.logged_in_username, "ReadNFC", success=True)
            return decrypted

        except Exception as e:
            self.logger.log_admin(self.logged_in_username, "ReadNFC", success=False,
                                  message=str(e))
            return None

    def _write_mifare_classic_block(self, uid, block_number, data):
        """Helper method for writing to Mifare Classic card."""
        try:
            if not self.pn532_nfc.pn532.mifare_classic_authenticate_block(
                    uid, block_number, MIFARE_CMD_AUTH_KEYA, DEFAULT_KEY):
                self.logger.log_admin(self.logged_in_username, "NFCAuth", success=False)
                return False

            # Ensure data is exactly 16 bytes
            if isinstance(data, str):
                data = data.encode('utf-8')
            data = data[:16].ljust(16, b'\x00')

            return self.pn532_nfc.pn532.mifare_classic_write_block(block_number, list(data))

        except Exception as e:
            self.logger.log_admin(self.logged_in_username, "NFCWrite", success=False,
                                  message=str(e))
            return False

    def _read_mifare_classic_block(self, uid, block_number):
        """Helper method for reading from Mifare Classic card."""
        try:
            if not self.pn532_nfc.pn532.mifare_classic_authenticate_block(
                    uid, block_number, MIFARE_CMD_AUTH_KEYA, DEFAULT_KEY):
                self.logger.log_admin(self.logged_in_username, "NFCAuth", success=False)
                return None

            return self.pn532_nfc.pn532.mifare_classic_read_block(block_number)

        except Exception as e:
            self.logger.log_admin(self.logged_in_username, "NFCRead", success=False,
                                  message=str(e))
            return None