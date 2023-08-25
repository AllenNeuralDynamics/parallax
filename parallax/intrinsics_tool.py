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
from .calibration import imtx, idist

CRIT = (cv2.TERM_CRITERIA_EPS, 0, 1e-8)

class IntrinsicParameters:

    def __init__(self, name):
        self.set_name(name)
        self.set_initial_intrinsics_default()

    def set_name(self, name):
        self.name = name

    def set_initial_intrinsics(self, mtx, dist):

        self.imtx = mtx
        self.idist = dist

    def set_initial_intrinsics_default(self):
        self.set_initial_intrinsics(imtx, idist)

    def calibrate(self, img_points, obj_points):

        # img_points have dims (npose, npts, 2)
        # obj_points have dims (npose, npts, 3)

        my_flags = cv2.CALIB_USE_INTRINSIC_GUESS

        rmse, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points,
                                                                        (WF, HF),
                                                                        self.imtx, self.idist,
                                                                        flags=my_flags,
                                                                        criteria=CRIT)

        self.mtx = mtx
        self.dist = dist
        self.rmse = rmse  # RMS error from reprojection (in pixels)

        # save calibration points
        self.obj_points = obj_points
        self.img_points = img_points


class IntrinsicsTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self):
        QWidget.__init__(self, parent=None)

        self.load_corners_button = QPushButton('Load corners')
        self.load_corners_button.clicked.connect(self.load_corners)

        self.opts = None
        self.ipts = None
        self.npts_label = QLabel('0 poses loaded')
        self.npts_label.setAlignment(Qt.AlignCenter)
        self.npts_label.setFont(FONT_BOLD)

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_name = 'intrinsics_%04d%02d%02d-%02d%02d%02d' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.name_edit = QLineEdit(suggested_name)

        self.generate_button = QPushButton('Generate intrinsics')
        self.generate_button.clicked.connect(self.generate_intrinsics)
        self.generate_button.setEnabled(False)

        self.save_button = QPushButton('Save intrinsics')
        self.save_button.clicked.connect(self.save_intrinsics)
        self.save_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.load_corners_button)
        layout.addWidget(self.npts_label)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.save_button)

        self.setLayout(layout)
        self.setMinimumWidth(350)

        self.setWindowTitle('Intrinsics Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def load_corners(self):
        filename = QFileDialog.getOpenFileName(self, 'Load corners file (mono)', data_dir,
                                                    'Numpy files (*.npz)')[0]
        if filename:
            corners = np.load(filename)
            self.opts = corners['opts']
            self.ipts = corners['ipts']
            self.update_gui()

    def update_gui(self):
        if self.opts is not None:
            self.npts_label.setText('%d points loaded' % self.opts.shape[0])
            self.generate_button.setEnabled(True)

    def generate_intrinsics(self):
        name = self.name_edit.text()
        self.intrinsics = IntrinsicParameters(name)
        self.intrinsics.calibrate(self.ipts, self.opts)
        self.msg_posted.emit('Generated %s' % self.intrinsics.name)
        self.msg_posted.emit('mtx = %s' % np.array2string(self.intrinsics.mtx))
        self.msg_posted.emit('dist = %s' % np.array2string(self.intrinsics.dist))
        self.msg_posted.emit('RMSE = %.2f' % self.intrinsics.rmse)
        self.save_button.setEnabled(True)

    def save_intrinsics(self):
        suggested_filename = os.path.join(data_dir, self.intrinsics.name + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save intrinsics file',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(self.intrinsics, f)
            self.msg_posted.emit('Saved intrinsics to: %s' % filename)

