"""
NoFilter serves as a pass-through component in a frame processing pipeline, 
employing a worker-thread model to asynchronously handle frames without modification, 
facilitating integration and optional processing steps.
"""

import logging
import time

import cv2
from PyQt5.QtCore import QObject, QThread, pyqtSignal

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class NoFilter(QObject):
    """Class representing no filter."""

    name = "None"
    frame_processed = pyqtSignal(object)

    class Worker(QObject):
        """Worker class for processing frames in a separate thread."""

        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)

        def __init__(self, name):
            """Initialize the worker object."""
            QObject.__init__(self)
            self.name = name
            self.running = True
            self.new = False
            self.frame = None

        def update_frame(self, frame):
            """Update the frame to be processed.

            Args:
                frame: The frame to be processed.
            """
            self.frame = frame
            self.new = True

        def process(self, frame):
            """Process nothing (no filter) and emit the frame_processed signal.

            Args:
                frame: The frame to be processed.
            """
            self.frame_processed.emit(frame)

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
                    self.process(self.frame)
                    self.new = False
                time.sleep(0.001)
            self.finished.emit()

        def set_name(self, name):
            """Set name as camera serial number."""
            self.name = name

    def __init__(self, camera_name):
        """Initialize the filter object."""
        logger.debug(f"{self.name} Init no filter manager")
        super().__init__()
        self.worker = None
        self.name = camera_name
        self.thread = None
        self.start()

    def init_thread(self):
        """Initialize or reinitialize the worker and thread"""
        if self.thread is not None:
            self.clean()  # Clean up existing thread and worker before reinitializing 
        self.thread = QThread()
        self.worker = self.Worker(self.name)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.destroyed.connect(self.onThreadDestroyed)
        self.threadDeleted = False

        self.worker.frame_processed.connect(self.frame_processed.emit)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.destroyed.connect(self.onWorkerDestroyed) # Debug msg
        logger.debug(f"{self.name} init camera name")

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
        self.thread.start()
        self.worker.start_running()

    def stop(self):
        """Stop the filter by stopping the worker."""
        logger.debug(f" {self.name} Stopping thread")
        if self.worker is not None:
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

    def __del__(self):
        """Destructor for the filter object."""
        self.clean()