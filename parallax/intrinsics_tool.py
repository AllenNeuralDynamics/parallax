# Import necessary PyQt5 modules and other dependencies
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

# Import local modules and constants
from . import get_image_file, data_dir
from .helper import FONT_BOLD, WF, HF
from .calibration import imtx, idist

# Set the termination criteria for calibration
CRIT = (cv2.TERM_CRITERIA_EPS, 0, 1e-8)

# Define a class to store intrinsic camera parameters
class IntrinsicParameters:
    def __init__(self, name):
        self.set_name(name)
        # Set initial intrinsic parameters to default values
        self.set_initial_intrinsics_default()

    def set_name(self, name):
        self.name = name

    def set_initial_intrinsics(self, mtx, dist):
        # Set initial intrinsic parameters, such as camera matrix (mtx) and distortion coefficients (dist)
        # imtx = np.array([[1.5e+04, 0.0e+00, 2e+03],
        #        [0.0e+00, 1.5e+04, 1.5e+03],
        #        [0.0e+00, 0.0e+00, 1.0e+00]],
        #        dtype=np.float32)
        # idist = np.array([[ 0e+00, 0e+00, 0e+00, 0e+00, 0e+00 ]],
        #            dtype=np.float32)
        self.imtx = mtx
        self.idist = dist

    def set_initial_intrinsics_default(self):
        self.set_initial_intrinsics(imtx, idist)

    def calibrate(self, img_points, obj_points):
        # img_points have dims (npose, npts, 2)
        # obj_points have dims (npose, npts, 3)

        my_flags = cv2.CALIB_USE_INTRINSIC_GUESS

        # Returns the camera matrix, distortion coefficients, rotation and translation vectors etc
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


# Define a QWidget for intrinsics calibration tool
class IntrinsicsTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self):
        # Initialize the QWidget
        QWidget.__init__(self, parent=None)

        # Create a button to load corner data
        self.load_corners_button = QPushButton('Load corners')
        self.load_corners_button.clicked.connect(self.load_corners)

        # Initialize variables to store corner data
        self.opts = None
        self.ipts = None

        # Create a label to display the number of poses loaded
        self.npts_label = QLabel('0 poses loaded')
        self.npts_label.setAlignment(Qt.AlignCenter)
        self.npts_label.setFont(FONT_BOLD)

        # Create a line edit widget for specifying the name
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_name = 'intrinsics_%04d%02d%02d-%02d%02d%02d' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.name_edit = QLineEdit(suggested_name)

        # Create a button to generate intrinsics
        self.generate_button = QPushButton('Generate intrinsics')
        self.generate_button.clicked.connect(self.generate_intrinsics)
        self.generate_button.setEnabled(False)

        # Create a button to save intrinsics
        self.save_button = QPushButton('Save intrinsics')
        self.save_button.clicked.connect(self.save_intrinsics)
        self.save_button.setEnabled(False)

        # Create a layout for the widgets
        layout = QVBoxLayout()
        layout.addWidget(self.load_corners_button)
        layout.addWidget(self.npts_label)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.save_button)

        # Set the layout for the QWidget
        self.setLayout(layout)
        self.setMinimumWidth(350)
        # Set the window title and icon
        self.setWindowTitle('Intrinsics Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def load_corners(self):
        # Load corner data from a file selected using a file dialog
        filename = QFileDialog.getOpenFileName(self, 'Load corners file (mono)', data_dir,
                                                    'Numpy files (*.npz)')[0]
        if filename:
            corners = np.load(filename)
            self.opts = corners['opts']
            self.ipts = corners['ipts']
            self.update_gui()

    def update_gui(self):
        # Update the GUI elements based on loaded corner data
        if self.opts is not None:
            self.npts_label.setText('%d points loaded' % self.opts.shape[0])
            self.generate_button.setEnabled(True)

    def generate_intrinsics(self):
        # Generate intrinsic parameters using loaded corner data
        name = self.name_edit.text()
        self.intrinsics = IntrinsicParameters(name)
        self.intrinsics.calibrate(self.ipts, self.opts)
        self.msg_posted.emit('Generated %s' % self.intrinsics.name)
        self.msg_posted.emit('mtx = %s' % np.array2string(self.intrinsics.mtx))
        self.msg_posted.emit('dist = %s' % np.array2string(self.intrinsics.dist))
        self.msg_posted.emit('RMSE = %.2f' % self.intrinsics.rmse)
        self.save_button.setEnabled(True)

    def save_intrinsics(self):
        # Save generated intrinsic parameters to a file
        suggested_filename = os.path.join(data_dir, self.intrinsics.name + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save intrinsics file',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(self.intrinsics, f)
            self.msg_posted.emit('Saved intrinsics to: %s' % filename)

