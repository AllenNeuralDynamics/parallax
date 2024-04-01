"""
Manages reticle detection in images through a worker thread, integrating line detection, 
masking, coordinate analysis, and camera calibration. Uses PyQt's signals 
for thread-safe operations and real-time processing feedback.
"""
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from .reticle_detection import ReticleDetection
from .mask_generator import MaskGenerator
from .reticle_detection_coords_interests import ReticleDetectCoordsInterest
from .calibration_camera import CalibrationCamera
import cv2
import numpy as np
import time
import logging

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
        """ Reticle detection Worker Thread """
        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)
        found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray) 

        def __init__(self, name):
            """Initialize the worker"""
            QObject.__init__(self)
            self.name = name
            self.running = False
            self.is_detection_on = False
            self.new = False
            self.frame = None
            self.IMG_SIZE_ORIGINAL = (4000, 3000) # TODO
            self.frame_success = None

            self.mask_detect = MaskGenerator()
            self.reticleDetector = ReticleDetection(self.IMG_SIZE_ORIGINAL, self.mask_detect)
            self.coordsInterests = ReticleDetectCoordsInterest()
            self.calibrationCamera = CalibrationCamera()
                
        def update_frame(self, frame):
            """Update the frame to be processed."""
            self.frame = frame
            if self.new is False: # Deal with one frame at a time. This may cause the frame drop
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
        
        def process(self, frame):
            """Process the frame for reticle detection."""
            #cv2.circle(frame, (2000,1500), 10, (255, 0, 0), -1)
            ret, frame_, _, inliner_lines_pixels = self.reticleDetector.get_coords(frame)
            if ret:
                ret, x_axis_coords, y_axis_coords = self.coordsInterests.get_coords_interest(inliner_lines_pixels)
            if ret:
                # Draw
                ret, mtx, dist = self.calibrationCamera.calibrate_camera(x_axis_coords, y_axis_coords)
                if ret:
                    self.found_coords.emit(x_axis_coords, y_axis_coords, mtx, dist)
                    origin, x, y, z = self.calibrationCamera.get_origin_xyz()
                    frame = self.draw_xyz(frame, origin, x, y, z)
                    frame = self.draw(frame, x_axis_coords, y_axis_coords)
                self.frame_success = frame
            if self.frame_success is None:
                return frame
            else: 
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
                time.sleep(0.001)
                self.new = False
            self.finished.emit()

    def __init__(self):
        """Initialize the reticle detection manager."""
        logger.debug("Init reticle detect manager")
        super().__init__()
        self.worker = None
        self.thread = None
        self.init_thread()
    
    def init_thread(self):
        """Initialize the worker thread."""
        #if self.thread is not None:
        #    self.clean()  # Clean up existing thread and worker before reinitializing
        self.thread = QThread()
        self.worker = self.Worker(self.name)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.frame_processed.connect(self.frame_processed)
        self.worker.found_coords.connect(self.found_coords) 
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

    def process(self, frame):
        """Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
        """
        if self.worker is not None:
            self.worker.update_frame(frame)
    
    def start(self):
        """Start the reticle detection manager."""
        self.init_thread()  # Reinitialize and start the worker and thread
        self.worker.start_running()
        self.thread.start()
    
    def stop(self):
        """Stop the reticle detection manager."""
        if self.worker is not None:
            self.worker.stop_running()

    def clean(self):
        """Clean up the reticle detection manager."""
        if self.worker is not None:
            self.worker.stop_running()
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def __del__(self):
        """Destructor for the reticle detection manager."""
        self.clean()