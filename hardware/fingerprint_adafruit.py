"""
fingerprint_adafruit.py

Module for managing the Adafruit fingerprint sensor.
"""
from tkinter import messagebox

import serial
import time
import json
import os
import logging
from typing import Optional, Tuple, Any
from db.hajj_db import get_hajj_records
import adafruit_fingerprint

logger = logging.getLogger(__name__)


def log_status(message: str) -> None:
    """
    Log a status message.
    """
    logger.info(f"[Fingerprint Status] {message}")


class FingerprintManager:
    def __init__(
        self,
        uart_device: str = "/dev/ttyAMA0",
        baudrate: int = 57600,
        timeout: float = 1.0,
        storage_path: str = "fingerprint_data"
    ) -> None:
        """
        Initialize the fingerprint sensor.
        """
        try:
            self.uart = serial.Serial(uart_device, baudrate, timeout=timeout)
        except serial.SerialException as e:
            logger.error(f"Failed to initialize serial device {uart_device}: {e}")
            raise

        self.finger = adafruit_fingerprint.Adafruit_Fingerprint(self.uart)
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    def print_status(self, message):
        print(f"[Fingerprint Status] {message}")

    def save_fingerprint_data(self, location, raw_data, template_data, hajj_id=None):
        """Save fingerprint data to JSON file."""
        data = {
            "finger_id": location,
            "hajj_id": hajj_id,
            "raw_image": bytes(raw_data).hex() if raw_data else None,
            "template": bytes(template_data).hex() if template_data else None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        filepath = os.path.join(self.storage_path, f"finger_{location}.json")
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved fingerprint data to {filepath}")

    def wait_for_finger(self, timeout: int = 30) -> bool:
        """Wait for a finger to be placed on the sensor."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.finger.get_image()
            if result == adafruit_fingerprint.OK:
                return True
            elif result == adafruit_fingerprint.NOFINGER:
                time.sleep(0.1)
            else:
                log_status(f"Unexpected result while waiting for finger: {result}")
                return False
        log_status("Timeout waiting for finger.")
        return False

    def wait_for_finger_remove(self, timeout: int = 30) -> bool:
        """Wait for finger to be removed from the sensor."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.finger.get_image() == adafruit_fingerprint.NOFINGER:
                return True
            time.sleep(0.1)
        log_status("Timeout waiting for finger removal.")
        return False

    def enroll_finger(self, location):
        """
        Enhanced debug version of fingerprint enrollment using SystemLogger
        """
        self.print_status("=== Starting fingerprint enrollment process ===")
        self.print_status(f"Target location: {location}")
        raw_images = []
        templates = []

        for finger_img in range(1, 3):
            self.print_status(f"=== Starting capture {finger_img} of 2 ===")
            self.print_status("Waiting for finger placement...")

            if not self.wait_for_finger(timeout=30):
                self.print_status("Timeout waiting for finger")
                return False

            self.print_status("Finger detected, capturing image...")

            try:
                # Try to get raw image data
                self.print_status("Getting raw fingerprint data...")
                raw_image = self.finger.get_fpdata()  # Try without buffer type first
                self.print_status(f"Raw image data type: {type(raw_image)}")
                self.print_status(f"Raw image data length: {len(raw_image) if raw_image else 'None'}")
                raw_images.append(raw_image)
            except Exception as e:
                self.print_status(f"Error getting raw image data: {str(e)}")
                return False

            self.print_status("Converting image to template...")
            i = self.finger.image_2_tz(finger_img)
            if i != adafruit_fingerprint.OK:
                self.print_status(f"Failed to convert image to template. Error code: {i}")
                return False

            try:
                # Try to get template data
                self.print_status("Getting template data...")
                template = self.finger.get_fpdata()  # Try without buffer type
                self.print_status(f"Template data type: {type(template)}")
                self.print_status(f"Template data length: {len(template) if template else 'None'}")
                templates.append(template)
            except Exception as e:
                self.print_status(f"Error getting template data: {str(e)}")
                return False

            if finger_img == 1:
                self.print_status("First capture complete. Waiting for finger removal...")
                if not self.wait_for_finger_remove(timeout=30):
                    self.print_status("Timeout waiting for finger removal")
                    return False
                time.sleep(1)

        self.print_status("Creating model from templates...")
        if self.finger.create_model() != adafruit_fingerprint.OK:
            self.print_status("Failed to create model")
            return False

        self.print_status(f"Storing model at location {location}...")
        if self.finger.store_model(location) != adafruit_fingerprint.OK:
            self.print_status("Failed to store model")
            return False

        try:
            self.print_status("Saving fingerprint data to storage...")
            self.print_status(f"Raw image data type: {type(raw_images[0])}")
            self.print_status(f"Template data type: {type(templates[0])}")
            self.save_fingerprint_data(location, raw_images[0], templates[0])
            self.print_status("Data saved successfully")
        except Exception as e:
            self.print_status(f"Error saving fingerprint data: {str(e)}")
            return False

        self.print_status(f"=== Enrollment successful at location {location} ===")
        return True

    def search_fingerprint(self) -> Tuple[bool, Optional[int], Optional[int]]:
        """Search for a fingerprint match."""
        log_status("Place finger for search (30 seconds)...")
        if not self.wait_for_finger(timeout=30):
            log_status("Timeout waiting for finger.")
            return False, None, None

        if self.finger.image_2_tz(1) != adafruit_fingerprint.OK:
            log_status("Failed to convert image to template for search.")
            return False, None, None

        if self.finger.finger_search() != adafruit_fingerprint.OK:
            log_status("No matching fingerprint found.")
            return False, None, None

        log_status(f"Match found! ID: {self.finger.finger_id}, Confidence: {self.finger.confidence}")
        return True, self.finger.finger_id, self.finger.confidence

    def check_specific_finger(self, template_id: int) -> dict:
        """Check if current fingerprint matches specific template ID."""
        self.print_status(f"=== Checking Fingerprint Against Template {template_id} ===")

        if not self.wait_for_finger(timeout=30):
            self.print_status("Timeout waiting for finger")
            return None

        # Convert image
        if self.finger.image_2_tz(1) != adafruit_fingerprint.OK:
            self.print_status("Error: Could not convert image")
            return None

        # Load template into buffer 2
        if self.finger.load_model(template_id, 2) != adafruit_fingerprint.OK:
            self.print_status(f"Error: Could not load template {template_id}")
            return None

        # Compare templates
        if self.finger.compare_templates() != adafruit_fingerprint.OK:
            self.print_status("Fingerprint does not match template")
            return None

        confidence = self.finger.confidence
        self.print_status(f"Match found! Confidence: {confidence}")

        return {
            "matched": True,
            "template_id": template_id,
            "confidence": confidence
        }

    def delete_model(self, location: int) -> bool:
        """Delete a fingerprint model from the sensor."""
        log_status(f"Deleting fingerprint model at location #{location}...")
        if self.finger.delete_model(location) != adafruit_fingerprint.OK:
            log_status("Failed to delete fingerprint model from sensor.")
            return False

        json_path = os.path.join(self.storage_path, f"finger_{location}.json")
        try:
            os.remove(json_path)
        except FileNotFoundError:
            log_status(f"No saved data found for fingerprint at #{location} to delete.")

        log_status("Fingerprint deletion successful.")
        return True

    def get_num_templates(self) -> int:
        """Get the number of stored templates."""
        if self.finger.count_templates() != adafruit_fingerprint.OK:
            log_status("Failed to retrieve the number of templates.")
            return -1

        log_status(f"Number of templates stored: {self.finger.template_count}")
        return self.finger.template_count


class AdminFingerprint:
    def __init__(self, logger_obj: Any, fingerprint_manager: FingerprintManager) -> None:
        self.logger = logger_obj
        self.fingerprint_manager = fingerprint_manager
        self.logged_in_username: Optional[str] = None

    def show_message(self, title, message, message_type="info"):
        """Show a messagebox with the given title and message."""
        if message_type == "info":
            messagebox.showinfo(title, message)
        elif message_type == "warning":
            messagebox.showwarning(title, message)
        elif message_type == "error":
            messagebox.showerror(title, message)

    def check_fingerprint_in_db(self) -> Optional[str]:
        """Check if the fingerprint is registered in the database."""
        if not self.logged_in_username:
            self.logger.log_admin(None, "CheckFingerprint", success=False,
                                  message="No admin logged in")
            return None

        try:
            found, finger_id, confidence = self.fingerprint_manager.search_fingerprint()
            if not found or finger_id is None:
                return None

            # Search in database records
            hajj_records = get_hajj_records()
            for record in hajj_records:
                if record.get('fingerprint_data') and \
                        record['fingerprint_data'].get('location') == str(finger_id):
                    self.logger.log_admin(
                        self.logged_in_username, "CheckFingerprint", success=True)
                    return record['hajj_id']

            return None

        except Exception as e:
            self.logger.log_admin(self.logged_in_username, "CheckFingerprint",
                                  success=False, message=str(e))
            return None

    def delete_fingerprint(self, location: int) -> bool:
        """Delete a fingerprint from the specified location."""
        if not self.logged_in_username:
            self.logger.log_admin(None, "DeleteFingerprint", success=False,
                                  message="No admin logged in")
            return False

        try:
            if not self.fingerprint_manager.delete_model(location):
                return False

            # Try to delete the corresponding file
            try:
                filepath = os.path.join(
                    self.fingerprint_manager.storage_path, f"finger_{location}.json")
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass  # File deletion is optional

            self.logger.log_admin(
                self.logged_in_username, f"DeleteFingerprint[{location}]", success=True)
            return True

        except Exception as e:
            self.logger.log_admin(
                self.logged_in_username, f"DeleteFingerprint[{location}]",
                success=False, message=str(e))
            return False