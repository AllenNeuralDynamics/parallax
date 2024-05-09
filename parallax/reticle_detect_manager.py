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

from .calibration_camera import CalibrationCamera
from .mask_generator import MaskGenerator
from .reticle_detection import ReticleDetection
from .reticle_detection_coords_interests import ReticleDetectCoordsInterest

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.DEBUG)


class ReticleDetectManager(QObject):
    """Reticle detection class"""

    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray)

    class Worker(QObject):
        """Reticle detection Worker Thread"""

        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)
        found_coords = pyqtSignal(
            np.ndarray, np.ndarray, np.ndarray, np.ndarray
        )

        def __init__(self, name):
            """Initialize the worker"""
            QObject.__init__(self)
            self.name = name
            self.running = False
            self.is_detection_on = False
            self.new = False
            self.frame = None
            self.IMG_SIZE_ORIGINAL = (4000, 3000)  # TODO
            self.frame_success = None

            self.mask_detect = MaskGenerator(initial_detect = True)
            self.reticleDetector = ReticleDetection(
                self.IMG_SIZE_ORIGINAL, self.mask_detect, self.name
            )
            self.coordsInterests = ReticleDetectCoordsInterest()
            self.calibrationCamera = CalibrationCamera(self.name)

        def update_frame(self, frame):
            """Update the frame to be processed."""
            self.frame = frame
            # Deal with one frame at a time. This may cause the frame drop
            if self.new is False:
                self.new = True

        def draw(self, frame, x_axis_coords, y_axis_coords):
            """Draw the coordinates on the frame.

            Args:
                frame (numpy.ndarray): Input frame.
                x_axis_coords (numpy.ndarray): X-axis coordinates.
                y_axis_coords (numpy.ndarray): Y-axis coordinates.

            Returns:
                numpy.ndarray: Frame with coordinates drawn.
            """
            if x_axis_coords is None or y_axis_coords is None:
                return frame
            for pixel in x_axis_coords:
                pt = tuple(pixel)
                cv2.circle(frame, pt, 7, (255, 255, 0), -1)
            for pixel in y_axis_coords:
                pt = tuple(pixel)
                cv2.circle(frame, pt, 7, (0, 255, 255), -1)
            return frame

        def draw_xyz(self, frame, origin, x, y, z):
            """Draw the XYZ axes on the frame."""
            frame = cv2.line(frame, origin, x, (0, 0, 255), 3)  # Blue line
            frame = cv2.line(frame, origin, y, (0, 255, 0), 3)  # Green line
            frame = cv2.line(frame, origin, z, (255, 0, 0), 3)  # Red line
            return frame

        def draw_calibration_info(self, frame, ret, mtx, dist):
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
                frame,
                status_text,
                (10, offset_start),
                font,
                font_scale,
                font_color,
                line_type,
            )

            # Camera matrix text
            mtx_lines = [
                f"Camera Matrix:",
                f"[{mtx[0][0]:.2f}, {mtx[0][1]:.2f}, {mtx[0][2]:.2f}]",
                f"[{mtx[1][0]:.2f}, {mtx[1][1]:.2f}, {mtx[1][2]:.2f}]",
                f"[{mtx[2][0]:.2f}, {mtx[2][1]:.2f}, {mtx[2][2]:.2f}]"
            ]
            # Draw each line of the camera matrix
            for i, line in enumerate(mtx_lines):
                cv2.putText(
                    frame,
                    line,
                    (10, offset_start + line_height + i * line_height),
                    font,
                    font_scale,
                    font_color,
                    line_type,
                )

            # Distortion coefficients text
            dist_text = f"Dist Coeffs: [{dist[0][0]:.4f}, {dist[0][1]:.4f}, \
                {dist[0][2]:.4f}, {dist[0][3]:.4f} {dist[0][4]:.4f}]"
            cv2.putText(
                frame,
                dist_text,
                (10, offset_start + line_height * 5),
                font,
                font_scale,
                font_color,
                line_type,
            )

            return frame

        def process(self, frame):
            """Process the frame for reticle detection."""
            # cv2.circle(frame, (2000,1500), 10, (255, 0, 0), -1)
            ret, frame_, _, inliner_lines_pixels = (
                self.reticleDetector.get_coords(frame)
            )
            if not ret:
                logger.debug(f"{ self.name} get_coords fails ")
            else:
                ret, x_axis_coords, y_axis_coords = (
                    self.coordsInterests.get_coords_interest(
                        inliner_lines_pixels
                    )
                )

            if not ret:
                logger.debug(f"{ self.name} get_coords_interest fails ")
            else:
                # TODO
                # ret, mtx, dist = self.calibrationCamera.get_predefined_intrinsic(x_axis_coords, y_axis_coords)
                # if not ret:
                ret, mtx, dist = self.calibrationCamera.calibrate_camera(
                    x_axis_coords, y_axis_coords
                )
                if not ret:
                    logger.debug(f"{ self.name} calibrate_camera fails ")
                else:
                    # Draw
                    self.found_coords.emit(
                        x_axis_coords, y_axis_coords, mtx, dist
                    )
                    origin, x, y, z = self.calibrationCamera.get_origin_xyz()
                    frame = self.draw_xyz(frame, origin, x, y, z)
                    frame = self.draw(frame, x_axis_coords, y_axis_coords)
                    frame = self.draw_calibration_info(frame, ret, mtx, dist)
                self.frame_success = frame
            
            if self.frame_success is None:
                logger.debug(f"{ self.name} reticle detection fail ")
                return frame
            else:
                logger.debug(f"{ self.name} reticle detection success \n")
                self.stop_running() # If found, stop processing
                return self.frame_success

        def stop_running(self):
            """Stop the worker from running."""
            self.running = False

        def start_running(self):
            """Start the worker running."""
            self.running = True

        def start_detection(self):
            """Start the reticle detection."""
            self.is_detection_on = True

        def stop_detection(self):
            """Stop the reticle detection."""
            self.is_detection_on = False

        def run(self):
            """Run the worker thread."""
            while self.running:
                if self.new:
                    self.frame = self.process(self.frame)
                    self.frame_processed.emit(self.frame)
                self.new = False
                time.sleep(0.001)
            self.finished.emit()

        def set_name(self, name):
            """Set name as camera serial number."""
            self.name = name

    def __init__(self, camera_name):
        """Initialize the reticle detection manager."""
        logger.debug(f"{self.name} Init reticle detect manager")
        super().__init__()
        self.worker = None
        self.name = camera_name
        self.thread = None

    def init_thread(self):
        """Initialize the worker thread."""
        if self.thread is not None:
            self.clean()  # Clean up existing thread and worker before reinitializing
        self.thread = QThread()
        self.worker = self.Worker(self.name)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.destroyed.connect(self.onThreadDestroyed) # Debug msg
        self.threadDeleted = False

        self.worker.frame_processed.connect(self.frame_processed)
        self.worker.found_coords.connect(self.found_coords)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.destroyed.connect(self.onWorkerDestroyed)
        logger.debug(f"{self.name} init camera")

    def process(self, frame):
        """Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
        """
        if self.worker is not None:
            self.worker.update_frame(frame)

    def start(self):
        """Start the reticle detection manager."""
        logger.debug(f"{self.name} Starting thread in {self.__class__.__name__}")
        self.init_thread()  # Reinitialize and start the worker and thread
        self.worker.start_running()
        self.thread.start()

    def stop(self):
        """Stop the reticle detection manager."""
        if self.worker is not None:
            self.worker.stop_running()
        
    def onWorkerDestroyed(self):
        """Cleanup after worker finishes."""
        logger.debug(f"{self.name} worker finished")

    def onThreadDestroyed(self):
        """Flag if thread is deleted"""
        logger.debug(f"{self.name} thread destroyed")
        self.threadDeleted = True
        self.thread = None

    def set_name(self, camera_name):
        """Set camera name."""
        self.name = camera_name
        if self.worker is not None:
            self.worker.set_name(self.name)
        logger.debug(f"{self.name} set camera name")

    def clean(self):
        """Safely clean up the reticle detection manager."""
        logger.debug(f"{self.name} Cleaning the thread")
        if self.worker is not None:
            self.worker.stop_running()  # Signal the worker to stop
        
        if not self.threadDeleted and self.thread.isRunning():
            logger.debug(f"{self.name} Stopping thread in {self.__class__.__name__}")
            self.thread.quit()  # Ask the thread to quit
            self.thread.wait()  # Wait for the thread to finish
        self.thread = None  # Clear the reference to the thread
        self.worker = None  # Clear the reference to the worker
        logger.debug(f"{self.name} Cleaned the thread")

    def onThreadDestroyed(self):
        """Flag if thread is deleted"""
        self.threadDeleted = True

    def __del__(self):
        """Destructor for the reticle detection manager."""
        self.clean()