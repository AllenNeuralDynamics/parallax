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

xScreen = 500
yScreen = 375


class FlirTab(QWidget):

    def __init__(self, msgLog):
        QWidget.__init__(self)

        self.msgLog = msgLog
        self.ncameras = 0
        self.initGui()
        self.initialized = False
        self.lastImage = None

    def initCameras(self):

        self.msgLog.post('Initializing cameras...')

        self.instance = PySpin.System.GetInstance()

        self.libVer = self.instance.GetLibraryVersion()
        self.libVerString = 'Version %d.%d.%d.%d' % (self.libVer.major, self.libVer.minor,
                                                    self.libVer.type, self.libVer.build)
        self.cameras_pyspin = self.instance.GetCameras()
        self.ncameras = self.cameras_pyspin.GetSize()

        ncameras_string = '%d camera%s detected' % (self.ncameras, 's' if self.ncameras!=1 else '')
        self.msgLog.post(ncameras_string)
        if self.ncameras < 2:
            print('Error: need at least 2 cameras')
            return

        ###

        for i in range(self.ncameras):
            State.CAMERAS.append(Camera(self.cameras_pyspin.GetByIndex(i)))

        self.lcamera = State.CAMERAS[0]
        self.rcamera = State.CAMERAS[1]

        self.msgLog.post('FLIR Library Version is %s' % self.libVerString)

        self.captureButton.setEnabled(True)
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
        hlayout.addWidget(self.lscreen)
        self.rscreen = ScreenWidget()
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        self.initializeButton = QPushButton('Initialize Cameras')
        self.initializeButton.clicked.connect(self.initCameras)

        self.captureButton = QPushButton('Capture Frames')
        self.captureButton.setEnabled(False)
        self.captureButton.clicked.connect(self.capture)

        self.saveButton = QPushButton('Save Last Frame')
        self.saveButton.setEnabled(False)
        self.saveButton.clicked.connect(self.save)

        mainLayout.addWidget(self.initializeButton)
        mainLayout.addWidget(self.captureButton)
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.screens)

        self.setLayout(mainLayout)

    def capture(self):

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        strTime = '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.lastStrTime= strTime

        self.lcamera.capture()
        self.lscreen.setData(self.lcamera.getLastImageData())

        self.rcamera.capture()
        self.rscreen.setData(self.rcamera.getLastImageData())

        self.saveButton.setEnabled(True)

    def save(self):

        image_converted = self.lcamera.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'lcamera_%s.png' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

        image_converted = self.rcamera.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'rcamera_%s.png' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

