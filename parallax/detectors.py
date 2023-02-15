import cv2
import numpy as np
import random

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider
from PyQt5.QtCore import pyqtSignal, Qt


class NoDetector():

    name = "None"

    def __init__(self):
        pass

    def process(self, frame):
        return None

    def launch_control_panel(self):
        pass


class RandomWalkDetector():

    name = 'Random Walk'

    def __init__(self):
        self.pos = (0,0)
        self.step = 5

    def set_step(self, value):
        self.step = value

    def walk(self, val, step, mn, mx):
        val += random.choice([-1, 1]) * self.step
        if val < mn:    val = mn
        if val >= mx:   val = mx-1
        return val

    def process(self, frame):
        x,y = self.pos
        x = self.walk(x, self.step, 0, 4000)
        y = self.walk(y, self.step, 0, 3000)
        self.pos = (x,y)
        return self.pos

    def launch_control_panel(self):
        self.control_panel = QWidget()
        layout = QVBoxLayout()
        self.step_slider = QSlider(Qt.Horizontal)
        self.step_slider.setValue(self.step)
        self.step_slider.setToolTip('Step Size')
        self.step_slider.sliderMoved.connect(self.set_step)
        layout.addWidget(self.step_slider)
        self.control_panel.setLayout(layout)
        self.control_panel.setWindowTitle('Random Walk Detector')
        self.control_panel.setMinimumWidth(300)
        self.control_panel.show()

