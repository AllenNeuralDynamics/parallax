from PyQt5.QtCore import QObject, pyqtSignal, QThread, QThreadPool, QRunnable, pyqtSlot
import time
import numpy as np
import cv2
import logging
import math
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class BaseDrawWorker(QObject):
    finished = pyqtSignal()
    frame_processed = pyqtSignal(object)

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.running = False
        self.new = False
        self.found = False
        self.frame = None

        # Drawing variables
        self.origin, self.x, self.y, self.z = None, None, None, None
        self.x_coords, self.y_coords = None, None

    def update_frame(self, frame):
        self.frame = frame
        self.new = True

    @pyqtSlot()
    def run(self):
        while self.running:
            if self.new:                
                if self.found:
                    self._draw_result()
                    self.frame_processed.emit(self.frame)
                else:
                    self._draw_progress()
                    self.frame_processed.emit(self.frame)
                self.new = False
            time.sleep(0.01)
        self.finished.emit()

    def start_running(self):
        self.running = True

    def stop_running(self):
        self.running = False

    def _draw_result(self):
        if self.origin and self.x and self.y and self.z:
            self._draw_xyz(self.origin, self.x, self.y, self.z)
        if self.x_coords is not None and self.y_coords is not None:
            self._draw_coords(self.x_coords, self.y_coords)

    def _draw_coords(self, x_axis_coords, y_axis_coords):
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

    def _draw_progress(self):
        """Draw circling effect in the center of the frame."""
        if self.frame is None:
            return
        center_x = self.frame.shape[1] // 2
        center_y = self.frame.shape[0] // 2
        center = (center_x, center_y)
        radius = 200
        dot_radius = 40
        color = (255, 255, 0)

        current_time = time.time()
        angle = (current_time * 2 * math.pi * 0.4) % (2 * math.pi)
        dot_x = int(center_x + radius * math.cos(angle))
        dot_y = int(center_y + radius * math.sin(angle))
        cv2.circle(self.frame, center, radius, (100, 100, 100), 10)
        cv2.circle(self.frame, (dot_x, dot_y), dot_radius, color, -1)

class ProcessWorkerSignal(QObject):
    detect_failed = pyqtSignal()
    finished = pyqtSignal()
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
    found = pyqtSignal()

class BaseProcessWorker(QRunnable):
    def __init__(self, name):
        super().__init__()
        self.signals = (ProcessWorkerSignal())
        self.name = name
        self.frame = None
        self.running = False

        # Drawing variables
        self.origin = None
        self.x = None
        self.y = None
        self.z = None
        self.x_coords = None
        self.y_coords = None

    @pyqtSlot()
    def run(self):
        while self.running:
            if self.frame is None:
                time.sleep(0.01)
                continue
            result = self.process(self.frame)
            if result == -1:
                logger.debug(f"{self.name} - Outside request to stop processing")
                self.signals.finished.emit()
                return  # Exit early
            if result is None:
                logger.debug(f"{self.name} - Detection failed")
                self.signals.detect_failed.emit()
                self.signals.finished.emit()
                return  # Exit early
            if result == 1:
                logger.debug(f"{self.name} - Detection success")
                self.signals.found.emit()
            #self.signals.finished.emit()
            return

    def process(self, frame):
        raise NotImplementedError("Subclasses must implement this method.")
    
    def update_frame(self, frame):
        self.frame = frame

    def set_name(self, name):
        """Set name as camera serial number."""
        self.name = name
    
    def start_running(self):
        self.running = True

    def stop_running(self):
        self.running = False

class BaseReticleManager(QObject):
    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple, tuple)
    detect_failed = pyqtSignal()

    def __init__(self, name, WorkerClass, ProcessWorkerClass):
        super().__init__()
        self.name = name
        self.WorkerClass = WorkerClass
        self.thread = None
        self.worker = None

        self.processWorkerClass = ProcessWorkerClass
        self.processWorker = None

        self.threadpool = QThreadPool()
        print( f"Thread max count: {self.threadpool.maxThreadCount()}")

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

    def init_process_thread(self):
        #------------------ Process Thread---------
        self.processWorker = self.processWorkerClass(self.name)
        self.processWorker.signals.finished.connect(self.onThreadFinished)
        self.processWorker.signals.found_coords.connect(self.found_coords)
        self.processWorker.signals.detect_failed.connect(self.detect_failed)
        self.processWorker.signals.found.connect(self.process_success)
        #self.processWorker.signals.finished.connect(self.processWorker.deleteLater)

    def process(self, frame):
        if self.worker:
            self.worker.update_frame(frame)
        if self.processWorker:
            self.processWorker.update_frame(frame)

    def start(self):
        logger.debug(f"{self.name} Starting thread")
        self.init_thread()
        self.worker.start_running()
        self.thread.start()

        self.init_process_thread()
        self.processWorker.start_running()
        self.threadpool.start(self.processWorker)

    def stop(self):
        logger.debug(f"{self.name} Stopping thread")
        if self.worker:
            self.worker.stop_running()
        if self.processWorker:
            self.processWorker.stop_running()

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
        if self.processWorker is not None:
            self.processWorker.set_name(self.name)

    def process_success(self):
        if self.worker:
            # Drawing variables
            self.worker.origin = self.processWorker.origin
            self.worker.x = self.processWorker.x
            self.worker.y = self.processWorker.y
            self.worker.z = self.processWorker.z
            self.worker.x_coords = self.processWorker.x_coords
            self.worker.y_coords = self.processWorker.y_coords
            self.worker.found = True
