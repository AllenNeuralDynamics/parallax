import cv2
import numpy as np
import random
import time
import os

import sleap
from time import perf_counter

from PyQt5.QtWidgets import QWidget, QLabel, QSlider, QPushButton
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog
from PyQt5.QtCore import pyqtSignal, Qt, QThread, QObject

from . import data_dir
from .helper import FONT_BOLD


class NoDetector:

    name = "None"

    def __init__(self):
        pass

    def process(self, frame): return None

    def launch_control_panel(self):
        pass


class SleapDetector(QObject):

    name = 'SLEAP'

    tracked = pyqtSignal(tuple)

    class SleapWorker(QObject):

        finished = pyqtSignal()
        tracked = pyqtSignal(tuple)
        status_updated = pyqtSignal(bool, float)

        def __init__(self, predictor):
            QObject.__init__(self)
            self.predictor = predictor
            self.running = True
            self.new = False

        def update_frame(self, frame):
            self.frame = frame
            self.new = True

        def process(self, frame, report=True):
            frame = np.array([frame])
            t0 = perf_counter()
            labeled_frames = self.predictor.predict(frame)        
            dt = perf_counter() - t0
            labeled_frame = labeled_frames[0]
            tip_positions = []
            for i, instance in enumerate(labeled_frame.instances):
                point = instance.points[0]
                tip_positions.append((point.x, point.y))
            if report:
                print('\tinference time = ', dt)
            if len(tip_positions) >= 1:
                self.tracked.emit(tip_positions[0])
            else:
                print('No probe tips detected')

        def run(self):
            while self.running:
                if self.new:
                    self.process(self.frame)
                    self.new = False
                time.sleep(0.001)
            self.finished.emit()

    def __init__(self):
        QObject.__init__(self)

        centroid_dir = os.path.join(data_dir, 'sleap_centroid')
        centered_instance_dir = os.path.join(data_dir, 'sleap_centered_instance')
        predictor = sleap.load_model([centroid_dir, centered_instance_dir],
                            batch_size=1)

        # CV worker and thread
        self.cv_thread = QThread()
        self.cv_worker = self.SleapWorker(predictor)
        self.cv_worker.moveToThread(self.cv_thread)
        self.cv_thread.started.connect(self.cv_worker.run)
        self.cv_worker.finished.connect(self.cv_thread.quit, Qt.DirectConnection)
        self.cv_worker.finished.connect(self.cv_worker.deleteLater)
        self.cv_thread.finished.connect(self.cv_thread.deleteLater)
        #self.cv_worker.tracked.connect(self.handle_tracked)
        self.cv_worker.tracked.connect(self.tracked)
        #self.cv_worker.status_updated.connect(self.update_status)
        self.cv_thread.start()

    def process(self, frame):
        self.cv_worker.update_frame(frame)
        return 0,0

    def handle_tracked(self, pos):
        print('HANDLE TRACKED: ', pos)

    def launch_control_panel(self):
        pass


class RandomWalkDetector:

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


class TemplateMatchDetector:

    name = 'Template Match'

    method = cv2.TM_CCORR_NORMED
    interp = cv2.INTER_NEAREST

    def __init__(self):
        self.template = None
        self.template_scaled = None
        self.scaling = 0.25

        self.control_panel = QWidget()
        self.template_label = QLabel('(no template loaded)')
        self.template_label.setAlignment(Qt.AlignCenter)
        self.template_label.setFont(FONT_BOLD)
        self.load_button = QPushButton('Load Template')
        self.load_button.clicked.connect(self.load)
        layout = QVBoxLayout()
        layout.addWidget(self.template_label)
        layout.addWidget(self.load_button)
        self.control_panel.setLayout(layout)
        self.control_panel.setWindowTitle('Template Match Detector')
        self.control_panel.setMinimumWidth(300)

    def scale(self, img):
        return cv2.resize(img, None, fx=self.scaling, fy=self.scaling, interpolation=self.interp)

    def scale_template(self):
        if self.template is not None:
            self.template_scaled = self.scale(self.template)

    def process(self, frame):
        if self.template_scaled is not None:
            frame_scaled = self.scale(frame)
            res, mx = template_match(frame_scaled, self.template_scaled, self.method)
            y,x = tuple(mx / self.scaling + self.offset)
            return (x,y)
        else:
            return (0,0)

    def launch_control_panel(self):
        self.control_panel.show()

    def load(self):
        filename = QFileDialog.getOpenFileName(self.control_panel, 'Load template file',
                                                data_dir, 'Numpy files (*.npy)')[0]
        if filename:
            self.template = np.load(filename)
            self.offset = np.array(self.template.shape[:2]) // 2
            self.scale_template()
            self.template_label.setText(os.path.relpath(filename))

    
