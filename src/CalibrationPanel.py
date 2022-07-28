from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtCore import QThread, Qt
from PyQt5.QtCore import QThread, pyqtSignal, Qt

from CalibrationWorker import CalibrationWorker
from lib import *
from Helper import *

import os

class CalibrationPanel(QFrame):
    snapshotRequested = pyqtSignal()
    msgPosted = pyqtSignal(str)

    def __init__(self):
        QFrame.__init__(self)

        # layout
        mainLayout = QVBoxLayout()
        self.mainLabel = QLabel('Calibration')
        self.mainLabel.setAlignment(Qt.AlignCenter)
        self.mainLabel.setFont(FONT_BOLD)
        self.startButton = QPushButton('Start Calibration Procedure')
        self.registerButton = QPushButton('Register Correspondence Points')
        self.loadButton = QPushButton('Load')
        self.saveButton = QPushButton('Save')
        self.statusLabel = QLabel('Cached: None')
        self.statusLabel.setAlignment(Qt.AlignCenter)
        self.statusLabel.setFont(FONT_BOLD)
        mainLayout.addWidget(self.mainLabel)
        mainLayout.addWidget(self.startButton)
        mainLayout.addWidget(self.registerButton)
        mainLayout.addWidget(self.loadButton)
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.statusLabel)
        self.setLayout(mainLayout)

        # connections
        self.startButton.clicked.connect(self.startCalibration)
        self.loadButton.clicked.connect(self.load)
        self.saveButton.clicked.connect(self.save)
        self.registerButton.clicked.connect(self.register)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def setStage(self, stage):

        self.stage = stage

    def setScreens(self, lscreen, rscreen):

        self.lscreen = lscreen
        self.rscreen = rscreen

    def startCalibration(self):

        try:
            self.mtx1_in, self.mtx2_in, self.dist1_in, self.dist2_in = self.intrinsicsPanel.getIntrinsics()
        except AttributeError:
            self.msgPosted.emit('Error: No intrinsics loaded.')
            return

        self.imgPoints1_cal = []
        self.imgPoints2_cal = []
        self.calThread = QThread()
        self.calWorker = CalibrationWorker(self.stage, stepsPerDim=2)
        self.calWorker.moveToThread(self.calThread)
        self.calThread.started.connect(self.calWorker.run)
        self.calWorker.finished.connect(self.calThread.quit)
        self.calWorker.finished.connect(self.calWorker.deleteLater)
        self.calWorker.calibrationPointReached.connect(self.handleCalPointReached)
        self.calThread.finished.connect(self.calThread.deleteLater)
        self.calThread.finished.connect(self.handleCalFinished)
        self.msgPosted.emit('Starting Calibration...')
        self.calThread.start()

    def register(self):

        lcorr = self.lscreen.getSelected()
        rcorr = self.rscreen.getSelected()
        self.imgPoints1_cal.append(lcorr)
        self.imgPoints2_cal.append(rcorr)
        self.msgPosted.emit('Registered correspondence points %s and %s' % (lcorr.__str__(),rcorr.__str__()))
        self.calWorker.carryOn()

    def handleCalPointReached(self, n, numCal, x,y,z):

        self.msgPosted.emit('Calibration point %d (of %d) reached: [%f, %f, %f]' % (n+1,numCal, x,y,z))
        self.snapshotRequested.emit()
        self.msgPosted.emit('Select correspondence points and click Register to continue')
        #tag = "x{0:.2f}_y{1:.2f}_z{2:.2f}".format(x,y,z)
        #self.save(tag=tag)

    def handleCalFinished(self):

        self.msgPosted.emit('Calibration finished')

        imgPoints1_cal = np.array([self.imgPoints1_cal], dtype=np.float32)
        imgPoints2_cal = np.array([self.imgPoints2_cal], dtype=np.float32)
        objPoints_cal = self.calWorker.getObjectPoints()

        # undistort calibration points
        imgPoints1_cal = undistortImagePoints(imgPoints1_cal, self.mtx1_in, self.dist1_in)
        imgPoints2_cal = undistortImagePoints(imgPoints2_cal, self.mtx2_in, self.dist2_in)

        # calibrate each camera against these points
        myFlags = cv.CALIB_USE_INTRINSIC_GUESS + cv.CALIB_FIX_PRINCIPAL_POINT
        rmse1, self.mtx1_ex, self.dist1_ex, rvecs1, tvecs1 = cv.calibrateCamera(objPoints_cal, imgPoints1_cal,
                                                                        (WF, HF), self.mtx1_in, self.dist1_in,
                                                                        flags=myFlags)
        rmse2, self.mtx2_ex, self.dist2_ex, rvecs2, tvecs2 = cv.calibrateCamera(objPoints_cal, imgPoints2_cal,
                                                                        (WF, HF), self.mtx2_in, self.dist2_in,
                                                                        flags=myFlags)

        # calculate projection matrices
        self.proj1 = getProjectionMatrix(self.mtx1_ex, rvecs1[0], tvecs1[0])
        self.proj2 = getProjectionMatrix(self.mtx2_ex, rvecs2[0], tvecs2[0])

        self.updateStatus()

    def load(self):

        filenames = QFileDialog.getOpenFileNames(self, 'Select intrinsics files', '.',
                                                    'Numpy files (*.npy)')
        if filenames[0]:
            self.loadExtrinsics(filenames[0])

    def loadExtrinsics(self, filenames):

        m1,m2,d1,d2,p1,p2 = False, False, False, False, False, False
        for filename in filenames:
            basename = os.path.basename(filename)
            if basename == 'ex_mtx1.npy':
                self.mtx1_ex = np.load(filename)
                m1 = True
            elif basename == 'ex_mtx2.npy':
                self.mtx2_ex = np.load(filename)
                m2 = True
            elif basename == 'ex_dist1.npy':
                self.dist1_ex = np.load(filename)
                d1 = True
            elif basename == 'ex_dist2.npy':
                self.dist2_ex = np.load(filename)
                d2 = True
            elif basename == 'ex_proj1.npy':
                self.proj1 = np.load(filename)
                p1 = True
            elif basename == 'ex_proj2.npy':
                self.proj2 = np.load(filename)
                p2 = True
        if m1 and m2 and d1 and d2 and p1 and p2:
            self.updateStatus()

    def save(self):

        path = QFileDialog.getExistingDirectory(self, 'Save Extrinsics: '
                                                    'Choose Destination Folder', '.')
        if path:
            self.saveExtrinsics(path)

    def saveExtrinsics(self, path):

        try:
            np.save(os.path.join(path, 'ex_mtx1.npy'), self.mtx1_ex)
            np.save(os.path.join(path, 'ex_mtx2.npy'), self.mtx2_ex)
            np.save(os.path.join(path, 'ex_dist1.npy'), self.dist1_ex)
            np.save(os.path.join(path, 'ex_dist2.npy'), self.dist2_ex)
            np.save(os.path.join(path, 'ex_proj1.npy'), self.proj1)
            np.save(os.path.join(path, 'ex_proj2.npy'), self.proj2)
        except AttributeError:
            self.msgPosted.emit('Error: extrinsics missing')

    def updateStatus(self):

        self.statusLabel.setText('Loaded: mtx1, mtx2, dist1, dist2, proj1, proj2')

    def getExtrinsics(self):

        return self.mtx1_ex, self.mtx2_ex, self.dist1_ex, self.dist2_ex, self.proj1, self.proj2

