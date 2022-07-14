from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtGui import QPainter, QPixmap, QImage
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import PySpin
import time, datetime
import numpy as np
import cv2 as cv

import socket
socket.setdefaulttimeout(0.020)  # 20 ms timeout

from Helper import *
import State
from Camera import Camera
from Stage import Stage
from ScreenWidget import ScreenWidget
from IntrinsicsPanel import IntrinsicsPanel
from ExtrinsicsPanel import ExtrinsicsPanel
from ReconstructionPanel import ReconstructionPanel


class ProbeTrackingTab(QWidget):

    def __init__(self, msgLog):
        QWidget.__init__(self)

        self.msgLog = msgLog
        self.ncameras = 0
        self.initGui()
        self.lastImage = None 
        self.initialized = False

        self.lcorrs = []
        self.rcorrs = []

    def initGui(self):

        mainLayout = QVBoxLayout()

        self.screens = QWidget()
        hlayout = QHBoxLayout()
        self.lscreen = ScreenWidget()
        self.rscreen = ScreenWidget()
        hlayout.addWidget(self.lscreen)
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        self.controls = QWidget()
        hlayout = QHBoxLayout()
        self.intrinsicsPanel = IntrinsicsPanel(self.msgLog)
        self.extrinsicsPanel = ExtrinsicsPanel(self.msgLog, self.intrinsicsPanel)
        self.reconstructionPanel = ReconstructionPanel(self.msgLog, self.extrinsicsPanel)
        hlayout.addWidget(self.intrinsicsPanel)
        hlayout.addWidget(self.extrinsicsPanel)
        hlayout.addWidget(self.reconstructionPanel)
        self.controls.setLayout(hlayout)

        self.initButton = QPushButton('Initialize Peripherals')
        self.initButton.clicked.connect(self.initialize)

        self.captureButton = QPushButton('Take Snapshot')
        self.captureButton.clicked.connect(self.capture)

        self.saveButton = QPushButton('Save Snapshot')
        self.saveButton.clicked.connect(self.save)

        self.extrinsicsPanel.snapshotRequested.connect(self.capture)
        self.reconstructionPanel.snapshotRequested.connect(self.capture)

        mainLayout.addWidget(self.initButton)
        mainLayout.addWidget(self.captureButton)
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.controls)

        self.setLayout(mainLayout)

    def initialize(self):

        # for idempotency
        if not self.initialized:
            # stage
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('10.128.49.22', PORT_NEWSCALE))
            self.stage = Stage(sock)
            self.stage.initialize()
            self.stage.center()
            self.extrinsicsPanel.setStage(self.stage)
            self.reconstructionPanel.setStage(self.stage)
            # cameras
            self.instance = PySpin.System.GetInstance()
            self.cameras_pyspin = self.instance.GetCameras()
            self.lcamera = Camera(self.cameras_pyspin.GetByIndex(0))
            self.rcamera = Camera(self.cameras_pyspin.GetByIndex(1))
            self.extrinsicsPanel.setScreens(self.lscreen, self.rscreen)
            self.reconstructionPanel.setScreens(self.lscreen, self.rscreen)
            # ok
            self.initialized = True
            self.msgLog.post('Cameras and Stage initialized')

        self.capture()

    def clean(self):

        if (self.initialized):
            print('cleaning up SpinSDK')
            time.sleep(1)
            self.lcamera.clean()
            self.rcamera.clean()
            self.cameras_pyspin.Clear()
            self.instance.ReleaseInstance()

    def reconstruct(self):

        lcorr = (self.lscreen.xclicked * 8, self.lscreen.yclicked * 8)
        rcorr = (self.rscreen.xclicked * 8, self.rscreen.yclicked * 8)

        x,y,z = DLT(self.lproj, self.rproj, lcorr, rcorr)
        self.msgLog.post('Reconstructed position: (%f, %f, %f) mm' % (x,y,z))

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

        # "tuple of length 1" to facilitate direct conversion to the proper numpy shape
        self.lcorrs.append(((self.lscreen.xclicked*CONVERSION_PX, self.lscreen.yclicked*CONVERSION_PX),))
        self.rcorrs.append(((self.rscreen.xclicked*CONVERSION_PX, self.rscreen.yclicked*CONVERSION_PX),))
        self.calWorker.carryOn()

    def carryOn(self):
        self.calWorker.carryOn()

    """

    def calibrate(self):

        self.initialize()
        self.calThread = QThread()
        self.calWorker = CalibrationWorker(self.stage)
        self.calWorker.moveToThread(self.calThread)
        self.calThread.started.connect(self.calWorker.run)
        self.calWorker.finished.connect(self.calThread.quit)
        self.calWorker.finished.connect(self.calWorker.deleteLater)
        self.calWorker.calibrationPointReached.connect(self.handleCalPointReached)
        self.calThread.finished.connect(self.calThread.deleteLater)
        self.calThread.finished.connect(self.handleCalFinished)
        self.imagePointsSelected.connect(self.calWorker.carryOn)
        self.msgLog.post('Starting Calibration...')
        self.calThread.start()

    def handleCalPointReached(self, n, x,y,z):

        self.msgLog.post('Calibration point %d reached (%f, %f, %f)' % (n,x,y,z))
        self.capture()
        tag = "x{0:.2f}_y{1:.2f}_z{2:.2f}".format(x,y,z)
        self.save(tag=tag)
        self.msgLog.post('Click "Continue with Calibration"')


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

    """

    def capture(self):

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

    def save(self, tag=None):

        if not tag:
            tag = self.lastStrTime

        image_converted = self.lcamera.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'lcamera_%s.png' % tag
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

        image_converted = self.rcamera.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'rcamera_%s.png' % tag
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

