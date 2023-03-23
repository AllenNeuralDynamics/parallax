import cv2
import numpy as np

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider
from PyQt5.QtCore import pyqtSignal, Qt


class NoFilter:

    name = "None"

    def __init__(self):
        pass

    def process(self, frame):
        return frame

    def launch_control_panel(self):
        pass

class AlphaBetaFilter:

    name = 'Brightness and Contrast'

    def __init__(self):
        self.alpha = 1.0
        self.beta = 0

    def set_alpha(self, value):
        self.alpha = value / 25.

    def set_beta(self, value):
        self.beta = value * 4 - 200

    def process(self, frame):
        return cv2.convertScaleAbs(frame, alpha=self.alpha, beta=self.beta)

    def launch_control_panel(self):
        self.control_panel = QWidget()
        layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setValue(50)
        self.brightness_slider.setToolTip('Brightness')
        self.brightness_slider.sliderMoved.connect(self.set_beta)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setValue(25)
        self.contrast_slider.setToolTip('Contrast')
        self.contrast_slider.sliderMoved.connect(self.set_alpha)
        layout.addWidget(self.brightness_slider)
        layout.addWidget(self.contrast_slider)
        self.control_panel.setLayout(layout)
        self.control_panel.setWindowTitle('Brightness and Contrast')
        self.control_panel.setMinimumWidth(300)
        self.control_panel.show()

class DifferenceFilter:

    name = 'Difference'

    def __init__(self):
        self.buff = None
        self.alpha = 1.0
        self.beta = 0

    def process(self, frame):
        if self.buff is not None:
            """
            buff_scaled = np.array(self.alpha * self.buff, dtype=np.uint8)
            result = frame - buff_scaled
            """
            diff = cv2.absdiff(frame, self.buff)
            result = cv2.convertScaleAbs(diff, alpha=self.alpha, beta=self.beta)
        else:
            result = frame
        self.buff = frame
        return result

    def set_alpha(self, value):
        self.alpha = value / 25.

    def set_beta(self, value):
        self.beta = value * 4 - 200

    def launch_control_panel(self):
        self.control_panel = QWidget()
        layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setValue(50)
        self.brightness_slider.setToolTip('Brightness')
        self.brightness_slider.sliderMoved.connect(self.set_beta)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setValue(25)
        self.contrast_slider.setToolTip('Contrast')
        self.contrast_slider.sliderMoved.connect(self.set_alpha)
        layout.addWidget(self.brightness_slider)
        layout.addWidget(self.contrast_slider)
        self.control_panel.setLayout(layout)
        self.control_panel.setWindowTitle('Difference Filter')
        self.control_panel.setMinimumWidth(300)
        self.control_panel.show()


class CheckerboardFilter:

    name = 'Checkerboard'
    CB_ROWS = 6
    CB_COLS = 9

    def __init__(self):
        self.patternSize = (self.CB_ROWS, self.CB_COLS)
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        self.corners = None

    def process(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_scaled = cv2.pyrDown(gray)    # 1/2
        gray_scaled = cv2.pyrDown(gray_scaled)    # 1/4
        ret, corners_scaled = cv2.findChessboardCorners(gray_scaled, self.patternSize, None)
        if ret:
            self.corners = corners_scaled * 4
            conv_size = (11, 11)    # Convolution size, don't make this too large.
            self.corners = cv2.cornerSubPix(gray, self.corners, conv_size, (-1, -1), self.criteria)
            cv2.drawChessboardCorners(frame, self.patternSize, self.corners, ret)
        return frame

    def launch_control_panel(self):
        pass

