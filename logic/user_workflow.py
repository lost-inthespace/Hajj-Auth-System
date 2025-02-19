# logic/user_workflow.py

import datetime
import logging
from typing import Optional, List, Any

from PySide6.QtCore import QTimer

from db.hajj_db import get_hajj_records
from hardware.sound_manager import SoundManager
from logic.user_workflow_helpers import (
    verify_nfc_data,
    perform_headcount_check,
    handle_door_status,
    process_trip_data,
    cleanup_hardware
)
from logic.workflow_phase import WorkflowPhase
from ui.pyside6_scenes import SceneType, MessageType, TripCompleteScene, HeadcountResultScene, HajjScene

logger = logging.getLogger(__name__)


class UserWorkflow:
    def __init__(
            self,
            logger: Any,
            nfc: Any,
            fingerprint_manager: Any,
            camera_manager: Optional[Any] = None,
            encryption_manager: Optional[Any] = None,
            gui_window: Any = None
    ) -> None:
        """Initialize workflow components and state."""
        # Hardware components
        self.logger = logger
        self.nfc = nfc
        self.fingerprint_manager = fingerprint_manager
        self.camera_manager = camera_manager
        self.encryption_manager = encryption_manager
        self.gui_window = gui_window
        self.scene_manager = gui_window.scene_manager if gui_window else None
        self.sound_manager = SoundManager()

        # State tracking / flags
        self.current_phase = WorkflowPhase.PHASE_ONE
        self.hajj_id_scans: List[str] = []
        self.trip_number: int = 1
        self.trip_start_time: Optional[datetime.datetime] = None
        self.trip_end_time: Optional[datetime.datetime] = None
        self.door_status: bool = True
        self.nfc_reader_active = True

        # Door monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_nfc_and_door)

        # Initialize scene transitions
        if self.scene_manager:
            self.scene_manager.scene_changed.connect(self.handle_scene_change)
            self.scene_manager.switch_to_scene(SceneType.CARD_SCAN)

        # Start monitoring
        self.start_phase_one()

    def switch_to_scene(self, scene_type: SceneType):
        try:
            if self.scene_manager:
                self.scene_manager.switch_to_scene(scene_type)
        except Exception as e:
            logger.error(f"Error switching to scene {scene_type}: {e}")

    def cleanup(self):
        """Clean up resources"""
        try:
            self.monitor_timer.stop()
            cleanup_hardware(self.camera_manager)
            # Any other cleanup needed
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def handle_scene_change(self, scene_type: SceneType):
        """Handle scene change events"""
        try:
            logger.info(f"Scene changed to: {scene_type.name}")
            if scene_type == SceneType.CARD_SCAN:
                self.nfc_reader_active = True  # Enable NFC reading
            elif scene_type == SceneType.FINGER_SCAN:
                self.nfc_reader_active = False  # Disable NFC reading
        except Exception as e:
            logger.error(f"Error handling scene change: {e}")

    def run(self) -> None:
        """Start the workflow application."""
        # No need for mainloop() as it's handled by PySide6 QApplication
        self.start_phase_one()

    def start_phase_one(self) -> None:
        """Initialize Phase One: NFC and fingerprint verification."""
        self.logger.info("Starting Phase 1: NFC scanning and fingerprint verification")
        self.current_phase = WorkflowPhase.PHASE_ONE
        self.nfc_reader_active = True
        self.monitor_timer.start(1000)

    def _monitor_nfc_and_door(self) -> None:
        """Monitor NFC detection and door status."""
        try:
            # Check door status
            door_result = handle_door_status(self.door_status)
            if not door_result['door_open']:
                self.transition_to_phase_two()
                return

            # Monitor for NFC card
            if self.nfc_reader_active:
                if nfc_data := self.nfc.read_nfc(timeout=0.1):
                    self.handle_nfc_detection(nfc_data)

        except Exception as e:
            self.logger.exception("Error during monitoring")
            self.gui_window.show_message(f"Error: {str(e)}", MessageType.ERROR)

    def handle_nfc_detection(self, nfc_data: str) -> None:
        """Process detected NFC card with database verification."""
        if self.current_phase != WorkflowPhase.PHASE_ONE:
            return

        self.scene_manager.switch_to_scene(SceneType.WAIT)

        if hajj_id := verify_nfc_data(nfc_data, self.encryption_manager):
            try:
                hajj_records = get_hajj_records()
                if not any(record['hajj_id'] == hajj_id for record in hajj_records):
                    self.scene_manager.switch_to_scene(SceneType.CARD_FAILED)
                    self.sound_manager.play_fail()
                    QTimer.singleShot(5000, lambda: self.scene_manager.switch_to_scene(SceneType.CARD_SCAN))
                    return

                self.sound_manager.play_success()
                self.scene_manager.switch_to_scene(SceneType.FINGER_SCAN)
                QTimer.singleShot(2000, lambda: self.handle_fingerprint_verification(hajj_id))

            except Exception as e:
                logger.exception("Database verification failed")
                self.scene_manager.switch_to_scene(SceneType.CARD_FAILED)
                self.sound_manager.play_fail()
                QTimer.singleShot(5000, lambda: self.scene_manager.switch_to_scene(SceneType.CARD_SCAN))
        else:
            self.scene_manager.switch_to_scene(SceneType.CARD_FAILED)
            self.sound_manager.play_fail()
            QTimer.singleShot(5000, lambda: self.scene_manager.switch_to_scene(SceneType.CARD_SCAN))

    # In UserWorkflow class
    def handle_fingerprint_verification(self, hajj_id: str) -> None:
        """Verify fingerprint matches Hajj ID."""
        if self.current_phase != WorkflowPhase.PHASE_ONE:
            return

        try:
            hajj_records = get_hajj_records()
            stored_record = next((record for record in hajj_records
                                  if record['hajj_id'] == hajj_id), None)

            if not stored_record or not stored_record.get('fingerprint_data'):
                self.scene_manager.switch_to_scene(SceneType.ACCESS_DENIED)
                self.sound_manager.play_fail()
                self.nfc_reader_active = True
                return

            stored_location = int(stored_record['fingerprint_data'].get('location'))
            result = self.fingerprint_manager.check_specific_finger(stored_location)

            if result and result["matched"]:
                if hajj_id not in self.hajj_id_scans:
                    self.hajj_id_scans.append(hajj_id)

                # Get passenger name for welcome message
                passenger_name = stored_record.get('name', 'Passenger')

                # Update success scene with personalized message
                success_scene = self.scene_manager.scenes[SceneType.SUCCESS]
                self.sound_manager.play_success()
                if isinstance(success_scene, HajjScene):
                    success_scene.message_label.setText(f"Welcome {passenger_name}, please be seated")

                self.scene_manager.switch_to_scene(SceneType.SUCCESS)
                QTimer.singleShot(3000, lambda: self.scene_manager.switch_to_scene(SceneType.CARD_SCAN))
            else:
                self.scene_manager.switch_to_scene(SceneType.FINGER_FAILED)
                self.sound_manager.play_fail()
                QTimer.singleShot(3000, lambda: self.scene_manager.switch_to_scene(SceneType.CARD_SCAN))
                self.nfc_reader_active = True

        except Exception as e:
            logger.exception("Fingerprint verification error")
            self.scene_manager.switch_to_scene(SceneType.FINGER_FAILED)
            self.sound_manager.play_fail()
            QTimer.singleShot(3000, lambda: self.scene_manager.switch_to_scene(SceneType.CARD_SCAN))
            self.nfc_reader_active = True

    def transition_to_phase_two(self) -> None:
        """Transition from Phase One to Phase Two."""
        self.logger.info("Door closed, transitioning to Phase 2")
        self.monitor_timer.stop()
        self.current_phase = WorkflowPhase.PHASE_TWO
        self.start_phase_two()

    def start_phase_two(self) -> None:
        """Initialize Phase Two: PIN verification and trip start."""
        if self.current_phase != WorkflowPhase.PHASE_TWO:
            return
        self.logger.info("Starting Phase 2: PIN entry for trip initiation")
        self.nfc_reader_active = False
        self.scene_manager.switch_to_scene(SceneType.PIN_ENTRY)

    def proceed_with_trip(self, headcount_verified: bool):
        """Proceed with trip after headcount verification"""
        if headcount_verified:
            self.gui_window.show_message("Trip started", MessageType.SUCCESS)
        else:
            self.gui_window.show_message("Warning: Headcount mismatch", MessageType.WARNING)

    def _perform_headcount(self) -> None:
        """Perform headcount check after showing processing scene."""
        try:
            headcount_result = perform_headcount_check(
                self.camera_manager,
                len(self.hajj_id_scans)
            )

            # Show result scene
            result_scene = self.scene_manager.scenes[SceneType.HEADCOUNT_RESULT]
            if isinstance(result_scene, HeadcountResultScene):
                result_scene.set_result(
                    headcount_result['success'],
                    f"Headcount {'Verified' if headcount_result['success'] else 'Mismatch'}: "
                    f"{headcount_result['detected_count']}/{headcount_result['scanned_count']}"
                )

            self.scene_manager.switch_to_scene(SceneType.HEADCOUNT_RESULT)

            # Auto-proceed after showing result
            QTimer.singleShot(5000, lambda: self.proceed_with_trip(headcount_result['success']))

        except Exception as e:
            self.logger.exception("Error during headcount check")
            self.gui_window.show_message(f"Error during headcount check: {str(e)}", MessageType.ERROR)
            self.scene_manager.switch_to_scene(SceneType.CARD_SCAN)

    def start_trip(self) -> None:
        """Start new trip and perform headcount verification."""
        self.logger.info("Starting trip verification process")
        self.trip_start_time = datetime.datetime.now()

        # First ensure we're showing the processing scene
        if self.scene_manager.current_scene_type != SceneType.HEADCOUNT_PROCESSING:
            self.scene_manager.switch_to_scene(SceneType.HEADCOUNT_PROCESSING)

        # Use QTimer to ensure processing scene is visible before continuing
        QTimer.singleShot(1500, self._perform_headcount)

    def end_trip(self) -> None:
        """End current trip and reset for next one."""
        try:
            self.trip_end_time = datetime.datetime.now()
            trip_data = process_trip_data(
                self.trip_number,
                self.hajj_id_scans,
                self.trip_start_time or datetime.datetime.now(),
                self.trip_end_time
            )

            self.logger.log_trip(self.trip_number, trip_data)
            cleanup_hardware(self.camera_manager)

            # Show trip completion scene
            self.scene_manager.switch_to_scene(SceneType.TRIP_COMPLETE)
            current_scene = self.scene_manager.get_current_scene()
            if isinstance(current_scene, TripCompleteScene):
                current_scene.update_trip_info(trip_data)

        except Exception as e:
            self.logger.exception("Error ending trip")
            self.gui_window.show_message("Error ending trip", MessageType.ERROR)
            self.start_phase_one()

    def reset_for_new_trip(self):
        """Reset workflow state for a new trip"""
        # Reset all state variables
        self.hajj_id_scans = []
        self.trip_start_time = None
        self.trip_end_time = None
        self.trip_number += 1
        self.current_phase = WorkflowPhase.PHASE_ONE
        self.door_status = True  # Reset door status to open
        self.nfc_reader_active = True

        # Ensure we're in CARD_SCAN scene
        if hasattr(self, 'scene_manager'):
            self.scene_manager.switch_to_scene(SceneType.CARD_SCAN)

        # Start monitoring only after scene transition
        QTimer.singleShot(500, lambda: self.monitor_timer.start(1000))

    def show_message(self, message: str, message_type: MessageType):
        """Show message in GUI window"""
        if hasattr(self.gui_window, 'show_message'):
            self.gui_window.show_message(message, message_type)