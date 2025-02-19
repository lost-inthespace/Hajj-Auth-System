# main.py

import sys
import tkinter as tk

from hardware.nfc_pn532 import PN532NFC, AdminNFC  # Low-level NFC + AdminNFC
from hardware.fingerprint_adafruit import FingerprintManager, AdminFingerprint  # Low-level + Admin
from utils.encryption_manager import EncryptionKeyManager
# from door_sensor import DoorSensor
from hardware.camera_manager import CameraManager
from utils.logger_module import SystemLogger
from logic.user_workflow import UserWorkflow
from logic.workflow_phase import WorkflowPhase
from ui.user_workflow_gui import UserWorkflowGUI
from ui.pyside6_scenes import HajjAuthenticationWindow, SceneManager, SceneType
from PySide6.QtWidgets import QApplication

# The Tkinter-based admin GUI
from logic.admin_app import AdminAppGUI

def main():
    logger = SystemLogger()

    # 1) Initialize Encryption Manager
    encryption_manager = EncryptionKeyManager()

    # 2) Initialize NFC (PN532) over spidev0.0
    nfc_reader = PN532NFC(spi_bus=0, spi_device=0, debug=True)

    # 3) Initialize Fingerprint sensor
    fingerprint_manager = FingerprintManager("/dev/ttyAMA0", 57600, 1)

    # 4) Initialize Door Sensor
    # door_sensor = DoorSensor()

    # 5) Initialize Camera manager (head counting)
    camera_manager = CameraManager()

    # 6) Initialize PySide6
    app = QApplication([])

    # Check command-line arg for "admin" mode
    if len(sys.argv) > 1 and sys.argv[1] == "admin":
        print("[INFO] Starting Admin GUI...")

        # Create a Tk window for the admin GUI
        root = tk.Tk()

        # Create the specialized 'AdminNFC' and 'AdminFingerprint' for admin tasks
        admin_nfc = AdminNFC(logger, encryption_manager, nfc_reader)
        admin_fp = AdminFingerprint(logger, fingerprint_manager)

        # Create the admin GUI (login + admin features)
        app = AdminAppGUI(
            root=root,
            logger=logger,
            admin_nfc=admin_nfc,
            admin_fingerprint=admin_fp
        )

        # Run the Tkinter main loop (blocks until GUI closes)
        root.mainloop()
        return  # Exit after admin GUI is closed

    # Otherwise, run the user workflow
    print("[INFO] Starting User Workflow (Phase 1 & 2).")

    # Initialize PySide6
    window = HajjAuthenticationWindow()

    # Initialize user workflow with all dependencies
    user_flow = UserWorkflow(
        logger=logger,
        nfc=nfc_reader,
        fingerprint_manager=fingerprint_manager,
        # door_sensor=door_sensor,
        camera_manager=camera_manager,
        encryption_manager = encryption_manager  # Add this since we need it for decryption
    )

    # Start the workflow (this initializes the UI and starts Phase 1)
    user_flow.run()
    # Show the window
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

