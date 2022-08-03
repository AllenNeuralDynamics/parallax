from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtCore import QThread, Qt
from PyQt5.QtCore import QThread, pyqtSignal, Qt

import os
import numpy as np

from Calibration import Calibration
from lib import *
from Helper import *
from Dialogs import *


class TriangulationPanel(QFrame):
    msgPosted = pyqtSignal(str)

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # layout
        mainLayout = QVBoxLayout()
        self.mainLabel = QLabel('Triangulation')
        self.mainLabel.setAlignment(Qt.AlignCenter)
        self.mainLabel.setFont(FONT_BOLD)
        self.calButton = QPushButton('Run Calibration Routine')
        self.loadButton = QPushButton('Load Calibration')
        self.saveButton = QPushButton('Save Calibration')
        self.goButton = QPushButton('Triangulate Points')

        self.statusLabel = QLabel()
        self.statusLabel.setAlignment(Qt.AlignCenter)
        self.statusLabel.setFont(FONT_BOLD)
        self.updateStatus()

        mainLayout.addWidget(self.mainLabel)
        mainLayout.addWidget(self.calButton)
        mainLayout.addWidget(self.loadButton)
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.goButton)
        mainLayout.addWidget(self.statusLabel)
        self.setLayout(mainLayout)

        # connections
        self.calButton.clicked.connect(self.launchCalibrationDialog)
        self.loadButton.clicked.connect(self.load)
        self.saveButton.clicked.connect(self.save)
        self.goButton.clicked.connect(self.triangulate)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def triangulate(self):

        if not (self.model.calibration and self.model.lcorr and self.model.rcorr):
            self.msgPosted.emit('Error: please load a calibration, and select '
                                'correspondence points before attempting triangulation')
            return

        x,y,z = self.model.triangulate()
        self.msgPosted.emit('Reconstructed object point: (%f, %f, %f)' % (x,y,z))

    def launchCalibrationDialog(self):
        dlg = CalibrationDialog(self.model)
        if dlg.exec_():
            self.model.setCalStage(dlg.getStage())
            if dlg.intrinsicsFromFile():
                #cal.setInitialIntrinsics(mtx, mtx2, mtx3, mtx4)
                print('TODO intrinsics from file')
                return
            self.model.calFinished.connect(self.updateStatus)
            self.model.startCalibration()

    def load(self):
        filename = QFileDialog.getOpenFileName(self, 'Load calibration file', '.',
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            self.model.loadCalibration(filename)
            self.updateStatus()

    def save(self):

        if not self.model.calibration:
            self.msgPosted.emit('Error: no calibration loaded')
            return

        filename = QFileDialog.getSaveFileName(self, 'Save calibration file', '.',
                                                'Pickle files (*.pkl)')[0]
        if filename:
            self.model.saveCalibration(filename)
            self.msgPosted.emit('Saved calibration to: %s' % filename)

    def updateStatus(self):
        if self.model.calibration:
            self.statusLabel.setText('Calibration is loaded.')
        else:
            self.statusLabel.setText('No calibration loaded.')


