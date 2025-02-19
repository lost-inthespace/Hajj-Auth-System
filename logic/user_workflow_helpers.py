# user_workflow_helpers.py

import datetime
import cv2
import logging
from typing import Dict, Any, List, Optional

from db.hajj_db import get_hajj_records

logger = logging.getLogger(__name__)

def verify_nfc_data(nfc_data: str, encryption_manager: Any) -> Optional[str]:
    """
    Verify and decrypt NFC card data.
    Returns decrypted Hajj ID if successful, None otherwise.
    """
    try:
        logger.info("Verifying NFC card data...")
        hajj_id = (encryption_manager.decrypt_data(nfc_data)
                  if encryption_manager else nfc_data)
        logger.info(f"Decrypted Hajj ID: {hajj_id}")
        return hajj_id
    except Exception as e:
        logger.exception("NFC verification failed")
        return None


def verify_fingerprint(fingerprint_manager: Any, hajj_id: str) -> bool:
    """
    Verify fingerprint matches the provided Hajj ID.
    Returns True if verified with sufficient confidence, False otherwise.
    """
    min_confidence = 50  # Minimum confidence threshold

    try:
        found, fp_id, confidence = fingerprint_manager.search_fingerprint()
        logger.info(f"Fingerprint scan result: Found={found}, Confidence={confidence}")

        if found and fp_id is not None and confidence >= min_confidence:
            for record in get_hajj_records():
                if (record.get('fingerprint_data') and
                        record['fingerprint_data'].get('location') == str(fp_id) and
                        record['hajj_id'] == hajj_id):
                    return True

        if found and confidence < min_confidence:
            logger.warning(f"Fingerprint match found but confidence too low: {confidence}")

        return False

    except Exception as e:
        logger.exception("Fingerprint verification failed")
        return False

def perform_headcount_check(camera_manager: Any, scanned_count: int) -> Dict[str, Any]:
    """
    Perform headcount verification using camera.
    Returns result dictionary with success status and message.
    """
    logger.info("Starting headcount verification")
    result = {
        'success': False,
        'message': '',
        'scanned_count': scanned_count,
        'detected_count': 0
    }

    if not camera_manager:
        result['message'] = "No camera manager available"
        return result

    try:
        counts = camera_manager.get_three_counts()
        head_count = max(counts)
        result['detected_count'] = head_count

        if head_count == scanned_count:
            result['success'] = True
            result['message'] = "Headcount verified"
        else:
            result['message'] = (
                f"Headcount mismatch! Detected: {head_count}, "
                f"Scanned: {scanned_count}"
            )
    except Exception as e:
        result['message'] = f"Error during headcount check: {str(e)}"
        logger.exception("Headcount check failed")

    return result

def handle_door_status(door_status: bool) -> Dict[str, bool]:
    """
    Check door status and determine if workflow should continue.
    Returns dictionary with door status information.
    """
    return {
        'door_open': door_status,
        'should_continue': door_status
    }

def process_trip_data(
    trip_number: int,
    hajj_ids: List[str],
    start_time: datetime.datetime,
    end_time: datetime.datetime
) -> Dict[str, Any]:
    """
    Process and format trip data for logging.
    Returns formatted trip data dictionary.
    """
    duration = end_time - start_time
    return {
        "trip_number": trip_number,
        "hajj_ids": hajj_ids,
        "passenger_count": len(hajj_ids),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration.total_seconds(),
    }

def cleanup_hardware(camera_manager: Any) -> None:
    """
    Clean up hardware resources after trip completion.
    """
    try:
        if (camera_manager and hasattr(camera_manager, 'cap') and
            camera_manager.cap.isOpened()):
            camera_manager.cap.release()
        cv2.destroyAllWindows()
    except Exception as e:
        logger.exception("Error during hardware cleanup")