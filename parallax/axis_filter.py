"""
This class is used during the reticle calibration process to handle the selection of the positive x-axis.
The system detects the reticle and requests the user to select the positive x-axis point. AxisFilter manages 
the visualization of reticle points and processing of the two points along the x-axis and y-axis, retrieving points clicked by 
the user on the screen.
"""

import logging
import time

import cv2
import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from .calibration_camera import CalibrationCamera

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class AxisFilter(QObject):
    """
    AxisFilter class is used during the reticle calibration process.

    After detecting the reticle, the system prompts the user to select the positive x-axis. AxisFilter displays 
    the detected reticle points on the x-axis and y-axis and processes user input (clicked points) for calibration.
    """

    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)

    class Worker(QObject):
        """
        Worker class for processing frames and handling user interactions in a separate thread.

        This class processes frames by displaying reticle coordinates and handles user clicks to select
        the positive x-axis point. It also performs calibration based on selected points.
        """

        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)
        found_coords = pyqtSignal(
            np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple
        )

        def __init__(self, name, model):
            """
            Initialize the worker object.

            Args:
                name (str): The name of the camera (e.g., serial number).
                model: The data model associated with the worker.
            """
            QObject.__init__(self)
            self.model = model
            self.name = name
            self.running = False
            self.new = False
            self.frame = None
            self.reticle_coords = self.model.get_coords_axis(self.name)
            self.pos_x = None
            self.calibrationCamera = CalibrationCamera(self.name)

        def update_frame(self, frame):
            """Update the frame to be processed.

            Args:
                frame: The frame to be processed.
            """
            self.frame = frame
            self.new = True

        def process(self):
            """Process the frame and emit the frame_processed signal."""
            if self.reticle_coords is not None:
                for reticle_coords in self.reticle_coords:
                    for pt in reticle_coords:
                        cv2.circle(self.frame, tuple(pt), 4, (155, 155, 50), -1)
                    first_pt = reticle_coords[0]
                    last_pt = reticle_coords[-1]
                    cv2.circle(self.frame, tuple(first_pt), 12, (255, 255, 0), -1)
                    cv2.circle(self.frame, tuple(last_pt), 12, (255, 255, 0), -1)

            pos_x = self.model.get_pos_x(self.name)
            if pos_x is not None:
                cv2.circle(self.frame, pos_x, 15, (255, 0, 0), -1)

            self.frame_processed.emit(self.frame)
            
        def squared_distance(self, p1, p2):
            """Calculate the squared distance between two points.

            Args:
                p1, p2 (tuple): Points between which the squared distance is calculated.
            """
            return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2
    
        def sort_reticle_points(self):
            """
            Sort the reticle points based on the current position of the camera.

            This method sorts the reticle points in the correct order based on the 
            selected positive x-axis point and the detected coordinates.
            """
            if self.pos_x is None or self.reticle_coords is None:
                return

            if self.pos_x == tuple(self.reticle_coords[0][0]):
                self.reticle_coords[0] = self.reticle_coords[0][::-1]
                self.reticle_coords[1] = self.reticle_coords[1][::-1]
            elif self.pos_x == tuple(self.reticle_coords[1][-1]):
                tmp = self.reticle_coords[1]
                self.reticle_coords[1] = self.reticle_coords[0][::-1]
                self.reticle_coords[0] = tmp
            elif self.pos_x == tuple(self.reticle_coords[1][0]):
                tmp = self.reticle_coords[1][::-1]
                self.reticle_coords[1] = self.reticle_coords[0]
                self.reticle_coords[0] = tmp
            else:
                pass
            
            self.pos_x = tuple(self.reticle_coords[0][-1])
            return
            
        def clicked_position(self, input_pt):
            """Get clicked position."""
            if not self.running: 
                return
            
            if self.reticle_coords is None:
                return

            logger.debug(f"clicked_position {input_pt}")
            # Coordinates of points
            pt1, pt2 = self.reticle_coords[0][0], self.reticle_coords[0][-1]
            pt3, pt4 = self.reticle_coords[1][0], self.reticle_coords[1][-1]
            pts = [pt1, pt2, pt3, pt4]
            
            # Finding the closest point to pt
            self.pos_x = min(pts, key=lambda pt: self.squared_distance(pt, input_pt))
            self.pos_x = tuple(self.pos_x)

            # sort the reticle points and register to the model
            self.sort_reticle_points()
            ret, mtx, dist, rvecs, tvecs = self.calibrationCamera.calibrate_camera(
                    self.reticle_coords[0], self.reticle_coords[1]
            )
            if ret:
                self.found_coords.emit(
                        self.reticle_coords[0], self.reticle_coords[1], mtx, dist, rvecs, tvecs
                )
            
            # Register the camera intrinsic parameters and coords  to the model
            self.model.add_coords_axis(self.name, self.reticle_coords)
            self.model.add_camera_intrinsic(self.name, mtx, dist, rvecs, tvecs)
            self.model.add_pos_x(self.name, self.pos_x)

        def reset_pos_x(self):
            """Reset the position of the x-axis (pos_x) in the model."""
            self.pos_x = None
            self.model.reset_pos_x()
            logger.debug("reset pos_x")

        def stop_running(self):
            """Stop the worker from running."""
            self.running = False

        def start_running(self):
            """Start the worker running."""
            self.running = True

        def run(self):
            """Run the worker thread."""
            while self.running:
                if self.new:
                    self.process()
                    self.new = False
                time.sleep(0.001)
            self.finished.emit()
            logger.debug(f"thread finished {self.name}")

        def set_name(self, name):
            """Set name as camera serial number."""
            self.name = name
            self.reticle_coords = self.model.get_coords_axis(self.name)
            self.pos_x = self.model.get_pos_x(self.name)

    def __init__(self, model, camera_name):
        """Initialize the filter object."""
        logger.debug("Init axis filter manager")
        super().__init__()
        self.model = model
        self.worker = None
        self.name = camera_name
        self.thread = None

    def init_thread(self):
        """Initialize or reinitialize the worker and thread"""
        if self.thread is not None:
            self.clean()  # Clean up existing thread and worker before reinitializing 
        self.thread = QThread()
        self.worker = self.Worker(self.name, self.model)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.destroyed.connect(self.onThreadDestroyed)
        self.threadDeleted = False

        #self.worker.frame_processed.connect(self.frame_processed)
        self.worker.frame_processed.connect(self.frame_processed.emit)
        self.worker.found_coords.connect(self.found_coords)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.destroyed.connect(self.onWorkerDestroyed)
        logger.debug(f"init camera name: {self.name}")

    def process(self, frame):
        """Process the frame using the worker.

        Args:
            frame: The frame to be processed.
        """
        if self.worker is not None:
            self.worker.update_frame(frame)

    def start(self):
        """Start the filter by reinitializing and starting the worker and thread."""
        logger.debug(f" {self.name} Starting thread")
        self.init_thread()  # Reinitialize and start the worker and thread
        self.worker.start_running()
        self.thread.start()

    def stop(self):
        """Stop the filter by stopping the worker."""
        logger.debug(f" {self.name} Stopping thread")
        if self.worker is not None:
            self.worker.reset_pos_x()
            self.worker.stop_running()

    def onWorkerDestroyed(self):
        """Cleanup after worker finishes."""
        logger.debug(f"{self.name} worker destroyed")

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

    def clicked_position(self, pt):
        """Get clicked position."""
        if self.worker is not None:
            self.worker.clicked_position(pt)

    def clean(self):
        """Safely clean up the reticle detection manager."""
        logger.debug(f"{self.name} Cleaning the thread")
        if self.worker is not None:
            self.worker.stop_running()  # Signal the worker to stop
        
        if not self.threadDeleted and self.thread.isRunning():
            self.thread.quit()  # Ask the thread to quit
            self.thread.wait()  # Wait for the thread to finish
        self.thread = None  # Clear the reference to the thread
        self.worker = None  # Clear the reference to the worker
        logger.debug(f"{self.name} Cleaned the thread")

    def onThreadDestroyed(self):
        """Flag if thread is deleted"""
        self.threadDeleted = True

    def __del__(self):
        """Destructor for the filter object."""
        self.clean()


