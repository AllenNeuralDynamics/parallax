from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPixmap, QImage
from PyQt5.QtCore import Qt

import PySpin
import time, datetime
import numpy as np

from Camera import Camera

xScreen = 500
yScreen = 375


class ScreenWidget(QLabel):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setMinimumSize(xScreen, yScreen)
        self.setMaximumSize(xScreen, yScreen)
        self.setData(np.zeros((3000,4000), dtype=np.uint8))

    def setData(self, data):
        # data should be a numpy array
        qimage = QImage(data, data.shape[1], data.shape[0], QImage.Format_Grayscale8)
        pixmap = QPixmap(qimage.scaled(xScreen, yScreen, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.setPixmap(pixmap)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            print('click: %d, %d' % (e.x(), e.y()))


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
        if not self.ncameras:
            return

        ###

        self.cameras = []
        for i in range(2):
            self.cameras.append(Camera(self.cameras_pyspin.GetByIndex(i)))

        self.msgLog.post('FLIR Library Version is %s' % self.libVerString)

        self.captureButton.setEnabled(True)
        self.initialized = True

    def clean(self):

        if (self.initialized):
            print('cleaning up SpinSDK')
            time.sleep(1)
            for camera in self.cameras:
                camera.clean()
            self.cameras_pyspin.Clear()
            self.instance.ReleaseInstance()

    def initGui(self):

        mainLayout = QVBoxLayout()

        self.screens = QWidget()
        hlayout = QHBoxLayout()
        self.screen_l = ScreenWidget()
        hlayout.addWidget(self.screen_l)
        self.screen_r = ScreenWidget()
        hlayout.addWidget(self.screen_r)
        self.screens.setLayout(hlayout)

        self.initializeButton = QPushButton('Initialize Cameras')
        self.initializeButton.clicked.connect(self.initCameras)
        self.captureButton = QPushButton('Capture Frame')
        self.captureButton.setEnabled(False)
        self.captureButton.clicked.connect(self.capture)
        self.saveButton = QPushButton('Save Last Frame')
        self.saveButton.setEnabled(False)
        self.saveButton.clicked.connect(self.save)

        mainLayout.addWidget(self.initializeButton)
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.captureButton)
        mainLayout.addWidget(self.saveButton)

        self.setLayout(mainLayout)

    def capture(self):

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        strTime = '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.lastStrTime= strTime

        self.cameras[0].capture()
        self.screen_l.setData(self.cameras[0].getLastImageData())

        self.cameras[1].capture()
        self.screen_r.setData(self.cameras[1].getLastImageData())

        self.saveButton.setEnabled(True)

    def save(self):

        image_converted = self.cameras[0].getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'capture_l_%s.jpg' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

        image_converted = self.cameras[1].getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'capture_r_%s.jpg' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)

