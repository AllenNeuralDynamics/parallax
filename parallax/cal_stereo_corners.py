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

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_name = 'cal_%04d%02d%02d-%02d%02d%02d' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.name_edit = QLineEdit(suggested_name)

        self.generate_button = QPushButton('Generate Calibration')
        self.generate_button.clicked.connect(self.generate_calibration)
        self.generate_button.setEnabled(False)

        self.save_button = QPushButton('Save Calibration')
        self.save_button.clicked.connect(self.save_calibration)
        self.save_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.load_corners_button)
        layout.addWidget(self.npts_label)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.save_button)

        self.setLayout(layout)
        self.setMinimumWidth(350)

        self.setWindowTitle('Calibration from Stereo Corners')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

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
        self.cal.calibrate(self.lipts, self.ripts, self.opts)
        self.msg_posted.emit('Generated %s' % self.cal.name)
        self.msg_posted.emit('RMSE = %.2f' % self.cal.rmse_tri_norm)
        self.model.add_calibration(self.cal)
        self.save_button.setEnabled(True)

    def save_calibration(self):
        suggested_filename = os.path.join(data_dir, self.cal.name + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save calibration',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(self.cal, f)
            self.msg_posted.emit('Saved calibration to: %s' % filename)

