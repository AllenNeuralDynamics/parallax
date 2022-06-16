from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPixmap, QImage
from PyQt5.QtCore import Qt

import PySpin
import time, datetime
import numpy as np
import cv2 as cv

from Camera import Camera
from ScreenWidget import ScreenWidget
import State

class ProbeTrackingTab(QWidget):

    def __init__(self, msgLog):
        QWidget.__init__(self)

        self.msgLog = msgLog
        self.ncameras = 0
        self.initGui()
        self.lastImage = None

        self.initialized = False

    def initialize(self):
        # this function is idempotent
        if not self.initialized:
            self.lcamera = State.CAMERAS[0]
            self.rcamera = State.CAMERAS[1]
            self.stage = State.STAGES[0]
            self.initialized = True

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
        self.lscreen.clicked.connect(self.handleScreenClicked)
        hlayout.addWidget(self.lscreen)
        self.rscreen = ScreenWidget()
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        self.captureButton = QPushButton('Capture Frames')
        self.captureButton.clicked.connect(self.capture)

        self.saveButton = QPushButton('Save Last Frame')
        self.saveButton.clicked.connect(self.save)

        self.calibrateButton = QPushButton('Calibrate')
        self.calibrateButton.clicked.connect(self.calibrate)

        mainLayout.addWidget(self.captureButton)
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.calibrateButton)

        self.setLayout(mainLayout)

    def handleScreenClicked(self, xClicked, yClicked):
        print(xClicked, yClicked)

    def calibrate(self):

        self.initialize()

        self.stage.selectAxis('x')
        self.stage.jogForward()
        time.sleep(1)
        self.capture()
        self.stage.selectAxis('y')
        self.stage.jogForward()
        time.sleep(1)
        self.capture()
        self.stage.selectAxis('z')
        self.stage.jogForward()
        time.sleep(1)
        self.capture()
        self.stage.selectAxis('x')
        self.stage.jogBackward()
        time.sleep(1)
        self.capture()
        self.stage.selectAxis('y')
        self.stage.jogBackward()
        time.sleep(1)
        self.capture()
        self.stage.selectAxis('z')
        self.stage.jogBackward()
        time.sleep(1)
        self.capture()

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
        filename = 'lcamera_%s.jpg' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

        image_converted = self.rcamera.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'rcamera_%s.jpg' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

