from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import numpy as np
import time
 
from Helper import *
from lib import *
from TargetDialog import TargetDialog

class ReconstructionPanel(QFrame):
    snapshotRequested = pyqtSignal()
    msgPosted = pyqtSignal(str)

    def __init__(self):
        QFrame.__init__(self)

        # layout
        mainLayout = QVBoxLayout()
        self.mainLabel = QLabel('Reconstruction')
        self.mainLabel.setAlignment(Qt.AlignCenter)
        self.mainLabel.setFont(FONT_BOLD)
        self.triangulateButton = QPushButton('Triangulate Points')
        self.statusLabel = QLabel('Correspondence Points: None')
        self.statusLabel.setAlignment(Qt.AlignCenter)
        self.statusLabel.setFont(FONT_BOLD)
        mainLayout.addWidget(self.mainLabel)
        mainLayout.addWidget(self.triangulateButton)
        mainLayout.addWidget(self.statusLabel)
        self.setLayout(mainLayout)

        # connections
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

    def triangulate(self):
        lcorr = self.lscreen.getSelected()
        rcorr = self.rscreen.getSelected()
        if not (lcorr and rcorr):
            self.msgPosted.emit('Error: please select corresponding points in both frames to triangulate')
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
        self.msgPosted.emit('Reconstructed object point: (%f, %f, %f)' % (x,y,z))

