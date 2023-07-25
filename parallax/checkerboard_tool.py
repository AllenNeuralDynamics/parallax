from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QInputDialog
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QIcon

import cv2
import numpy as np
import time
import datetime
import os
import pickle

from . import get_image_file, data_dir
from .screen_widget import ScreenWidget
from .filters import CheckerboardFilter

CB_ROWS = 19 #number of checkerboard rows.
CB_COLS = 19 #number of checkerboard columns.
WORLD_SCALE = 500 # 500 um per square

#coordinates of squares in the checkerboard world space
OBJPOINTS_CB = np.zeros((CB_ROWS*CB_COLS,3), np.float32)
OBJPOINTS_CB[:,:2] = np.mgrid[0:CB_ROWS,0:CB_COLS].T.reshape(-1,2)
OBJPOINTS_CB = WORLD_SCALE * OBJPOINTS_CB


class CheckerboardToolMono(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.model = model

        self.lscreen = ScreenWidget(model=self.model)
        self.grab_button = QPushButton('Grab Corners')
        self.grab_button.clicked.connect(self.grab_corners)
        self.save_corners_button = QPushButton('Save Corners (None)')
        self.save_corners_button.clicked.connect(self.save_corners)
        self.load_corners_button = QPushButton('Load Corners')
        self.load_corners_button.clicked.connect(self.load_corners)

        self.screens_layout = QHBoxLayout()
        self.screens_layout.addWidget(self.lscreen)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.lscreen)
        self.layout.addWidget(self.grab_button)
        self.layout.addWidget(self.save_corners_button)
        self.layout.addWidget(self.load_corners_button)
        self.setLayout(self.layout)

        self.setWindowTitle('Checkerboard Tool (Mono)')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.lscreen.refresh)
        self.refresh_timer.start(250)

        self.opts = []  # object points
        self.ipts = [] # left image points

        self.last_cal = None

    def grab_corners(self):
        lfilter = self.lscreen.filter
        if isinstance(lfilter, CheckerboardFilter):
            if (lfilter.worker.corners is not None):
                self.ipts.append(lfilter.worker.corners)
                self.opts.append(OBJPOINTS_CB)
                self.update_gui()

    def update_gui(self):
        self.save_corners_button.setText('Save Corners (%d)' % len(self.opts))

    def save_corners(self):
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_basename = 'corners_mono_%04d%02d%02d-%02d%02d%02d.npz' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        suggested_filename = os.path.join(data_dir, suggested_basename)
        filename = QFileDialog.getSaveFileName(self, 'Save Corners File',
                                                suggested_filename,
                                                'Numpy files (*.npz)')[0]
        if filename:
            np.savez(filename, opts=self.opts, ipts=self.ipts)
            self.msg_posted.emit('Exported corners to %s' % filename)

    def load_corners(self):
        filename = QFileDialog.getOpenFileName(self, 'Load corners file', data_dir,
                                                    'Numpy files (*.npz)')[0]
        if filename:
            corners = np.load(filename)
            self.opts = corners['opts']
            self.ipts = corners['ipts']
            self.update_gui()


class CheckerboardToolStereo(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.model = model

        self.lscreen = ScreenWidget(model=self.model)
        self.rscreen = ScreenWidget(model=self.model)
        self.grab_button = QPushButton('Grab Corners')
        self.grab_button.clicked.connect(self.grab_corners)
        self.save_button = QPushButton('Save Corners (None)')
        self.save_button.clicked.connect(self.save_corners)
        self.load_button = QPushButton('Load Corners')
        self.load_button.clicked.connect(self.load_corners)

        self.screens_layout = QHBoxLayout()
        self.screens_layout.addWidget(self.lscreen)
        self.screens_layout.addWidget(self.rscreen)

        self.layout = QVBoxLayout()
        self.layout.addLayout(self.screens_layout)
        self.layout.addWidget(self.grab_button)
        self.layout.addWidget(self.save_button)
        self.layout.addWidget(self.load_button)
        self.setLayout(self.layout)

        self.setWindowTitle('Checkerboard Tool (stereo)')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.lscreen.refresh)
        self.refresh_timer.timeout.connect(self.rscreen.refresh)
        self.refresh_timer.start(250)

        self.opts = []  # object points
        self.lipts = [] # left image points
        self.ripts = [] # right image points

    def grab_corners(self):
        lfilter = self.lscreen.filter
        rfilter = self.rscreen.filter
        if isinstance(lfilter, CheckerboardFilter) and \
            isinstance(rfilter, CheckerboardFilter):
            lfilter.lock()
            rfilter.lock()
            if (lfilter.worker.corners is not None) and (rfilter.worker.corners is not None):
                self.lipts.append(lfilter.worker.corners)
                self.ripts.append(rfilter.worker.corners)
                self.opts.append(OBJPOINTS_CB)
                self.update_text()
            lfilter.unlock()
            rfilter.unlock()

    def update_text(self):
        self.export_button.setText('Save Corners (%d)' % len(self.opts))

    def save_corners(self):
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_basename = 'corners_%04d%02d%02d-%02d%02d%02d.npz' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        suggested_filename = os.path.join(data_dir, suggested_basename)
        filename = QFileDialog.getSaveFileName(self, 'Save corners',
                                                suggested_filename,
                                                'Numpy files (*.npz)')[0]
        if filename:
            np.savez(filename, opts=self.opts, lipts=self.lipts, ripts=self.ripts)
            self.msg_posted.emit('Saved corners to %s' % filename)

    def load_corners(self):
        filename = QFileDialog.getOpenFileName(self, 'Load corners file', data_dir,
                                                    'Numpy files (*.npz)')[0]
        corners = np.load(filename)
        self.opts = corners['opts']
        self.lipts = corners['lipts']
        self.ripts = corners['ripts']
        self.update_text()

