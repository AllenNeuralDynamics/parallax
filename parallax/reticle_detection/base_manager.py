"""Base manager for reticle detection workers."""
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable, pyqtSlot
from parallax.config.config_path import debug_img_dir
import time
import numpy as np
import cv2
import logging
import math
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class DrawWorkerSignal(QObject):
    """Signals for the DrawWorker."""
    finished = pyqtSignal()
    frame_processed = pyqtSignal(object)


class BaseDrawWorker(QRunnable):
    """Base worker for drawing reticle detection results on frames."""
    def __init__(self, name):
        """Initialize the worker with a name."""
        super().__init__()
        self.signals = (DrawWorkerSignal())
        self.name = name
        self.running = False
        self.new = False
        self.state = None  # "Found", "InProcess", "Failed"
        self.frame = None
        self.draw_flag = True

        # Drawing variables
        self.origin, self.x, self.y, self.z = None, None, None, None
        self.x_coords, self.y_coords = None, None

    def update_frame(self, frame):
        """Update the frame to be processed."""
        self.frame = frame
        self.new = True

    @pyqtSlot()
    def run(self):
        """Run the worker to draw results on the frame."""
        while self.running:
            if self.new:
                if self.state == "Found":
                    self._draw_result()
                    self._save_debug_image()
                elif self.state == "InProcess":
                    self._draw_progress()
                elif self.state == "Failed":
                    self._draw_failed()
                elif self.state == "Stopping":
                    self._draw_progress(color=(255, 0, 0), text="Waiting to stop")
                self.signals.frame_processed.emit(self.frame)
                self.new = False
            time.sleep(0.01)
        self.signals.finished.emit()

    def start_running(self):
        """Start the worker to process frames."""
        self.running = True

    def stop_running(self):
        """Stop the worker from processing frames."""
        self.running = False

    def _draw_failed(self):
        """Draw a sad emoji face with text indicating detection failure."""
        # Draw text
        text = "Detection       Failed"
        font = cv2.FONT_HERSHEY_PLAIN
        font_scale = 10
        color = (0, 0, 255)  # Red
        thickness = 5
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (self.frame.shape[1] - text_size[0]) // 2 - 130
        text_y = (self.frame.shape[0] + text_size[1]) // 2
        cv2.putText(self.frame, text, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)

        # Emoji face center and size
        center = (self.frame.shape[1] // 2, self.frame.shape[0] // 2)
        face_radius = 200
        face_color = (255, 255, 0)  # Yellow face

        # Draw face
        cv2.circle(self.frame, center, face_radius, face_color, -1)

        # Draw eyes
        eye_radius = 20
        eye_offset_x = 60
        eye_offset_y = 50
        eye_color = (0, 0, 0)  # Black eyes
        left_eye = (center[0] - eye_offset_x, center[1] - eye_offset_y)
        right_eye = (center[0] + eye_offset_x, center[1] - eye_offset_y)
        cv2.circle(self.frame, left_eye, eye_radius, eye_color, -1)
        cv2.circle(self.frame, right_eye, eye_radius, eye_color, -1)

        # Draw sad mouth
        mouth_center = (center[0], center[1] + 70)
        mouth_axes = (80, 40)
        cv2.ellipse(self.frame, mouth_center, mouth_axes, 0, 0, 180, (0, 0, 0), 5)

        # Animate tears
        tear_color = (0, 0, 255)  # Blue tears
        tear_length = 30
        time_offset = int((time.time() * 10) % 30)  # Animate by moving tears down
        tear1 = (left_eye[0], left_eye[1] + eye_radius + time_offset)
        tear2 = (right_eye[0], right_eye[1] + eye_radius + time_offset)
        cv2.line(self.frame, (tear1[0], tear1[1]), (tear1[0], tear1[1] + tear_length), tear_color, 5)
        cv2.line(self.frame, (tear2[0], tear2[1]), (tear2[0], tear2[1] + tear_length), tear_color, 5)

    def _save_debug_image(self):
        """Save the current frame as a debug image if in DEBUG mode."""
        if self.draw_flag is False:
            return
        if logger.getEffectiveLevel() != logging.DEBUG:
            return
        self.draw_flag = False
        # Save the image with a unique name
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        debug_image_path = f"{debug_img_dir}/{self.name}_{timestamp}.jpg"
        # Change RGB to BGR
        if self.frame.shape[2] == 3:
            self.frame = cv2.cvtColor(self.frame, cv2.COLOR_RGB2BGR)
        # Save the image
        cv2.imwrite(debug_image_path, self.frame)

    def _draw_result(self):
        """Draw the detected reticle coordinates and axes on the frame."""
        if self.origin and self.x and self.y and self.z:
            self._draw_xyz(self.origin, self.x, self.y, self.z)
        if self.x_coords is not None and self.y_coords is not None:
            self._draw_coords(self.x_coords, self.y_coords)

    def _draw_coords(self, x_axis_coords, y_axis_coords):
        """Draw axis points on the frame."""
        size = 2 if logger.getEffectiveLevel() == logging.DEBUG else 7
        for pixel in x_axis_coords:
            cv2.circle(self.frame, tuple(pixel), size, (255, 255, 0), -1)
        for pixel in y_axis_coords:
            cv2.circle(self.frame, tuple(pixel), size, (0, 255, 255), -1)

    def _draw_xyz(self, origin, x, y, z):
        """Draw the XYZ axes on the frame."""
        size = 1 if logger.getEffectiveLevel() == logging.DEBUG else 3
        self.frame = cv2.line(self.frame, origin, x, (255, 0, 0), size)  # Red line
        self.frame = cv2.line(self.frame, origin, y, (0, 255, 0), size)  # Green line
        self.frame = cv2.line(self.frame, origin, z, (0, 0, 255), size)  # Blue line

    def set_name(self, name):
        """Set name as camera serial number."""
        self.name = name

    def _draw_progress(self, color=(255, 255, 0), text=None):
        """Draw circling effect in the center of the frame."""
        if self.frame is None:
            return
        center_x = self.frame.shape[1] // 2
        center_y = self.frame.shape[0] // 2
        center = (center_x, center_y)
        radius = 200
        dot_radius = 40

        current_time = time.time()
        angle = (current_time * 2 * math.pi * 0.4) % (2 * math.pi)
        dot_x = int(center_x + radius * math.cos(angle))
        dot_y = int(center_y + radius * math.sin(angle))
        cv2.circle(self.frame, center, radius, (100, 100, 100), 10)
        cv2.circle(self.frame, (dot_x, dot_y), dot_radius, color, -1)

        if text is not None:
            font = cv2.FONT_HERSHEY_PLAIN
            font_scale = 5
            color = (0, 0, 255)  # Red
            thickness = 3
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_x = (self.frame.shape[1] - text_size[0]) // 2
            text_y = (self.frame.shape[0] + text_size[1]) // 2 + 250
            cv2.putText(self.frame, text, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)


class ProcessWorkerSignal(QObject):
    """Signals for the ProcessWorker."""
    finished = pyqtSignal()
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
    state = pyqtSignal(str)  # "Found", "Failed", "Stopped", "InProcess"


class BaseProcessWorker(QRunnable):
    """Base worker for processing frames to detect reticle coordinates."""
    def __init__(self, name):
        """Initialize the worker with a name."""
        super().__init__()
        self.signals = (ProcessWorkerSignal())
        self.name = name
        self.frame = None
        self.running = False

        # Drawing variables
        self.origin, self.x, self.y, self.z = None, None, None, None
        self.x_coords, self.y_coords = None, None

    @pyqtSlot()
    def run(self):
        """Run the worker to process frames for reticle detection."""
        while self.running:
            if self.frame is None:
                time.sleep(0.01)
                continue
            self.signals.state.emit("InProcess")
            result = self.process(self.frame)
            if result == -1:
                logger.debug(f"{self.name} - Outside request to stop processing")
                self.signals.state.emit("Stopped")
            if result is None:
                logger.debug(f"{self.name} - Detection failed")
                self.signals.state.emit("Failed")
            if result == 1:
                logger.debug(f"{self.name} - Detection success")
                self.signals.state.emit("Found")

            self.signals.finished.emit()
            return
        self.signals.finished.emit()
        return

    def process(self, frame):
        """Process the frame to detect reticle coordinates.
        Args:
            frame (np.ndarray): The frame to process."""
        raise NotImplementedError("Subclasses must implement this method.")

    def update_frame(self, frame):
        """Update the frame to be processed."""
        self.frame = frame

    def set_name(self, name):
        """Set name as camera serial number."""
        self.name = name

    def start_running(self):
        """Start the worker to process frames."""
        self.running = True

    def stop_running(self):
        """Stop the worker from processing frames."""
        self.running = False


class BaseReticleManager(QObject):
    """Base manager for reticle detection workers."""
    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
    finished = pyqtSignal()

    def __init__(self, name, WorkerClass, ProcessWorkerClass):
        """Initialize the reticle manager with worker classes and a name."""
        super().__init__()
        self.name = name
        self.WorkerClass = WorkerClass
        self.worker = None
        self.processWorkerClass = ProcessWorkerClass
        self.processWorker = None
        self.threadpool = QThreadPool()

    def _init_draw_thread(self):
        """Initialize the draw worker thread."""
        self.worker = self.WorkerClass(self.name)
        self.worker.signals.finished.connect(self._onDrawThreadFinished)
        self.worker.signals.frame_processed.connect(self.frame_processed)

    def _init_process_thread(self):
        """Initialize the process worker thread."""
        self.processWorker = self.processWorkerClass(self.name)
        self.processWorker.signals.finished.connect(self._onProcessThreadFinished)
        self.processWorker.signals.found_coords.connect(self.found_coords)
        self.processWorker.signals.state.connect(self._state)

    def process(self, frame):
        """Process the frame to detect reticle coordinates."""
        if self.worker:
            self.worker.update_frame(frame)
        if self.processWorker:
            self.processWorker.update_frame(frame)

    def start(self):
        """Start the reticle detection threads."""
        if self.worker is not None or self.processWorker is not None:
            print(f"{self.name} Previous thread not cleaned up")
            return

        logger.debug(f"{self.name} Starting thread")
        self._init_draw_thread()
        self.worker.start_running()
        self.threadpool.start(self.worker)

        self._init_process_thread()
        self.processWorker.start_running()
        self.threadpool.start(self.processWorker)

    def stop(self):
        """Stop the reticle detection threads."""
        logger.debug(f"{self.name} Stopping thread")
        if self.worker is None and self.processWorker is None:  # State: Stopped
            return

        if self.worker and self.processWorker is None:  # State: Found, Failed
            self._state("Stopped")  # Stop the draw worker. processWoker is already stopped

        # State: InProgress
        self._state("Stopping")  # Both Draw and Process worker were in progres. DrawWorker draw progress.
        if self.processWorker:
            self.processWorker.stop_running()  # Stop the processWorker. After finishing, stop the DrawWorker

    def _onDrawThreadFinished(self):
        """Handle thread finished signal."""
        self.worker = None
        if self.processWorker is None:
            self.finished.emit()

    def _onProcessThreadFinished(self):
        """Handle thread finished signal."""
        self.processWorker = None

    def set_name(self, camera_name):
        """Set camera name."""
        self.name = camera_name
        if self.worker is not None:
            self.worker.set_name(self.name)
        if self.processWorker is not None:
            self.processWorker.set_name(self.name)

    def _state(self, state):
        """Update the state of the worker based on the given state."""
        if self.worker is None:
            return

        if state == "InProcess":
            self.worker.state = "InProcess"
        elif state == "Found":
            # Drawing variables
            self.worker.origin = self.processWorker.origin
            self.worker.x = self.processWorker.x
            self.worker.y = self.processWorker.y
            self.worker.z = self.processWorker.z
            self.worker.x_coords = self.processWorker.x_coords
            self.worker.y_coords = self.processWorker.y_coords
            self.worker.state = "Found"
        elif state == "Failed":
            self.worker.state = "Failed"
        elif state == "Stopping":
            self.worker.state = "Stopping"
        elif state == "Stopped":
            self.worker.stop_running()
