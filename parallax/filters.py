import cv2
import numpy as np
import time

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider
from PyQt5.QtCore import pyqtSignal, Qt, QObject, QThread, QMutex


class NoFilter(QObject):

    name = "None"

    frame_processed = pyqtSignal(object)

    class Worker(QObject):
        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)

        def __init__(self):
            QObject.__init__(self)
            self.running = True
            self.new = False

        def update_frame(self, frame):
            self.frame = frame
            self.new = True

        def process(self, frame):
            self.frame_processed.emit(frame)

        def stop_running(self):
            self.running = False

        def start_running(self):
            self.running = True

        def run(self):
            while self.running:
                if self.new:
                    self.process(self.frame)
                    self.new = False
                time.sleep(0.001)
            self.finished.emit()

    def __init__(self):
        QObject.__init__(self)
        # CV worker and thread
        self.thread = QThread()
        self.worker = self.Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.frame_processed.connect(self.frame_processed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def process(self, frame):
        self.worker.update_frame(frame)

    def launch_control_panel(self):
        pass

    def clean(self):
        self.worker.stop_running()
        self.thread.quit()
        self.thread.wait()


class CheckerboardFilter(NoFilter):

    name = "Checkerboard (fast)"
    CB_ROWS_DEFAULT = 19
    CB_COLS_DEFAULT = 19

    frame_processed = pyqtSignal(object)

    class Worker(NoFilter.Worker):

        CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        FLAGS = cv2.CALIB_CB_ADAPTIVE_THRESH \
                + cv2.CALIB_CB_NORMALIZE_IMAGE \
                + cv2.CALIB_CB_FAST_CHECK

        def __init__(self):
            NoFilter.Worker.__init__(self)
            self.mtx_corners = QMutex()
            self.corners = None

        def process(self, frame):
            if frame.ndim > 2:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            gray_scaled = cv2.pyrDown(gray)    # 1/2
            gray_scaled = cv2.pyrDown(gray_scaled)    # 1/4
            ret, corners_scaled = cv2.findChessboardCornersSB(gray_scaled, self.patternSize,
                                                                self.FLAGS)
            if ret:
                corners = corners_scaled * 4
                conv_size = (32, 32)
                corners = cv2.cornerSubPix(gray, corners, conv_size, (-1, -1), self.CRITERIA)
                self.mtx_corners.lock()
                self.corners = corners.squeeze()
                self.mtx_corners.unlock()
                cv2.drawChessboardCorners(frame, self.patternSize, self.corners, ret)
            else:
                self.mtx_corners.lock()
                self.corners = None
                self.mtx_corners.unlock()

            self.frame_processed.emit(frame)

        def set_pattern_size(self, rows, cols):
            self.patternSize = (rows, cols)

    def __init__(self):
        NoFilter.__init__(self)
        self.worker.set_pattern_size(self.CB_ROWS_DEFAULT, self.CB_COLS_DEFAULT)

    def launch_control_panel(self):
        pass

    def lock(self):
        self.worker.mtx_corners.lock()

    def unlock(self):
        self.worker.mtx_corners.unlock()


class CheckerboardSmoothFilter(NoFilter):

    name = "Checkerboard (smooth)"
    CB_ROWS_DEFAULT = 19
    CB_COLS_DEFAULT = 19

    frame_processed = pyqtSignal(object)

    class Worker(NoFilter.Worker):

        CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        FLAGS = cv2.CALIB_CB_ADAPTIVE_THRESH \
                + cv2.CALIB_CB_NORMALIZE_IMAGE \
                + cv2.CALIB_CB_FAST_CHECK

        def __init__(self):
            NoFilter.Worker.__init__(self)
            self.mtx_corners = QMutex()
            self.corners = None
            self.buf = []

        def process(self, frame):
            sz_roll = 16
            sz_conv = 32
            if frame.ndim > 2:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            gray_scaled = cv2.pyrDown(gray)    # 1/2
            gray_scaled = cv2.pyrDown(gray_scaled)    # 1/4
            ret, corners_scaled = cv2.findChessboardCornersSB(gray_scaled, self.patternSize,
                                                                self.FLAGS)
            corners_ave = None
            self.mtx_corners.lock()
            self.corners = None
            self.mtx_corners.unlock()
            if ret:
                corners = corners_scaled * 4
                conv_size = (sz_conv, sz_conv)
                corners = cv2.cornerSubPix(gray, corners, conv_size, (-1, -1), self.CRITERIA)
                corners = corners.squeeze()
                if len(self.buf) < sz_roll:
                    self.buf.append(corners)
                else:
                    buf_np = np.array(self.buf)
                    corners_ave = np.mean(buf_np, axis=0)
                    self.mtx_corners.lock()
                    self.corners = corners_ave
                    self.mtx_corners.unlock()
                    self.buf = self.buf[1:]
                    self.buf.append(corners)
                    cv2.drawChessboardCorners(frame, self.patternSize, self.corners, ret)

            self.frame_processed.emit(frame)


        def set_pattern_size(self, rows, cols):
            self.patternSize = (rows, cols)

    def __init__(self):
        NoFilter.__init__(self)
        self.worker.set_pattern_size(self.CB_ROWS_DEFAULT, self.CB_COLS_DEFAULT)

    def launch_control_panel(self):
        pass

    def lock(self):
        self.worker.mtx_corners.lock()

    def unlock(self):
        self.worker.mtx_corners.unlock()


