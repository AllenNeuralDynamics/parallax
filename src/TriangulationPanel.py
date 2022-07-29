from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtCore import QThread, Qt
from PyQt5.QtCore import QThread, pyqtSignal, Qt

from CalibrationWorker import CalibrationWorker
from lib import *
from Helper import *
from Dialogs import *

import os

class TriangulationPanel(QFrame):
    snapshotRequested = pyqtSignal()
    msgPosted = pyqtSignal(str)

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # layout
        mainLayout = QVBoxLayout()
        self.mainLabel = QLabel('Triangulation')
        self.mainLabel.setAlignment(Qt.AlignCenter)
        self.mainLabel.setFont(FONT_BOLD)
        self.calButton = QPushButton('Run Calibration')
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
        self.calButton.clicked.connect(self.startCalibration)
        self.loadButton.clicked.connect(self.load)
        self.saveButton.clicked.connect(self.save)
        self.goButton.clicked.connect(self.triangulate)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def triangulate(self):
        self.model.triangulate()

    def setStage(self, stage):

        self.stage = stage

    def startCalibration(self):

        self.calDialog = CalibrationDialog(self.model)
        self.calDialog.msgPosted.connect(self.msgPosted)
        self.calDialog.snapshotRequested.connect(self.snapshotRequested)
        self.calDialog.calDone.connect(self.updateStatus)
        self.calDialog.show()

    def load(self):

        filenames = QFileDialog.getOpenFileNames(self, 'Select extrinsics files', '.',
                                                    'Numpy files (*.npy)')
        if filenames[0]:
            self.loadExtrinsics(filenames[0])

    def loadExtrinsics(self, filenames):

        for filename in filenames:
            basename = os.path.basename(filename)
            if basename == 'ex_mtx1.npy':
                mtx1_ex = np.load(filename)
            elif basename == 'ex_mtx2.npy':
                mtx2_ex = np.load(filename)
            elif basename == 'ex_dist1.npy':
                dist1_ex = np.load(filename)
            elif basename == 'ex_dist2.npy':
                dist2_ex = np.load(filename)
            elif basename == 'ex_proj1.npy':
                proj1 = np.load(filename)
            elif basename == 'ex_proj2.npy':
                proj2 = np.load(filename)
        self.model.setCalibration(mtx1_ex, mtx2_ex, dist1_ex, dist2_ex, proj1, proj2)
        self.updateStatus()

    def save(self):

        if not self.model.calLoaded:
            self.msgPosted.emit('Error: extrinsics missing')
            return

        path = QFileDialog.getExistingDirectory(self, 'Save Extrinsics: '
                                                    'Choose Destination Folder', '.')
        if path:
            self.saveExtrinsics(path)

    def saveExtrinsics(self, path):
        self.model.saveCalibration()

    def updateStatus(self):

        if self.model.calLoaded:
            self.statusLabel.setText('Calibration loaded.')
        else:
            self.statusLabel.setText('Calibration needed.')

