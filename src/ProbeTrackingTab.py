from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPixmap, QImage
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import PySpin
import time, datetime
import numpy as np
import cv2 as cv

import socket
socket.setdefaulttimeout(0.020)  # 20 ms timeout

import State
from Camera import Camera
from Stage import Stage
from ScreenWidget import ScreenWidget
from CalibrationWorker import CalibrationWorker
from Helper import *

class ProbeTrackingTab(QWidget):
    imagePointsSelected = pyqtSignal()

    def __init__(self, msgLog):
        QWidget.__init__(self)

        self.msgLog = msgLog
        self.ncameras = 0
        self.initGui()
        self.lastImage = None 
        self.initialized = False

        self.lcorrs = []
        self.rcorrs = []

    def initialize(self):
        # this function is idempotent

        if not self.initialized:
            self.lcamera = State.CAMERAS[0]
            self.rcamera = State.CAMERAS[1]
            self.stage = State.STAGES[0]
            self.initialized = True

    def quickInit(self):

        # stage
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('10.128.49.22', 23))
        self.stage = Stage(sock)
        self.stage.initialize()
        self.stage.center()
        # cameras
        self.instance = PySpin.System.GetInstance()
        self.cameras_pyspin = self.instance.GetCameras()
        self.lcamera = Camera(self.cameras_pyspin.GetByIndex(0))
        self.rcamera = Camera(self.cameras_pyspin.GetByIndex(1))
        self.initialized = True
        self.msgLog.post('Cameras and Stage initialized')


    def clean(self):

        if (self.initialized):
            print('cleaning up SpinSDK')
            time.sleep(1)
            self.lcamera.clean()
            self.rcamera.clean()
            self.cameras_pyspin.Clear()
            self.instance.ReleaseInstance()

    def initGui(self):

        mainLayout = QVBoxLayout()

        self.screens = QWidget()
        hlayout = QHBoxLayout()
        self.lscreen = ScreenWidget()
        hlayout.addWidget(self.lscreen)
        self.rscreen = ScreenWidget()
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        self.quickInitButton = QPushButton('Quick Init')
        self.quickInitButton.clicked.connect(self.quickInit)

        self.captureButton = QPushButton('Capture Frames')
        self.captureButton.clicked.connect(self.capture)

        self.saveButton = QPushButton('Save Last Frame')
        self.saveButton.clicked.connect(self.save)

        self.calibrateButton = QPushButton('Calibrate')
        self.calibrateButton.clicked.connect(self.calibrate)

        self.registerButton = QPushButton('Register')
        self.registerButton.clicked.connect(self.registerCorrespondencePoints)

        self.checkerboardButton = QPushButton('Do Checkerboards')
        self.checkerboardButton.clicked.connect(self.doCheckerboards)

        self.randomButton = QPushButton('Move to a Random Position')
        self.randomButton.clicked.connect(self.moveToRandomPosition)

        self.reconstructButton = QPushButton('Reconstruct Correspondence Point')
        self.reconstructButton.clicked.connect(self.reconstruct)

        mainLayout.addWidget(self.quickInitButton)
        mainLayout.addWidget(self.captureButton)
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.checkerboardButton)
        mainLayout.addWidget(self.calibrateButton)
        mainLayout.addWidget(self.registerButton)
        mainLayout.addWidget(self.randomButton)
        mainLayout.addWidget(self.reconstructButton)

        self.setLayout(mainLayout)

    def reconstruct(self):

        lcorr = (self.lscreen.xclicked * 8, self.lscreen.yclicked * 8)
        rcorr = (self.rscreen.xclicked * 8, self.rscreen.yclicked * 8)

        x,y,z = DLT(self.lproj, self.rproj, lcorr, rcorr)
        self.msgLog.post('Reconstructed position: (%f, %f, %f) mm' % (x,y,z))

    def moveToRandomPosition(self):
    
        x = np.random.uniform(-7.5, 7.5)
        y = np.random.uniform(-7.5, 7.5)
        z = np.random.uniform(-7.5, 7.5)
        self.stage.moveToTarget_mm3d(x, y, z)
        time.sleep(2)
        self.msgLog.post('Moved to a random position: (%f, %f, %f) mm' % (x, y, z))

    def doCheckerboards(self):

        self.ldata = self.lcamera.getLastImageData()
        self.lret, self.lcorners = cv.findChessboardCorners(self.ldata, (NCW,NCH), None)
        if self.lret:
            self.lscreen.setData(cv.drawChessboardCorners(self.ldata, (NCW,NCH), self.lcorners, self.lret))
            self.msgLog.post('left checkerboard found')
        else:
            self.msgLog.post('Checkerboard corners not found in left frame')

        self.rdata = self.rcamera.getLastImageData()
        self.rret, self.rcorners = cv.findChessboardCorners(self.rdata, (NCW,NCH), None)
        if self.rret:
            self.rscreen.setData(cv.drawChessboardCorners(self.rdata, (NCW,NCH), self.rcorners, self.rret))
            self.msgLog.post('right checkerboard found')
        else:
            self.msgLog.post('Checkerboard corners not found in right frame')

        if self.lret and self.rret:
            self.lmtx, self.ldist = getIntrinsicsFromCheckerboard(self.lcorners)
            self.rmtx, self.rdist = getIntrinsicsFromCheckerboard(self.rcorners)
        else:
            self.msgLog.post('Error: intrinsics could not be calculated for both cameras')

    def registerCorrespondencePoints(self):

        # weird "tuple of length 1" thing to facilitate direct conversion to the proper numpy shape
        self.lcorrs.append(((self.lscreen.xclicked*CONVERSION_PX, self.lscreen.yclicked*CONVERSION_PX),))
        self.rcorrs.append(((self.rscreen.xclicked*CONVERSION_PX, self.rscreen.yclicked*CONVERSION_PX),))
        self.calWorker.carryOn()

    def calibrate(self):

        self.initialize()
        self.calThread = QThread()
        self.calWorker = CalibrationWorker(self.stage)
        self.calWorker.moveToThread(self.calThread)
        self.calThread.started.connect(self.calWorker.run)
        self.calWorker.finished.connect(self.calThread.quit)
        self.calWorker.finished.connect(self.calWorker.deleteLater)
        self.calWorker.imagePointsRequested.connect(self.handleImagePoints)
        self.calThread.finished.connect(self.calThread.deleteLater)
        self.calThread.finished.connect(self.handleCalFinished)
        self.imagePointsSelected.connect(self.calWorker.carryOn)
        self.msgLog.post('Starting Calibration...')
        self.calThread.start()

    def handleImagePoints(self, step, nsteps):

        self.capture()
        self.msgLog.post('Calibration point reached (%d of %d)' % (step, nsteps))
        self.msgLog.post('Click on probe tip in both images, then press "Register"')

    def handleCalFinished(self):

        self.msgLog.post('Calibration finished.')

        objectPoints = self.calWorker.getObjectPoints()
        objectPoints = [np.array(objectPoints, dtype=np.float32)]

        limagepoints = [np.array(self.lcorrs, dtype=np.float32)]
        rimagepoints = [np.array(self.rcorrs, dtype=np.float32)]

        if (len(objectPoints[0]) != len(self.lcorrs)) or (len(self.rcorrs) != len(self.lcorrs)):
            self.msgLog.post('Error: number of object points does not match correspondence points')
            self.msgLog.post('Error: %d vs %d vs %d' %
                                (len(self.lcorrs), len(self.rcorrs), len(objectPoints[0])) )
            return

        self.lproj = getProjectionMatrix(objectPoints, limagepoints, self.lmtx, self.ldist)
        self.rproj = getProjectionMatrix(objectPoints, rimagepoints, self.rmtx, self.rdist)

    def capture(self):

        self.initialize()

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        strTime = '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.lastStrTime= strTime

        self.lcamera.capture()
        self.lscreen.setData(self.lcamera.getLastImageData())

        self.rcamera.capture()
        self.rscreen.setData(self.rcamera.getLastImageData())

        self.lscreen.repaint()
        self.rscreen.repaint()

    def save(self):

        image_converted = self.lcamera.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'lcamera_%s.png' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

        image_converted = self.rcamera.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'rcamera_%s.png' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

