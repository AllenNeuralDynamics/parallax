from PyQt5.QtWidgets import QPushButton, QLabel, QWidget
from PyQt5.QtWidgets import QVBoxLayout, QFileDialog
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QIcon

import cv2
import numpy as np
import time
import datetime
import os

from . import get_image_file, data_dir
from .screen_widget import ScreenWidget

CB_ROWS = 19 #number of checkerboard rows.
CB_COLS = 19 #number of checkerboard columns.
WORLD_SCALE = 500 # 500 um per square

#coordinates of squares in the checkerboard world space
OBJPOINTS_CB = np.zeros((CB_ROWS*CB_COLS,3), np.float32)
OBJPOINTS_CB[:,:2] = np.mgrid[0:CB_ROWS,0:CB_COLS].T.reshape(-1,2)
OBJPOINTS_CB = WORLD_SCALE * OBJPOINTS_CB


class CheckerboardTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.model = model

        self.screen = ScreenWidget(model=self.model)
        self.save_button = QPushButton('Save Corners')
        self.save_button.clicked.connect(self.saveCorners)
        self.export_button = QPushButton('Export Corners (None)')
        self.export_button.clicked.connect(self.exportCorners)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.save_button)
        self.layout.addWidget(self.export_button)
        self.setLayout(self.layout)

        self.setWindowTitle('Checkerboard Calibration Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.screen.refresh)
        self.refresh_timer.start(250)

        self.opts = []
        self.ipts = []

    def saveCorners(self):
        corners = self.screen.filter.corners
        if corners is not None:
            self.ipts.append(corners)
            self.opts.append(OBJPOINTS_CB)
            self.export_button.setText('Export Corners (%d)' % len(self.ipts))

    def exportCorners(self):
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_basename = 'corners_%04d%02d%02d-%02d%02d%02d.npz' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        suggested_filename = os.path.join(data_dir, suggested_basename)
        filename = QFileDialog.getSaveFileName(self, 'Save corners',
                                                suggested_filename,
                                                'Numpy files (*.npz)')[0]
        if filename:
            np.savez(filename, opts=self.opts, ipts=self.ipts)
            self.msg_posted.emit('Exported corners to %s' % filename)

