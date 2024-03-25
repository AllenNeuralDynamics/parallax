# Import necessary PyQt5 modules and other libraries
from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QFrame, QTextEdit
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QFileDialog
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt 

import numpy as np
import os

# Import custom modules from the project
from .helper import FONT_BOLD
from . import get_image_file, data_dir
from .stage_dropdown import CalibrationDropdown

# Create a class for the CalibrationTester
class CalibrationTester(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        # Create a calibration dropdown widget
        self.cal_dropdown = CalibrationDropdown(self.model)

        # Create a button to load stereo corners data
        self.load_corners_button = QPushButton('Load Stereo Corners')
        self.load_corners_button.clicked.connect(self.load_corners)

        self.opts = None
        self.lipts = None
        self.ripts = None

        # Create a label for displaying the number of poses loaded
        self.npts_label = QLabel('0 poses loaded')
        self.npts_label.setAlignment(Qt.AlignCenter)
        self.npts_label.setFont(FONT_BOLD)

        # Create a button to test calibration
        self.test_button = QPushButton('Test Calibration')
        self.test_button.clicked.connect(self.test_calibration)
        self.test_button.setEnabled(False)

        # Create a QTextEdit widget to display test results
        self.results_edit = QTextEdit()
        self.results_edit.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.cal_dropdown)
        layout.addWidget(self.load_corners_button)
        layout.addWidget(self.npts_label)
        layout.addWidget(self.test_button)
        layout.addWidget(self.results_edit)

        self.setLayout(layout)
        self.setMinimumWidth(450)

        # Set window title and icon
        self.setWindowTitle('Calibration Tester')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    # Function to load stereo corners data
    def load_corners(self):
        filename = QFileDialog.getOpenFileName(self, 'Load corners file (stereo)', data_dir,
                                                    'Numpy files (*.npz)')[0]
        if filename:
            corners = np.load(filename)
            self.opts = corners['opts']
            self.lipts = corners['lipts']
            self.ripts = corners['ripts']
            self.load_corners_button.setText(os.path.basename(filename))
            self.update_gui()

    # Function to update the user interface
    def update_gui(self):
        if self.opts is not None:
            self.npts_label.setText('%d poses loaded' % self.opts.shape[0])
            self.test_button.setEnabled(True)

    # Function to test calibration
    def test_calibration(self):
        cal = self.model.calibrations[self.cal_dropdown.currentText()]
        nposes, ncorners, _ = self.opts.shape
        delta = []
        for i in range(nposes):
            origin_cb = self.opts[i,0,:]
            origin_cam = cal.triangulate(self.lipts[i,0,:], self.ripts[i,0,:])
            for j in range(1, ncorners):
                vec_cb = np.linalg.norm(self.opts[i,j,:] - origin_cb)
                vec_cam = np.linalg.norm(cal.triangulate(self.lipts[i,j,:], self.ripts[i,j,:]) - \
                                        origin_cam)
                delta.append(vec_cam - vec_cb)
        delta = np.array(delta, dtype=np.float32)
        self.results_edit.append('mean(err) = %.2f' % np.mean(delta, axis=0))
        self.results_edit.append('std(err) = %.2f' % np.std(delta, axis=0))
        self.results_edit.append('rms(err) = %.2f' % np.sqrt(np.mean(delta * delta)))
        self.results_edit.append('----')

