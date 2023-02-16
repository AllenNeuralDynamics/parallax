import cv2
import numpy as np
import random
import time

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt


class NoDetector():

    name = "None"

    def __init__(self):
        pass

    def process(self, frame): return None

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

def template_match(img, template, method):
    res = cv2.matchTemplate(img, template, method)
    if method == cv2.TM_SQDIFF_NORMED:
        ext = res.argmin()
    else:
        ext = res.argmax()
    mx = np.array(np.unravel_index(ext, res.shape))
    return res, mx

class TemplateMatchDetector():

    name = 'Template Match'

    scaling = 0.25
    method = cv2.TM_CCORR_NORMED
    #interp = cv2.INTER_LINEAR
    interp = cv2.INTER_NEAREST

    def __init__(self):
        self.template_scaled = None
        self.set_template(np.load('template.npy'))

    def scale(self, img):
        return cv2.resize(img, None, fx=self.scaling, fy=self.scaling, interpolation=self.interp)

    def set_template(self, template):
        self.template_scaled = self.scale(template)

    def process(self, frame):
        if self.template_scaled is not None:
            frame_scaled = self.scale(frame)
            res, mx = template_match(frame_scaled, self.template_scaled, self.method)
            return (mx[1], mx[0])
        else:
            return (0,0)

    def launch_control_panel(self):
        self.control_panel = QWidget()
        layout = QVBoxLayout()
        self.load_button = QPushButton('Load Template')
        layout.addWidget(self.load_button)
        self.control_panel.setLayout(layout)
        self.control_panel.setWindowTitle('Template Match Detector')
        self.control_panel.setMinimumWidth(300)
        self.control_panel.show()

    
