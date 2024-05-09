"""
NoFilter serves as a pass-through component in a frame processing pipeline, 
employing a worker-thread model to asynchronously handle frames without modification, 
facilitating integration and optional processing steps.
"""

import logging
import time

import cv2
import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class AxisFilter(QObject):
    """Class representing no filter."""

    name = "None"
    frame_processed = pyqtSignal(object)

    class Worker(QObject):
        """Worker class for processing frames in a separate thread."""

        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)

        def __init__(self, name, model):
            """Initialize the worker object."""
            QObject.__init__(self)
            self.model = model
            self.name = name
            self.running = False
            self.new = False
            self.frame = None
            self.reticle_coords = self.model.get_coords_axis(self.name)
            self.pos_x = None

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
            return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2
    
        def sort_reticle_points(self):
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
            if self.reticle_coords is None:
                return

            # Coordinates of points
            pt1, pt2 = self.reticle_coords[0][0], self.reticle_coords[0][-1]
            pt3, pt4 = self.reticle_coords[1][0], self.reticle_coords[1][-1]
            pts = [pt1, pt2, pt3, pt4]
            
            # Finding the closest point to pt
            self.pos_x = min(pts, key=lambda pt: self.squared_distance(pt, input_pt))
            self.pos_x = tuple(self.pos_x)

            # sort the reticle points and register to the model
            self.sort_reticle_points()
            self.model.add_coords_axis(self.name, self.reticle_coords)
            self.model.add_pos_x(self.name, self.pos_x)

        def reset_pos_x(self):
            self.pos_x = None
            self.model.reset_pos_x()

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
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.destroyed.connect(self.onThreadDestroyed)
        self.threadDeleted = False

        #self.worker.frame_processed.connect(self.frame_processed)
        self.worker.frame_processed.connect(self.frame_processed.emit)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.thread.deleteLater)
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
            self.worker.stop_running()
            self.worker.reset_pos_x()

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


