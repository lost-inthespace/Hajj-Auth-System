import adafruit_fingerprint
import serial
import time
import json
from datetime import datetime


class FingerprintHandler:
    def __init__(self, uart_device="/dev/ttyAMA0", baudrate=57600, timeout=1):
        # Create a hidden Tkinter root window for messageboxes
        self.root = Tk()
        self.root.withdraw()  # Hide the root window
        self.uart = serial.Serial(uart_device, baudrate, timeout=timeout)
        self.finger = adafruit_fingerprint.Adafruit_Fingerprint(self.uart)

    def get_fingerprint_detail(self):
        """Get fingerprint image and metadata"""
        while True:
            i = self.finger.get_image()
            if i == adafruit_fingerprint.OK:
                # Get the raw fingerprint image data
                # Note: R307 doesn't provide direct access to image data
                # but we can get characteristics

                # Get template size (typically 256 bytes for R307)
                template_size = self.finger.template_count

                # Get current characteristics
                self.finger.image_2_tz(1)

                # Create metadata
                fingerprint_data = {
                    "timestamp": datetime.now().isoformat(),
                    "template_size": template_size,
                    "sensor_security_level": self.finger.security_level,
                    "status": "captured",
                    "location_id": self.finger.template_count
                }

                return fingerprint_data

            elif i == adafruit_fingerprint.NOFINGER:
                continue
            else:
                return None

    def compare_fingerprint(self):
        """Compare current fingerprint against database"""
        while True:
            i = self.finger.get_image()
            if i == adafruit_fingerprint.OK:
                self.finger.image_2_tz(1)

                # Search database for matching print
                i = self.finger.finger_search()
                if i == adafruit_fingerprint.OK:
                    return {
                        "match_found": True,
                        "confidence_score": self.finger.confidence,
                        "template_id": self.finger.finger_id,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "match_found": False,
                        "timestamp": datetime.now().isoformat()
                    }

            elif i == adafruit_fingerprint.NOFINGER:
                continue

    def save_fingerprint_data(self, data, filename="fingerprint_records.json"):
        """Save fingerprint metadata to JSON file"""
        try:
            # Load existing records
            try:
                with open(filename, 'r') as f:
                    records = json.load(f)
            except FileNotFoundError:
                records = []

            # Append new record
            records.append(data)

            # Save updated records
            with open(filename, 'w') as f:
                json.dump(records, f, indent=4)

            return True
        except Exception as e:
            print(f"Error saving data: {e}")
            return False

def test():
    print("Testing finger data API")
    handler = FingerprintHandler()

if __name__ == "__main__":
    test()