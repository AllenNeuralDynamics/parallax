from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt


import numpy as np
import time
 
from Helper import *
from lib import *


class ReconstructionPanel(QFrame):
    snapshotRequested = pyqtSignal()

    def __init__(self, msgLog, extrinsicsPanel):
        QFrame.__init__(self)
        self.msgLog = msgLog
        self.extrinsicsPanel = extrinsicsPanel

        # layout
        mainLayout = QVBoxLayout()
        self.mainLabel = QLabel('Reconstruction')
        self.mainLabel.setAlignment(Qt.AlignCenter)
        self.mainLabel.setFont(FONT_BOLD)
        self.moveRandomButton = QPushButton('Move to a random position')
        self.moveGivenButton = QPushButton('Move to a given position')
        self.moveGivenButton.setEnabled(False)
        self.triangulateButton = QPushButton('Triangulate Points')
        self.triangulateButton.setEnabled(False)
        self.statusLabel = QLabel('Correspondence Points: None')
        self.statusLabel.setAlignment(Qt.AlignCenter)
        self.statusLabel.setFont(FONT_BOLD)
        mainLayout.addWidget(self.mainLabel)
        mainLayout.addWidget(self.moveRandomButton)
        mainLayout.addWidget(self.moveGivenButton)
        mainLayout.addWidget(self.triangulateButton)
        mainLayout.addWidget(self.statusLabel)
        self.setLayout(mainLayout)

        # connections
        self.moveRandomButton.clicked.connect(self.moveRandom)
        self.moveGivenButton.clicked.connect(self.moveGiven)
        self.triangulateButton.clicked.connect(self.triangulate)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def setStage(self, stage):
        self.stage = stage

    def setScreens(self, lscreen, rscreen):
        self.lscreen = lscreen
        self.rscreen = rscreen
        self.triangulateButton.setEnabled(True)

    def moveRandom(self):
    
        x = np.random.uniform(-2., 2.)
        y = np.random.uniform(-2., 2.)
        z = np.random.uniform(-2., 2.)
        self.stage.moveToTarget_mm3d(x, y, z)
        time.sleep(3)
        self.msgLog.post('Moved to a random position: (%f, %f, %f) mm' % (x, y, z))
        self.snapshotRequested.emit()

    def moveGiven(self):
    
        pass # TODO pop up dialog

    def triangulate(self):
        lcorr = self.lscreen.getSelected()
        rcorr = self.rscreen.getSelected()
        if not (lcorr and rcorr):
            self.msgLog.post('Error: please select corresponding points in both frames to triangulate')
            return

        mtx1, mtx2, dist1, dist2, proj1, proj2 = self.extrinsicsPanel.getExtrinsics()

        imgPoints1 = np.array([[lcorr]], dtype=np.float32)
        imgPoints2 = np.array([[rcorr]], dtype=np.float32)

        # undistort
        imgPoints1 = undistortImagePoints(imgPoints1, mtx1, dist1)
        imgPoints2 = undistortImagePoints(imgPoints2, mtx2, dist2)

        imgPoint1 = imgPoints1[0,0]
        imgPoint2 = imgPoints2[0,0]
        objPoint_recon = triangulateFromImagePoints(imgPoint1, imgPoint2, proj1, proj2)
        x,y,z = objPoint_recon
        self.msgLog.post('Reconstructed object point: (%f, %f, %f)' % (x,y,z))
