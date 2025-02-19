# camera_manager.py

import cv2
import time
import logging
from typing import Tuple, Optional
from ultralytics import YOLO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(
            self,
            camera_id: int = 0,
            confidence: float = 0.5,
            model_path: str = 'yolov8n.pt',
            frame_width: int = 640,
            frame_height: int = 480
    ) -> None:
        """
        Initialize the camera and YOLO model.

        :param camera_id: Camera device ID (default: 0)
        :param confidence: Detection confidence threshold (default: 0.5)
        :param model_path: Path to the YOLO model (default: 'yolov8n.pt')
        :param frame_width: Width of the camera frame (default: 640)
        :param frame_height: Height of the camera frame (default: 480)
        """
        self.camera_id = camera_id
        self.confidence = confidence
        self.model = YOLO(model_path)  # Load YOLOv8 model

        # Initialize camera
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise ValueError(f"Failed to open camera {camera_id}")

        # Set camera resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)

    def capture_frame(self) -> Optional[any]:
        """
        Capture a single frame from the camera.

        :return: The captured frame, or None if capture fails.
        """
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to capture frame from camera.")
            return None
        return frame

    def detect_people(self, frame) -> Tuple[any, int]:
        """
        Run YOLO inference on the frame to detect people (class 0 in the COCO dataset).

        :param frame: Input image frame.
        :return: A tuple containing the annotated frame and the count of detected people.
        """
        try:
            results = self.model(frame, verbose=False)[0]
            # Count people with confidence above the threshold
            person_count = sum(
                1 for box in results.boxes if box.cls == 0 and box.conf >= self.confidence
            )
            annotated_frame = results.plot()
            return annotated_frame, person_count
        except Exception as e:
            logger.error(f"Error during detection: {e}")
            return frame, 0

    def capture_and_count_heads(self) -> int:
        """
        Capture a frame and detect people in it.

        Optionally saves an annotated frame for debugging if any people are detected.

        :return: The number of detected people.
        """
        frame = self.capture_frame()
        if frame is None:
            return 0

        annotated_frame, person_count = self.detect_people(frame)

        # Save the annotated frame for debugging if people are detected
        if person_count > 0:
            cv2.imwrite('last_detection.jpg', annotated_frame)

        return person_count

    def get_three_counts(self, delay: float = 0.5) -> Tuple[int, int, int]:
        """
        Capture three frames with delays to obtain more reliable counts.

        :param delay: Delay between captures in seconds (default: 0.5)
        :return: A tuple of three counts.
        """
        counts = []
        for _ in range(3):
            count = self.capture_and_count_heads()
            counts.append(count)
            time.sleep(delay)
        return tuple(counts)

    def test_camera(self) -> None:
        """
        Test function to verify camera input and detection.

        Displays a live feed with detections until 'q' is pressed.
        """
        try:
            while True:
                frame = self.capture_frame()
                if frame is None:
                    break

                annotated_frame, person_count = self.detect_people(frame)

                # Draw the number of detected people on the frame
                cv2.putText(
                    annotated_frame,
                    f'People: {person_count}',
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )

                cv2.imshow('Head Detection Test', annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except KeyboardInterrupt:
            logger.info("Test interrupted by user.")
        finally:
            cv2.destroyAllWindows()

    def release(self) -> None:
        """
        Release the camera resource.
        """
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    def __del__(self):
        """
        Cleanup: Ensure the camera is released when the object is destroyed.
        """
        self.release()


if __name__ == '__main__':
    camera_manager = CameraManager()
    try:
        camera_manager.test_camera()
    finally:
        camera_manager.release()
