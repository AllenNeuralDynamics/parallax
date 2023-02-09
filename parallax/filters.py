import cv2

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider
from PyQt5.QtCore import pyqtSignal, Qt

class NoFilter():

    name = "None"

    def __init__(self):
        pass

    def process(self, frame):
        return frame

    def launch_control_panel(self):
        pass

class AlphaBetaFilter():

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

