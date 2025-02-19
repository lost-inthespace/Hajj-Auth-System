#!/usr/bin/env python3
"""
fingerprint_manager.py

A module to control an R307 fingerprint sensor using the Adafruit Fingerprint library.
Provides functions to enroll a new fingerprint, search for a fingerprint,
display all stored fingerprint data, and delete all fingerprints.
An interactive terminal menu is provided to list and execute these functions.
"""

import os
import json
import time
import serial
import adafruit_fingerprint

from db.hajj_db import get_hajj_records


class FingerprintUI:
    def __init__(
        self,
        uart_device: str = "/dev/ttyAMA0",
        baudrate: int = 57600,
        timeout: float = 1.0,
        storage_path: str = "fingerprint_data",
    ):
        """
        Initialize the FingerprintManager.

        :param uart_device: Serial port device (default: /dev/ttyAMA0)
        :param baudrate: Baudrate for serial communication (default: 57600)
        :param timeout: Serial timeout in seconds (default: 1.0)
        :param storage_path: Directory to store local fingerprint metadata (default: "fingerprint_data")
        """
        self.uart = serial.Serial(uart_device, baudrate, timeout=timeout)
        self.finger = adafruit_fingerprint.Adafruit_Fingerprint(self.uart)
        self.storage_path = storage_path

        # Create the storage directory if it doesn't exist.
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)

        self.data_file = os.path.join(storage_path, "fingerprint_data.json")
        if os.path.exists(self.data_file):
            with open(self.data_file, "r") as f:
                self.fingerprint_data = json.load(f)
        else:
            self.fingerprint_data = {}

    def _save_data(self):
        """Save the local fingerprint metadata to a JSON file."""
        with open(self.data_file, "w") as f:
            json.dump(self.fingerprint_data, f, indent=4)

    def enroll_fingerprint(self, user_id: int = None, user_info: dict = None) -> int:
        """
        Enroll a new fingerprint by capturing it twice.

        :param user_id: Optional numeric ID to assign to the fingerprint. If not provided, the lowest available ID is used.
        :param user_info: Optional dictionary of additional data to associate with this fingerprint.
        :return: The enrolled fingerprint ID if successful; otherwise, None.
        """
        # Determine which fingerprint ID to use.
        if user_id is None:
            # Find the smallest unused integer ID (as a string key in the local storage).
            user_id = 1
            while str(user_id) in self.fingerprint_data:
                user_id += 1

        print("=== Fingerprint Enrollment ===")
        print("Place finger on sensor...")
        # Wait until a finger is detected.
        while self.finger.get_image() != adafruit_fingerprint.OK:
            pass

        # Convert the first image to a template in slot 1.
        if self.finger.image_2_tz(1) != adafruit_fingerprint.OK:
            print("Error: Could not convert image (first scan).")
            return None

        print("Remove finger...")
        time.sleep(2)

        print("Place the same finger again...")
        while self.finger.get_image() != adafruit_fingerprint.OK:
            pass

        # Convert the second image to a template in slot 2.
        if self.finger.image_2_tz(2) != adafruit_fingerprint.OK:
            print("Error: Could not convert image (second scan).")
            return None

        # Create a model by comparing the two templates.
        if self.finger.create_model() != adafruit_fingerprint.OK:
            print("Error: Could not create fingerprint model.")
            return None

        # Store the created model in the sensor's flash memory.
        if self.finger.store_model(user_id) != adafruit_fingerprint.OK:
            print("Error: Could not store fingerprint model.")
            return None

        print(f"Fingerprint enrolled successfully with ID {user_id}.")

        # Save any additional user info locally.
        if user_info is not None:
            self.fingerprint_data[str(user_id)] = user_info
            self. _save_data()

        return user_id

    def search_finger(self) -> dict:
        """
        Search for a fingerprint on the sensor.

        :return: A dictionary with keys 'finger_id', 'confidence', and 'user_info'
                 if a fingerprint is found; otherwise, returns None.
        """
        print("=== Fingerprint Search ===")
        print("Place finger on sensor for search...")
        while self.finger.get_image() != adafruit_fingerprint.OK:
            pass

        if self.finger.image_2_tz(1) != adafruit_fingerprint.OK:
            print("Error: Could not convert image for search.")
            return None

        # Search the sensor's database for a matching fingerprint.
        if self.finger.finger_search() != adafruit_fingerprint.OK:
            print("Fingerprint not found.")
            return None

        # Retrieve the matching fingerprint ID and confidence score.
        finger_id = self.finger.finger_id
        confidence = self.finger.confidence

        # Optionally, retrieve any associated user info from local storage.
        user_info = self.fingerprint_data.get(str(finger_id), None)

        print(f"Fingerprint found! ID: {finger_id}, Confidence: {confidence}")
        return {"finger_id": finger_id, "confidence": confidence, "user_info": user_info}

    def display_all_data(self):
        """
        Display all fingerprint metadata stored locally.
        """
        print("=== Displaying All Fingerprint Data ===")
        if not self.fingerprint_data:
            print("No fingerprint data available.")
            return

        for key, info in self.fingerprint_data.items():
            print(f"Fingerprint ID: {key}")
            if isinstance(info, dict):
                for field, value in info.items():
                    print(f"  {field}: {value}")
            else:
                print(f"  Data: {info}")
            print("-" * 30)

    def check_finger_indb_test(self):
        found, finger_id, conf = self.finger.finger_search
        if not found:
            print("No finger found on sensor.")
            return None

        # Check local storage first
        try:
            filepath = os.path.join(self.finger.storage_path, f"finger_{finger_id}.json")
            with open(filepath, 'r') as f:
                data = json.load(f)
                if data.get('hajj_id'):
                    return data['hajj_id']
        except FileNotFoundError:
            pass

        # Fallback to database check
        fps_docs = get_hajj_records()
        for doc in fps_docs:
            if doc.get("fingerprint_data") == str(finger_id):
                return doc.get("hajj_id")

        return None

    def delete_all_fingerprints(self) -> bool:
        """
        Delete all fingerprints from the sensor and clear local storage.

        :return: True if the deletion process completes.
        """
        print("=== Deleting All Fingerprints ===")
        # The R307 sensor typically allows deletion by fingerprint ID.
        # Loop through a range of possible IDs (adjust the upper limit as needed).
        for template_id in range(1, 128):
            # Attempt to delete each fingerprint. The sensor will return an error if the template does not exist.
            self.finger.delete_model(template_id)
            # (Optional) You can check the return value if you want to report errors.

        # Remove the local metadata file if it exists.
        if os.path.exists(self.data_file):
            os.remove(self.data_file)
        self.fingerprint_data = {}
        print("All fingerprints deleted from sensor and local storage.")
        return True

    def check_specific_finger(self, template_id: int) -> dict:
        """
        Check if the current fingerprint matches a specific template ID.

        :param template_id: The specific template ID to check against
        :return: A dictionary with match result and confidence if found; None if no match
        """
        print(f"=== Checking Fingerprint Against Template {template_id} ===")
        print("Place finger on sensor...")

        # Wait for finger placement
        while self.finger.get_image() != adafruit_fingerprint.OK:
            pass

        # Convert image
        if self.finger.image_2_tz(1) != adafruit_fingerprint.OK:
            print("Error: Could not convert image.")
            return None

        # Load the template for the specified ID into buffer 2
        if self.finger.load_model(template_id, 2) != adafruit_fingerprint.OK:
            print(f"Error: Could not load template {template_id}")
            return None

        # Compare the two templates
        if self.finger.compare_templates() != adafruit_fingerprint.OK:
            print("Fingerprint does not match template.")
            return None

        confidence = self.finger.confidence
        print(f"Match found! Confidence: {confidence}")

        # Get any associated user info
        user_info = self.fingerprint_data.get(str(template_id), None)

        return {
            "matched": True,
            "template_id": template_id,
            "confidence": confidence,
            "user_info": user_info
        }


def interactive_terminal():
    """
    Provides an interactive terminal menu for managing fingerprints.
    """
    # Initialize the fingerprint manager.
    fm = FingerprintUI("/dev/ttyAMA0", 57600, 1)
    menu = """
========== Fingerprint Manager ==========
1. Enroll a new fingerprint
2. Search for a fingerprint
3. Check fingerprints in db (old)
4. Display all fingerprint data
5. Delete all fingerprints
6. Check specific fingerprint ID
7. Exit
===========================================
Enter your choice: """

    while True:
        choice = input(menu).strip()

        if choice == "1":
            print("\n--- Enroll a New Fingerprint ---")
            # Optionally, get extra info (e.g., a username) from the user.
            user_name = input("Enter a name or leave blank: ").strip()
            user_info = {"name": user_name} if user_name else None
            enrolled_id = fm.enroll_fingerprint(user_info=user_info)
            if enrolled_id is not None:
                print(f"Enrolled fingerprint with ID: {enrolled_id}")
            print("\n")

        elif choice == "2":
            print("\n--- Search for a Fingerprint ---")
            result = fm.search_finger()
            if result is not None:
                print("Search result:")
                print(f"  Fingerprint ID: {result['finger_id']}")
                print(f"  Confidence: {result['confidence']}")
                if result["user_info"]:
                    print("  User Info:")
                    for k, v in result["user_info"].items():
                        print(f"    {k}: {v}")
                else:
                    print("  No user info associated.")
            print("\n")

        elif choice == "3":
            print("\n--- Display All Fingerprint Data ---")
            fm.check_finger_indb_test()
            print("\n")

        elif choice == "4":
            print("\n--- Display All Fingerprint Data ---")
            fm.display_all_data()
            print("\n")

        elif choice == "5":
            print("\n--- Delete All Fingerprints ---")
            confirm = input("Are you sure you want to delete ALL fingerprints? (yes/no): ").strip().lower()
            if confirm in ["yes", "y"]:
                fm.delete_all_fingerprints()
            else:
                print("Deletion canceled.")
            print("\n")


        elif choice == "6":

            print("\n--- Check Specific Fingerprint ID ---")

            try:

                template_id = int(input("Enter the template ID to check against: "))

                result = fm.check_specific_finger(template_id)

                if result:

                    print("\nResults:")

                    print(f"Match Found with confidence: {result['confidence']}")

                    if result['user_info']:

                        print("User Info:")

                        for k, v in result['user_info'].items():
                            print(f"  {k}: {v}")

                print("\n")

            except ValueError:

                print("Please enter a valid number.")


        elif choice == "7":

            print("Exiting Fingerprint Manager.")

            break


# If the script is run directly, launch the interactive terminal.
if __name__ == "__main__":
    interactive_terminal()
