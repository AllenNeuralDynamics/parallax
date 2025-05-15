from PyQt5.QtCore import QObject, pyqtSignal, QThread
import time
import numpy as np
import cv2
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class BaseReticleWorker(QObject):
    finished = pyqtSignal()
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
    detect_failed = pyqtSignal()

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.running = False
        self.new = False
        self.found = False
        self.frame = None

        # Drawing variables
        self.origin = None
        self.x = None
        self.y = None
        self.z = None
        self.x_coords = None
        self.y_coords = None

    def update_frame(self, frame):
        self.frame = frame
        self.new = True

    def run(self):
        while self.running:
            if self.new:
                if not self.found:
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

                if self.found:
                    self._draw()
                    self.frame_processed.emit(self.frame)

                self.new = False

            time.sleep(0.01)
        self.finished.emit()

    def start_running(self):
        self.running = True

    def stop_running(self):
        self.running = False

    def process(self, frame):
        raise NotImplementedError("Subclasses must implement this method.")

    def _draw(self):
        if self.origin and self.x and self.y and self.z:
            self._draw_xyz(self.origin, self.x, self.y, self.z)
        if self.x_coords is not None and self.y_coords is not None:
            self._draw_coords(self.x_coords, self.y_coords)

    def _draw_coords(self, x_axis_coords, y_axis_coords):
        """Draw the coordinates on the frame.

        Args:
            frame (numpy.ndarray): Input frame.
            x_axis_coords (numpy.ndarray): X-axis coordinates.
            y_axis_coords (numpy.ndarray): Y-axis coordinates.

        Returns:
            numpy.ndarray: Frame with coordinates drawn.
        """
        """Draw axis points on the frame."""
        for pixel in x_axis_coords:
            cv2.circle(self.frame, tuple(pixel), 9, (255, 255, 0), -1)
        for pixel in y_axis_coords:
            cv2.circle(self.frame, tuple(pixel), 9, (0, 255, 255), -1)

    def _draw_xyz(self, origin, x, y, z):
        """Draw the XYZ axes on the frame."""
        self.frame = cv2.line(self.frame, origin, x, (255, 0, 0), 3)  # Red line
        self.frame = cv2.line(self.frame, origin, y, (0, 255, 0), 3)  # Green line
        self.frame = cv2.line(self.frame, origin, z, (0, 0, 255), 3)  # Blue line

    def set_name(self, name):
        """Set name as camera serial number."""
        self.name = name

class BaseReticleManager(QObject):
    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
    detect_failed = pyqtSignal()

    def __init__(self, name, WorkerClass):
        super().__init__()
        self.name = name
        self.WorkerClass = WorkerClass
        self.thread = None
        self.worker = None

    def init_thread(self):
        self.thread = QThread()
        self.worker = self.WorkerClass(self.name)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.onThreadFinished)

        self.worker.frame_processed.connect(self.frame_processed)
        self.worker.found_coords.connect(self.found_coords)
        self.worker.detect_failed.connect(self.detect_failed)

    def process(self, frame):
        if self.worker:
            self.worker.update_frame(frame)

    def start(self):
        logger.debug(f"{self.name} Starting thread")
        self.init_thread()
        self.worker.start_running()
        self.thread.start()

    def stop(self):
        logger.debug(f"{self.name} Stopping thread")
        if self.worker:
            self.worker.stop_running()
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def onThreadFinished(self):
        """Handle thread finished signal."""
        logger.debug(f"{self.name} Thread finished")
        self.thread = None

    def set_name(self, camera_name):
        """Set camera name."""
        self.name = camera_name
        if self.worker is not None:
            self.worker.set_name(self.name)

