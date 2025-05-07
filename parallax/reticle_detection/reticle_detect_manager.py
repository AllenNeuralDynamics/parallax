"""
Manages reticle detection in images through a worker thread, integrating line detection,
masking, coordinate analysis, and camera calibration. Uses PyQt's signals
for thread-safe operations and real-time processing feedback.
"""

import logging
import time

import cv2
import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from parallax.cameras.calibration_camera import CalibrationCamera
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.reticle_detection.reticle_detection import ReticleDetection
from parallax.reticle_detection.reticle_detection_coords_interests import ReticleDetectCoordsInterest

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)
IMG_SIZE_ORIGINAL = (4000, 3000)


class ReticleDetectManager(QObject):
    """Reticle detection class"""

    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
    detect_failed = pyqtSignal()

    class Worker(QObject):
        """Reticle detection Worker Thread"""

        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)
        found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
        detect_failed = pyqtSignal()

        def __init__(self, name, test_mode=False):
            """Initialize the worker"""
            QObject.__init__(self)
            self.name = name
            self.test_mode = test_mode
            self.running = False
            self.frame = None
            self.found = False
            self.new = False
            self.on_process = False

            self.mask_detect = MaskGenerator(initial_detect=True)
            self.reticleDetector = ReticleDetection(
                IMG_SIZE_ORIGINAL, self.mask_detect, self.name, test_mode=self.test_mode
            )
            self.coordsInterests = ReticleDetectCoordsInterest()
            self.calibrationCamera = CalibrationCamera(self.name)

        def update_frame(self, frame):
            """Update the frame to be processed."""
            self.frame = frame
            self.new = True

        def _draw_coords(self, x_axis_coords, y_axis_coords):
            """Draw the coordinates on the frame.

            Args:
                frame (numpy.ndarray): Input frame.
                x_axis_coords (numpy.ndarray): X-axis coordinates.
                y_axis_coords (numpy.ndarray): Y-axis coordinates.

            Returns:
                numpy.ndarray: Frame with coordinates drawn.
            """
            if x_axis_coords is None or y_axis_coords is None:
                return
            for pixel in x_axis_coords:
                pt = tuple(pixel)
                cv2.circle(self.frame, pt, 9, (255, 255, 0), -1)
            for pixel in y_axis_coords:
                pt = tuple(pixel)
                cv2.circle(self.frame, pt, 9, (0, 255, 255), -1)

        def _draw_xyz(self, origin, x, y, z):
            """Draw the XYZ axes on the frame."""
            self.frame = cv2.line(self.frame, origin, x, (0, 0, 255), 3)  # Blue line
            self.frame = cv2.line(self.frame, origin, y, (0, 255, 0), 3)  # Green line
            self.frame = cv2.line(self.frame, origin, z, (255, 0, 0), 3)  # Red line

        def _draw_calibration_info(self, ret, mtx, dist):
            """
            Draw calibration information on the frame.

            Parameters:
            - frame: The image frame on which to draw.
            - ret: Boolean indicating if calibration was successful.
            - mtx: The camera matrix obtained from calibration.
            - dist: The distortion coefficients obtained from calibration.
            """

            # Starting position for the text
            offset_start = 50
            line_height = 60

            # Basic settings for the text
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.5
            font_color = (255, 255, 255)  # White color
            line_type = 2

            # Status text
            status_text = f"Overall RMS re-projection error: {ret}"
            cv2.putText(
                self.frame,
                status_text,
                (10, offset_start),
                font,
                font_scale,
                font_color,
                line_type,
            )

            # Camera matrix text
            mtx_lines = [
                "Camera Matrix:",
                f"[{mtx[0][0]:.2f}, {mtx[0][1]:.2f}, {mtx[0][2]:.2f}]",
                f"[{mtx[1][0]:.2f}, {mtx[1][1]:.2f}, {mtx[1][2]:.2f}]",
                f"[{mtx[2][0]:.2f}, {mtx[2][1]:.2f}, {mtx[2][2]:.2f}]"
            ]
            # Draw each line of the camera matrix
            for i, line in enumerate(mtx_lines):
                cv2.putText(
                    self.frame,
                    line,
                    (10, offset_start + line_height + i * line_height),
                    font,
                    font_scale,
                    font_color,
                    line_type,
                )

            # Distortion coefficients text
            dist_text = (
                f"Dist Coeffs: [{dist[0][0]:.4f}, {dist[0][1]:.4f}, {dist[0][2]:.4f}, "
                f"{dist[0][3]:.4f}, {dist[0][4]:.4f}]"
            )

            cv2.putText(
                self.frame,
                dist_text,
                (10, offset_start + line_height * 5),
                font,
                font_scale,
                font_color,
                line_type,
            )
            return

        def _draw(self):
            self._draw_xyz(self.origin, self.x, self.y, self.z)
            self._draw_coords(self.x_coords, self.y_coords)
            self._draw_calibration_info(self.success, self.mtx, self.dist)

        def process(self, frame):
            """Process the frame for reticle detection."""
            logger.debug(f"{self.name} - Starting frame processing...")

            # Step 1: Get candidate coordinates from reticle detector
            success, processed_frame, _, inliner_lines = self.reticleDetector.get_coords(frame, lambda: self.running)
            if not self.running: return -1
            if not success: return None

            # Step 2: Analyze coordinates of interest
            success, self.x_coords, self.y_coords = self.coordsInterests.get_coords_interest(inliner_lines)
            if not self.running: return -1
            if not success: return None

            # Step 3: Calibrate the camera using found points
            self.success, self.mtx, self.dist, rvecs, tvecs = self.calibrationCamera.calibrate_camera(self.x_coords, self.y_coords)
            if not self.running: return -1
            if not self.success: return None

            # Step 4: Draw results and emit data
            self.found_coords.emit(self.x_coords, self.y_coords, self.mtx, self.dist, rvecs, tvecs)

            self.origin, self.x, self.y, self.z = self.calibrationCamera.get_origin_xyz()

            self.frame = frame
            return 1

        def stop_running(self):
            """Stop the worker from running."""
            logger.debug(f"{self.name} - stop running")
            self.running = False

        def start_running(self):
            """Start the worker running."""
            self.running = True

        def run(self):
            logger.debug(f"{self.name} - Thread started")
            """Run the worker thread."""
            while self.running:
                #if self.frame is not None:
                if self.new:
                    self.new = False
                    if not self.found and not self.on_process:
                        # Detect first time
                        self.on_process = True
                        result = self.process(self.frame)
                        if result == -1:
                            logger.debug(f"{self.name} - Outside request to stop processing")
                            self.finished.emit()
                            return  # Exit early
                        if result is None:
                            logger.debug(f"{self.name} - Detection failed")
                            self.detect_failed.emit()
                            self.finished.emit()
                            return  # Exit early
                        if result == 1:
                            logger.debug(f"{self.name} - Detection success")
                            self.frame_processed.emit(self.frame)
                            self.found = True
                            self.on_process = False
                    if self.found:
                        self._draw()  # Draw axis and coordinates
                        self.frame_processed.emit(self.frame)
                time.sleep(0.01)
            logger.debug(f"{self.name} - stop running")
            self.finished.emit()

        def set_name(self, name):
            """Set name as camera serial number."""
            self.name = name

    def __init__(self, camera_name, test_mode=False):
        """Initialize the reticle detection manager."""
        logger.debug(f"{self.name} Init reticle detect manager")
        super().__init__()
        self.worker = None
        self.name = camera_name
        self.test_mode = test_mode
        self.thread = None
        self.threadDeleted = False

    def init_thread(self):
        """Initialize the worker thread."""
        self.thread = QThread()
        self.worker = self.Worker(self.name)
        self.worker.moveToThread(self.thread)

        # Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.onThreadFinished)

        self.worker.frame_processed.connect(self.frame_processed)
        self.worker.found_coords.connect(self.found_coords)
        self.worker.detect_failed.connect(self.detect_failed)

    def process(self, frame):
        """Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
        """
        if self.worker is not None:
            self.worker.update_frame(frame)

    def start(self):
        """Start the reticle detection manager."""
        logger.debug(f"{self.name} Starting thread")
        self.init_thread()  # Reinitialize and start the worker and thread
        self.worker.start_running()
        self.thread.start()

    def stop(self):
        """Stop the reticle detection manager."""
        if self.worker is not None:
            self.worker.stop_running()

        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def set_name(self, camera_name):
        """Set camera name."""
        self.name = camera_name
        if self.worker is not None:
            self.worker.set_name(self.name)
        logger.debug(f"{self.name} set camera name")

    def onThreadFinished(self):
        """Handle thread finished signal."""
        logger.debug(f"{self.name} Thread finished")
        self.thread = None
