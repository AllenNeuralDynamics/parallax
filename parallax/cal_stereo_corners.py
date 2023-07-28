from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QFrame, QInputDialog, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QMenu, QCheckBox
from PyQt5.QtWidgets import QTabWidget 
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtGui import QIcon, QDrag
from PyQt5.QtCore import QSize, pyqtSignal, Qt 

import numpy as np
import time
import datetime
import cv2
import os
import pickle

from . import get_image_file, data_dir
from .helper import FONT_BOLD, WF, HF
from .calibration import Calibration

class CalibrateStereoCornersTool(QWidget):
    msg_posted = pyqtSignal(str)
    cal_generated = pyqtSignal()

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.load_corners_button = QPushButton('Load corners')
        self.load_corners_button.clicked.connect(self.load_corners)

        self.opts = None
        self.lipts = None
        self.ripts = None
        self.npts_label = QLabel('0 poses loaded')
        self.npts_label.setAlignment(Qt.AlignCenter)
        self.npts_label.setFont(FONT_BOLD)

        self.name_label = QLabel('Name:')
        self.name_label.setAlignment(Qt.AlignCenter)
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_name = 'cal_%04d%02d%02d-%02d%02d%02d' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.name_edit = QLineEdit(suggested_name)

        self.intrinsics_label = QLabel('Provide Intrinsics')
        self.intrinsics_label.setAlignment(Qt.AlignCenter)
        self.intrinsics_check = QCheckBox()
        self.intrinsics_check.stateChanged.connect(self.handle_check)
        self.int1_label = QLabel('Left:')
        self.int1_label.setAlignment(Qt.AlignRight)
        self.int1_button = QPushButton('Load')
        self.int1_button.setEnabled(False)
        self.int1_button.clicked.connect(self.load_int1)
        self.int2_label = QLabel('Right:')
        self.int2_label.setAlignment(Qt.AlignRight)
        self.int2_button = QPushButton('Load')
        self.int2_button.setEnabled(False)
        self.int2_button.clicked.connect(self.load_int2)

        self.generate_button = QPushButton('Generate Calibration')
        self.generate_button.clicked.connect(self.generate_calibration)
        self.generate_button.setEnabled(False)

        layout = QGridLayout()
        layout.addWidget(self.load_corners_button, 0,0, 1,2)
        layout.addWidget(self.npts_label, 1,0, 1,2)
        layout.addWidget(self.name_label, 2,0, 1,1)
        layout.addWidget(self.name_edit, 2,1, 1,1)
        layout.addWidget(self.intrinsics_label, 3,0, 1,1)
        layout.addWidget(self.intrinsics_check, 3,1, 1,1)
        layout.addWidget(self.int1_label, 4,0, 1,1)
        layout.addWidget(self.int1_button, 4,1, 1,1)
        layout.addWidget(self.int2_label, 5,0, 1,1)
        layout.addWidget(self.int2_button, 5,1, 1,1)
        layout.addWidget(self.generate_button, 6,0, 1,2)

        self.setLayout(layout)
        self.setMinimumWidth(350)

        self.setWindowTitle('Calibration from Stereo Corners')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def handle_check(self):
        self.int1_button.setEnabled(self.intrinsics_check.checkState())
        self.int2_button.setEnabled(self.intrinsics_check.checkState())

    def load_int1(self):
        filename = QFileDialog.getOpenFileName(self, 'Load intrinsics file', data_dir,
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                self.int1 = pickle.load(f)
            self.int1_button.setText(os.path.basename(self.int1.name))

    def load_int2(self):
        filename = QFileDialog.getOpenFileName(self, 'Load intrinsics file', data_dir,
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                self.int2 = pickle.load(f)
            self.int2_button.setText(os.path.basename(self.int2.name))

    def load_corners(self):
        filename = QFileDialog.getOpenFileName(self, 'Load corners file (stereo)', data_dir,
                                                    'Numpy files (*.npz)')[0]
        if filename:
            corners = np.load(filename)
            self.opts = corners['opts']
            self.lipts = corners['lipts']
            self.ripts = corners['ripts']
            self.update_gui()

    def update_gui(self):
        if self.opts is not None:
            self.npts_label.setText('%d points loaded' % self.opts.shape[0])
            self.generate_button.setEnabled(True)

    def generate_calibration(self):
        name = self.name_edit.text()
        self.cal = Calibration(name, 'checker')
        if self.intrinsics_check.isChecked():
            self.cal.set_initial_intrinsics(self.int1.mtx, self.int2.mtx,
                                            self.int1.dist, self.int2.dist, fixed=True)
        self.cal.calibrate(self.lipts, self.ripts, self.opts)
        self.msg_posted.emit('Generated %s' % self.cal.name)
        self.msg_posted.emit('RMSE = %.2f um' % self.cal.rmse_tri_norm)
        self.model.add_calibration(self.cal)
        self.cal_generated.emit()

