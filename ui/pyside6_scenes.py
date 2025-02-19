# ui/pyside_scenes.py

import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStackedWidget, QPushButton, QTreeWidget, QTreeWidgetItem,
    QDialog, QLineEdit, QGridLayout, QTextEdit, QScrollArea,
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QSize, QTimer, Signal, Slot, QTime
from PySide6.QtGui import QMovie, QFont, QImage, QPixmap
import cv2
import numpy as np
import time
import os
from enum import Enum, auto
import logging

from db.hajj_db import get_hajj_records
from logic.workflow_phase import WorkflowPhase

logger = logging.getLogger(__name__)


class SceneType(Enum):
    """Enum for different scene types in the workflow"""
    CARD_SCAN = auto()
    FINGER_SCAN = auto()
    SUCCESS = auto()
    WAIT = auto()
    FINGER_FAILED = auto()
    CARD_FAILED = auto()
    INVALID_FINGERPRINT = auto()
    ACCESS_DENIED = auto()
    PIN_ENTRY = auto()
    TRIP_COMPLETE = auto()
    HEADCOUNT_PROCESSING = auto()
    HEADCOUNT_RESULT = auto()


class MessageType(Enum):
    """Enum for message types in status bar"""
    INFO = "#2196F3"
    SUCCESS = "#4CAF50"
    WARNING = "#FFC107"
    ERROR = "#F44336"


class NumPad(QWidget):
    """Custom NumPad widget for PIN entry"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout()
        buttons = [
            ['1', '2', '3', '⌫'],
            ['4', '5', '6', 'Enter'],
            ['7', '8', '9', '0']
        ]

        for i, row in enumerate(buttons):
            for j, text in enumerate(row):
                btn = QPushButton(text)
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        padding: 10px;
                        min-width: 60px;
                        min-height: 60px;
                    }
                """)
                layout.addWidget(btn, i, j)
                if text == 'Enter':
                    btn.clicked.connect(self.parent().check_pin)
                elif text == '⌫':
                    btn.clicked.connect(self.parent().clear_pin)
                else:
                    # Simplified lambda without unused parameter
                    btn.clicked.connect(lambda _, t=text: self.parent().add_pin_digit(t))

        self.setLayout(layout)


class PinEntryDialog(QDialog):
    """Dialog for PIN entry with NumPad"""

    pin_verified = Signal()

    def __init__(self, correct_pin="1234", parent=None):
        super().__init__(parent)
        self.correct_pin = correct_pin
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Enter PIN")
        layout = QVBoxLayout()

        # PIN Entry field
        self.pin_entry = QLineEdit()
        self.pin_entry.setEchoMode(QLineEdit.Password)
        self.pin_entry.setAlignment(Qt.AlignCenter)
        self.pin_entry.setStyleSheet("""
            QLineEdit {
                font-size: 24px;
                padding: 10px;
                margin: 10px;
            }
        """)
        layout.addWidget(self.pin_entry)

        # Add NumPad
        numpad = NumPad(self)
        layout.addWidget(numpad)

        self.setLayout(layout)

    def add_pin_digit(self, digit):
        if len(self.pin_entry.text()) < 4:
            self.pin_entry.setText(self.pin_entry.text() + digit)

    def clear_pin(self):
        self.pin_entry.clear()

    def check_pin(self):
        if self.pin_entry.text() == self.correct_pin:
            self.pin_verified.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid PIN")
            self.clear_pin()


class HajjScene(QWidget):
    """Base class for all scenes in the Hajj Authentication System"""

    def __init__(self, gif_path: str, message: str, parent=None):
        super().__init__(parent)
        self.gif_path = gif_path
        self.message = message
        self.setStyleSheet("background-color: #FFFFFF;")
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout()
        message_container = QWidget()
        message_layout = QVBoxLayout()

        self.message_label = QLabel(self.message)
        self.message_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Align text to left
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("""
                    QLabel {
                        font-size: 36px;
                        font-weight: bold;
                        padding: 20px;
                        color: #2C3E50;
                    }
                """)
        message_layout.addWidget(self.message_label)
        message_layout.addStretch()  # Push message to top
        message_container.setLayout(message_layout)
        main_layout.addWidget(message_container, 1)  # 1 part for message

        # Right side - GIF
        if self.gif_path and os.path.exists(self.gif_path):
            gif_container = QWidget()
            gif_layout = QVBoxLayout()

            self.gif_label = QLabel()
            self.gif_label.setAlignment(Qt.AlignCenter)
            self.movie = QMovie(self.gif_path)
            self.movie.setScaledSize(QSize(400, 400))  # Fixed size 400x400
            self.gif_label.setMovie(self.movie)
            self.movie.start()

            gif_layout.addWidget(self.gif_label)
            gif_container.setLayout(gif_layout)
            main_layout.addWidget(gif_container, 1)  # 1 part for GIF

        self.setLayout(main_layout)


class CameraTestWindow(QDialog):
    """Window for testing camera with person detection"""

    def __init__(self, camera_manager, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.setup_ui()
        self.start_time = time.time()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(50)  # 20 FPS

    def setup_ui(self):
        self.setWindowTitle("Camera Test")
        layout = QVBoxLayout()

        self.time_label = QLabel("Time remaining: 5s")
        self.time_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.time_label)

        self.image_label = QLabel()
        layout.addWidget(self.image_label)

        self.setLayout(layout)

    def update_frame(self):
        elapsed = time.time() - self.start_time
        if elapsed >= 5:
            self.timer.stop()
            self.accept()
            return

        # Update time label
        remaining = 5 - int(elapsed)
        self.time_label.setText(f"Time remaining: {remaining}s")

        # Capture and process frame
        success, frame = self.camera_manager.cap.read()
        if not success:
            self.timer.stop()
            QMessageBox.critical(self, "Error", "Failed to read from camera")
            self.accept()
            return

        # Process frame with YOLO
        results = self.camera_manager.model(frame, verbose=False)[0]
        frame_with_detections = results.plot()

        # Count people
        person_count = sum(1 for box in results.boxes if box.cls == 0)

        # Add person count overlay
        cv2.putText(
            frame_with_detections,
            f'People detected: {person_count}',
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        # Convert to QPixmap and display
        rgb_image = cv2.cvtColor(frame_with_detections, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.image_label.setPixmap(pixmap.scaled(640, 480, Qt.KeepAspectRatio))


class DevPanel(QDialog):
    """Developer control panel"""

    def __init__(self, workflow, parent=None):
        super().__init__(parent)
        self.workflow = workflow
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Developer Panel")
        self.setGeometry(100, 100, 800, 480)  # Full screen size

        layout = QVBoxLayout()
        grid = QGridLayout()
        grid.setSpacing(10)  # Increased spacing between buttons

        # Common button style
        button_style = """
                    QPushButton {
                        font-size: 16px;  /* Reduced from 24px */
                        padding: 10px;    /* Reduced from 20px */
                        min-height: 50px; /* Reduced from 80px */
                        min-width: 140px; /* Reduced from 180px */
                        background-color: #3498db;
                        color: white;
                        border-radius: 8px;
                    }
                    QPushButton:pressed {
                        background-color: #2980b9;
                    }
                    QPushButton:disabled {
                        background-color: #bdc3c7;
                    }
                """

        # Row 1: Hardware Tests
        buttons = [
            ("Test Hardware", self.test_hardware),
            ("Test Camera", self.test_camera),
            ("Toggle Door", self.toggle_door)
        ]

        for col, (text, callback) in enumerate(buttons):
            btn = QPushButton(text)
            btn.setStyleSheet(button_style)
            btn.clicked.connect(callback)
            grid.addWidget(btn, 0, col)

        # Row 2: System Controls
        buttons = []

        # End Trip button - only enabled in Phase Two
        if self.workflow.current_phase == WorkflowPhase.PHASE_TWO:
            end_trip_btn = QPushButton("End Trip")
            end_trip_btn.clicked.connect(self.workflow.end_trip)
        else:
            end_trip_btn = QPushButton("End Trip (Disabled)")
            end_trip_btn.setEnabled(False)
        end_trip_btn.setStyleSheet(button_style)
        grid.addWidget(end_trip_btn, 1, 0)

        # Add other system controls
        buttons = [
            ("View Logs", self.show_logs),
            ("System Info", self.show_system_info)
        ]
        for col, (text, callback) in enumerate(buttons, 1):
            btn = QPushButton(text)
            btn.setStyleSheet(button_style)
            btn.clicked.connect(callback)
            grid.addWidget(btn, 1, col)

        # Row 3: Window Controls
        buttons = [
            ("Toggle Fullscreen", self.toggle_fullscreen),
            ("Reset UI", self.reset_ui),
            ("Exit Program", self.exit_program)
        ]

        buttons = [("Show Passengers", self.show_scanned_passengers)]

        for col, (text, callback) in enumerate(buttons):
            btn = QPushButton(text)
            btn.setStyleSheet(button_style)
            btn.clicked.connect(callback)
            grid.addWidget(btn, 2, col)

        layout.addLayout(grid)

        # Status label at bottom
        self.status_label = QLabel("Developer Mode Active")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                padding: 10px;
                color: #7f8c8d;
            }
        """)
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def show_scanned_passengers(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Scanned Passengers")
        dialog.setGeometry(100, 100, 400, 500)

        layout = QVBoxLayout()

        # Add header label
        header = QLabel("Successfully Scanned Passengers")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Create tree widget for passenger list
        tree = QTreeWidget()
        tree.setHeaderLabels(["Hajj ID", "Name", "Scan Time"])
        tree.setStyleSheet("QTreeWidget { font-size: 14px; }")

        try:
            for hajj_id in self.workflow.hajj_id_scans:
                name = "Unknown"
                scan_time = datetime.datetime.now().strftime("%H:%M:%S")

                # Look up passenger name from records
                for record in get_hajj_records():
                    if record['hajj_id'] == hajj_id:
                        name = record.get('name', 'Unknown')
                        break

                item = QTreeWidgetItem([hajj_id, name, scan_time])
                tree.addTopLevelItem(item)
        except Exception as e:
            logger.exception("Failed to fetch passenger data")
            QMessageBox.critical(self, "Error", f"Failed to fetch passenger data: {str(e)}")

        layout.addWidget(tree)

        # Add close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)
        dialog.exec()

    def test_hardware(self):
        results = []
        try:
            # Test NFC
            ic_version = self.workflow.nfc.pn532.firmware_version
            results.append(f"NFC: OK (Firmware: {[hex(i) for i in ic_version]})")
        except Exception as e:
            results.append(f"NFC: Failed ({str(e)})")

        try:
            # Test Fingerprint
            count = self.workflow.fingerprint_manager.get_num_templates()
            results.append(f"Fingerprint Sensor: OK ({count} templates)")
        except Exception as e:
            results.append(f"Fingerprint: Failed ({str(e)})")

        try:
            # Test Camera
            if self.workflow.camera_manager:
                if self.workflow.camera_manager.cap.isOpened():
                    results.append("Camera: OK")
                else:
                    results.append("Camera: Not opened")
            else:
                results.append("Camera: Not initialized")
        except Exception as e:
            results.append(f"Camera: Failed ({str(e)})")

        QMessageBox.information(self, "Hardware Test Results", "\n".join(results))

    def test_camera(self):
        if not self.workflow.camera_manager:
            QMessageBox.critical(self, "Error", "Camera not initialized")
            return

        camera_test = CameraTestWindow(self.workflow.camera_manager, self)
        camera_test.exec()

    def show_logs(self):
        log_dialog = QDialog(self)
        log_dialog.setWindowTitle("System Logs")
        log_dialog.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setFont(QFont("Courier", 10))

        try:
            # Read admin logs
            with open("logs/admin/admin_log.txt", "r") as f:
                log_text.append("=== Admin Logs ===\n")
                log_text.append(f.read() + "\n\n")

            # Read user logs
            with open("logs/user/user_log.txt", "r") as f:
                log_text.append("=== User Logs ===\n")
                log_text.append(f.read())

        except Exception as e:
            log_text.append(f"Error reading logs: {str(e)}")

        layout.addWidget(log_text)
        log_dialog.setLayout(layout)
        log_dialog.exec()

    def show_system_info(self):
        info_text = f"""
System Information:
------------------
Current Phase: {self.workflow.current_phase.name}
Door Status: {'Open' if self.workflow.door_status else 'Closed'}
Current Trip: {self.workflow.trip_number}
Scanned Passengers: {len(self.workflow.hajj_id_scans)}
NFC Reader: {'Connected' if self.workflow.nfc else 'Not Connected'}
Fingerprint Sensor: {'Connected' if self.workflow.fingerprint_manager else 'Not Connected'}
Camera: {'Connected' if self.workflow.camera_manager else 'Not Connected'}
"""
        QMessageBox.information(self, "System Information", info_text.strip())

    def toggle_fullscreen(self):
        parent = self.parent()
        if parent:
            parent.setWindowState(parent.windowState() ^ Qt.WindowFullScreen)

    def reset_ui(self):
        if QMessageBox.question(self, "Confirm Reset", "Reset UI to initial state?") == QMessageBox.Yes:
            self.workflow.current_phase = WorkflowPhase.PHASE_ONE
            self.workflow.scene_manager.switch_to_scene(SceneType.CARD_SCAN)

    def exit_program(self):
        if QMessageBox.question(self, "Exit", "Are you sure you want to exit?") == QMessageBox.Yes:
            QApplication.quit()

    def toggle_door(self):
        self.workflow.door_status = not self.workflow.door_status
        status = "Open" if self.workflow.door_status else "Closed"
        self.workflow.show_message(f"Door Status: {status}",
                                   MessageType.INFO if self.workflow.door_status else MessageType.WARNING)


class WorkflowPinEntry(QWidget):
    """PIN entry scene for the main workflow"""

    pin_verified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pin = ""
        self.correct_pin = "1234"  # Should be configurable
        self.setup_ui()

    def setup_ui(self):
        # Main horizontal layout for side-by-side design
        main_layout = QHBoxLayout()

        # Left side - Message and PIN display
        left_container = QWidget()
        left_layout = QVBoxLayout()

        # Message area
        message_label = QLabel("Enter PIN to Start Trip")
        message_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        message_label.setStyleSheet("""
            QLabel {
                font-size: 36px;
                font-weight: bold;
                color: #2C3E50;
                padding: 20px;
            }
        """)
        left_layout.addWidget(message_label)

        # PIN display
        self.pin_display = QLineEdit()
        self.pin_display.setEchoMode(QLineEdit.Password)
        self.pin_display.setAlignment(Qt.AlignCenter)
        self.pin_display.setReadOnly(True)
        self.pin_display.setStyleSheet("""
            QLineEdit {
                font-size: 48px;
                padding: 20px;
                margin: 20px;
                border: 3px solid #3498db;
                border-radius: 15px;
                background-color: white;
                min-height: 80px;
                max-width: 300px;
            }
        """)
        left_layout.addWidget(self.pin_display)

        # Add status label for feedback
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #e74c3c;
                padding: 10px;
                min-height: 40px;
            }
        """)
        left_layout.addWidget(self.status_label)

        left_layout.addStretch()
        left_container.setLayout(left_layout)
        main_layout.addWidget(left_container)

        # Right side - NumPad
        right_container = QWidget()
        right_layout = QVBoxLayout()

        numpad_grid = QGridLayout()
        numpad_grid.setSpacing(15)  # Increased spacing between buttons

        # Button style
        button_style = """
                    QPushButton {
                        font-size: 24px;  /* Reduced from 32px */
                        font-weight: bold;
                        padding: 7px;     /* Reduced from 10px */
                        min-width: 70px;  /* Reduced from 100px */
                        min-height: 70px; /* Reduced from 100px */
                        border-radius: 35px; /* Half of height for circle */
                        background-color: #f8f9fa;
                        color: #2C3E50;
                        border: 2px solid #e9ecef;
                    }
                    QPushButton:pressed {
                        background-color: #e9ecef;
                    }
                    QPushButton#clearButton {
                        background-color: #ffeae9;
                        border-color: #ffd0c9;
                        color: #e74c3c;
                    }
                    QPushButton#enterButton {
                        background-color: #edfdf8;
                        border-color: #c3f3e3;
                        color: #2ecc71;
                    }
                """

        # Create buttons with curved style
        buttons = [
            ['1', '2', '3'],
            ['4', '5', '6'],
            ['7', '8', '9'],
            ['⌫', '0', '✓']
        ]

        for i, row in enumerate(buttons):
            for j, text in enumerate(row):
                btn = QPushButton(text)
                btn.setStyleSheet(button_style)

                if text == '⌫':
                    btn.setObjectName("clearButton")
                    btn.clicked.connect(self.backspace)
                elif text == '✓':
                    btn.setObjectName("enterButton")
                    btn.clicked.connect(self.verify_pin)
                else:
                    btn.clicked.connect(lambda checked, digit=text: self.add_digit(digit))

                numpad_grid.addWidget(btn, i, j)

        right_layout.addLayout(numpad_grid)
        right_layout.addStretch()
        right_container.setLayout(right_layout)
        main_layout.addWidget(right_container)

        self.setLayout(main_layout)

    def add_digit(self, digit):
        if len(self.current_pin) < 4:
            self.current_pin += digit
            self.pin_display.setText('●' * len(self.current_pin))
            self.status_label.clear()

    def backspace(self):
        if self.current_pin:
            self.current_pin = self.current_pin[:-1]
            self.pin_display.setText('●' * len(self.current_pin))
            self.status_label.clear()

    def verify_pin(self):
        if not self.current_pin:
            self.status_label.setText("Please enter PIN")
            return

        if self.current_pin == self.correct_pin:
            self.pin_display.setStyleSheet("""
                QLineEdit {
                    font-size: 48px;
                    padding: 20px;
                    margin: 20px;
                    border: 3px solid #2ecc71;
                    border-radius: 15px;
                    background-color: #edfdf8;
                    min-height: 80px;
                    max-width: 300px;
                }
            """)
            self.current_pin = ""  # Clear PIN immediately
            QTimer.singleShot(500, self.pin_verified.emit)  # Emit signal after visual feedback
        else:
            self.pin_display.setStyleSheet("""
                QLineEdit {
                    font-size: 48px;
                    padding: 20px;
                    margin: 20px;
                    border: 3px solid #e74c3c;
                    border-radius: 15px;
                    background-color: #ffeae9;
                    min-height: 80px;
                    max-width: 300px;
                }
            """)
            self.status_label.setText("Incorrect PIN")
            QTimer.singleShot(1000, self.reset_display_style)
            self.current_pin = ""
            self.pin_display.clear()

    def reset_display_style(self):
        self.pin_display.setStyleSheet("""
            QLineEdit {
                font-size: 48px;
                padding: 20px;
                margin: 20px;
                border: 3px solid #3498db;
                border-radius: 15px;
                background-color: white;
                min-height: 80px;
                max-width: 300px;
            }
        """)
        self.status_label.clear()


class SceneManager(QStackedWidget):
    """Manages different scenes in the Hajj Authentication System"""

    scene_changed = Signal(SceneType)  # Signal emitted when scene changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes = {}
        self.current_scene_type = None
        self.initialize_scenes()

    def initialize_scenes(self):
        """Initialize all scenes with their respective GIFs and messages"""
        base_path = "/home/has/has-pi/ui"
        self.setStyleSheet("background-color: #FFFFFF;")

        # Initialize PIN_ENTRY scene separately
        pin_entry_scene = WorkflowPinEntry()
        pin_entry_scene.pin_verified.connect(lambda: self.handle_pin_verified())
        self.scenes[SceneType.PIN_ENTRY] = pin_entry_scene
        self.addWidget(pin_entry_scene)

        headcount_processing = HeadcountProcessingScene()
        self.scenes[SceneType.HEADCOUNT_PROCESSING] = headcount_processing
        self.addWidget(headcount_processing)

        headcount_result = HeadcountResultScene()
        self.scenes[SceneType.HEADCOUNT_RESULT] = headcount_result
        self.addWidget(headcount_result)

        # Add trip complete scene
        trip_complete_scene = TripCompleteScene()
        self.scenes[SceneType.TRIP_COMPLETE] = trip_complete_scene
        self.addWidget(trip_complete_scene)

        scene_configs = {
            SceneType.CARD_SCAN: (
                f"{base_path}/card_scan.gif",
                "Please put your card in the scan area"
            ),
            SceneType.FINGER_SCAN: (
                f"{base_path}/finger_scan.gif",
                "Please put your finger in the scanner"
            ),
            SceneType.SUCCESS: (
                f"{base_path}/success.gif",
                "Successful, Please be seated"
            ),
            SceneType.WAIT: (
                f"{base_path}/wait.gif",
                "Wait..."
            ),
            SceneType.FINGER_FAILED: (
                f"{base_path}/fingerprint_failed.gif",
                "Scan Failed, please put your fingerprint again"
            ),
            SceneType.CARD_FAILED: (
                f"{base_path}/card_failed.gif",
                "Scan Failed, please scan the card again"
            ),
            SceneType.INVALID_FINGERPRINT: (
                f"{base_path}/invalid_fingerprint.gif",
                "Fingerprint does not belong to the Card Holder"
            ),
            SceneType.ACCESS_DENIED: (
                f"{base_path}/access_denied.gif",
                "You are not allowed to enter the bus"
            ),
            SceneType.PIN_ENTRY: (
                None,  # No GIF for PIN entry
                "Enter PIN to start trip"
            )
        }

        # Remove PIN_ENTRY from scene_configs
        if SceneType.PIN_ENTRY in scene_configs:
            del scene_configs[SceneType.PIN_ENTRY]

        for scene_type, (gif_path, message) in scene_configs.items():
            scene = HajjScene(gif_path, message)
            self.scenes[scene_type] = scene
            self.addWidget(scene)

    @Slot(SceneType)
    def switch_to_scene(self, scene_type: SceneType):
        """Switch to the specified scene"""
        if scene_type in self.scenes:
            self.setCurrentWidget(self.scenes[scene_type])
            self.current_scene_type = scene_type
            self.scene_changed.emit(scene_type)

    def get_current_scene(self) -> HajjScene:
        """Get the currently displayed scene"""
        return self.scenes.get(self.current_scene_type)

    def handle_pin_verified(self):
        """Handle successful PIN verification."""
        if self.parent().workflow:
            workflow = self.parent().workflow
            # Ensure we're in the correct phase
            if workflow.current_phase == WorkflowPhase.PHASE_TWO:
                # First switch to processing scene
                self.switch_to_scene(SceneType.HEADCOUNT_PROCESSING)
                # Then start trip processing after a short delay
                QTimer.singleShot(1000, workflow.start_trip)


class HajjAuthenticationWindow(QWidget):
    """Main window for the Hajj Authentication System"""

    def __init__(self, workflow=None):
        super().__init__()
        self.workflow = workflow
        self.setup_ui()

    def setup_ui(self):
        """Initialize the main window UI"""
        self.setWindowTitle("Hajj Authentication System")
        self.setGeometry(100, 100, 800, 480)
        self.setWindowState(Qt.WindowFullScreen)

        layout = QVBoxLayout()

        # Title Bar
        title_bar = QHBoxLayout()
        title_label = QLabel("Hajj Authentication System")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_bar.addWidget(title_label)

        # Dev and Exit buttons
        button_layout = QHBoxLayout()
        dev_button = QPushButton("DEV")
        dev_button.clicked.connect(self.show_dev_login)
        exit_button = QPushButton("×")
        exit_button.clicked.connect(self.close_program)

        button_layout.addWidget(dev_button)
        button_layout.addWidget(exit_button)
        title_bar.addLayout(button_layout)

        layout.addLayout(title_bar)

        # Scene Manager
        self.scene_manager = SceneManager()
        layout.addWidget(self.scene_manager)

        # Status Bar
        self.status_label = QLabel("System Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                padding: 10px;
                color: #2196F3;
            }
        """)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def show_dev_login(self):
        """Show developer login dialog"""
        pin_dialog = PinEntryDialog("1234", self)
        pin_dialog.pin_verified.connect(self.show_dev_panel)
        pin_dialog.exec()

    def show_dev_panel(self):
        """Show developer control panel"""
        dev_panel = DevPanel(self.workflow, self)
        dev_panel.exec()

    def show_message(self, message: str, message_type: MessageType = MessageType.INFO):
        """Update status bar message"""
        self.status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                padding: 10px;
                color: {message_type.value};
            }}
        """)
        self.status_label.setText(message)

    def close_program(self):
        """Safely close the application"""
        if QMessageBox.question(self, "Exit", "Are you sure you want to exit?") == QMessageBox.Yes:
            QApplication.quit()

    def keyPressEvent(self, event):
        """Handle key press events for development/testing"""
        if event.key() == Qt.Key_Escape:
            self.close_program()
        # Map number keys 1-9 to different scenes for testing
        elif Qt.Key_1 <= event.key() <= Qt.Key_9:
            scene_types = list(SceneType)
            if event.key() - Qt.Key_1 < len(scene_types):
                self.scene_manager.switch_to_scene(scene_types[event.key() - Qt.Key_1])

class TripCompleteScene(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title = QLabel("Trip Complete")
        title.setStyleSheet("""
            QLabel {
                font-size: 36px;
                font-weight: bold;
                color: #2C3E50;
                padding: 20px;
            }
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Trip Info
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("""
            QTextEdit {
                font-size: 18px;
                padding: 20px;
                border: none;
                background-color: #f8f9fa;
            }
        """)
        layout.addWidget(self.info_text)

        # New Trip Button
        new_trip_btn = QPushButton("Start New Trip")
        new_trip_btn.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                font-weight: bold;
                padding: 15px 30px;
                border-radius: 10px;
                background-color: #2ecc71;
                color: white;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        new_trip_btn.clicked.connect(self.start_new_trip)
        layout.addWidget(new_trip_btn, alignment=Qt.AlignCenter)

        self.setLayout(layout)

    def update_trip_info(self, trip_data):
        """Update the trip information display"""
        info = f"""
Trip Summary:
------------
Trip Number: {trip_data['trip_number']}
Passengers: {trip_data['passenger_count']}
Start Time: {trip_data['start_time']}
End Time: {trip_data['end_time']}
Duration: {int(trip_data['duration_seconds'] / 60)} minutes

Passenger List:
{self.format_passenger_list(trip_data['hajj_ids'])}
"""
        self.info_text.setText(info)

    def format_passenger_list(self, hajj_ids):
        """Format the passenger list with names from database"""
        passenger_list = []
        for hajj_id in hajj_ids:
            name = "Unknown"
            for record in get_hajj_records():
                if record['hajj_id'] == hajj_id:
                    name = record.get('name', 'Unknown')
                    break
            passenger_list.append(f"• {hajj_id}: {name}")
        return "\n".join(passenger_list)

    def start_new_trip(self):
        """Reset workflow for new trip"""
        workflow = self.parent().parent().workflow
        workflow.reset_for_new_trip()

class HeadcountProcessingScene(HajjScene):
    def __init__(self, parent=None):
        gif_path = "/home/has/has-pi/ui/wait.gif"
        message = "Devices are processing, please wait..."
        super().__init__(gif_path, message, parent)

class HeadcountResultScene(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #FFFFFF;")
        self.setup_ui()

    def setup_ui(self):
        # Main horizontal layout for side-by-side design
        main_layout = QHBoxLayout()

        # Left side - Text content
        left_container = QWidget()
        left_layout = QVBoxLayout()

        # Result message
        self.result_label = QLabel()
        self.result_label.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                color: #2C3E50;
                padding: 20px;
            }
        """)
        self.result_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.result_label.setWordWrap(True)
        left_layout.addWidget(self.result_label)

        # "Have a safe trip" message
        safe_trip_label = QLabel("Have a safe trip")
        safe_trip_label.setStyleSheet("""
            QLabel {
                font-size: 36px;
                font-weight: bold;
                color: #2ecc71;
                padding: 20px;
            }
        """)
        safe_trip_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        left_layout.addWidget(safe_trip_label)

        left_layout.addStretch()  # Push content to top
        left_container.setLayout(left_layout)
        main_layout.addWidget(left_container,1)

        right_container = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins

        self.logo_label = QLabel()
        target_height = 330  # Leave some margin from 480
        target_width = int(target_height * (1200 / 1920))  # Maintain aspect ratio

        self.movie = QMovie("/home/has/has-pi/ui/has-logo.gif")
        self.movie.setScaledSize(QSize(target_width, target_height))
        self.logo_label.setMovie(self.movie)
        self.movie.start()
        self.logo_label.setAlignment(Qt.AlignCenter)

        right_layout.addWidget(self.logo_label)
        right_container.setLayout(right_layout)
        main_layout.addWidget(right_container)

        # Remove any extra spacing
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.setLayout(main_layout)

    def set_result(self, success: bool, message: str):
        """Update the result message and styling"""
        color = "#2ecc71" if success else "#e74c3c"
        self.result_label.setStyleSheet(f"""
            QLabel {{
                font-size: 32px;
                font-weight: bold;
                color: {color};
                padding: 20px;
            }}
        """)
        self.result_label.setText(message)

    def showEvent(self, event):
        """Ensure GIF starts playing when scene becomes visible"""
        super().showEvent(event)
        if hasattr(self, 'movie'):
            self.movie.start()

    def hideEvent(self, event):
        """Stop GIF when scene is hidden to save resources"""
        super().hideEvent(event)
        if hasattr(self, 'movie'):
            self.movie.stop()