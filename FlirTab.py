from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPixmap, QImage
from PyQt5.QtCore import QRect, Qt

import PySpin
import time, datetime
import numpy as np

xScreen = 1000
yScreen = 750

class ScreenWidget(QLabel):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setMinimumSize(xScreen, yScreen)
        self.setMaximumSize(xScreen, yScreen)

    def setData(self, data):
        # data should be a numpy array
        qimage = QImage(data, data.shape[1], data.shape[0], QImage.Format_Grayscale8)
        pixmap = QPixmap(qimage.scaled(xScreen, yScreen, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.setPixmap(pixmap)
        self.update()


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
        self.cameras = self.instance.GetCameras()
        self.ncameras = self.cameras.GetSize()
        ncameras_string = '%d camera%s detected' % (self.ncameras, 's' if self.ncameras!=1 else '')
        self.msgLog.post(ncameras_string)
        if not self.ncameras:
            return

        self.camera = self.cameras.GetByIndex(0)
        self.tldnm = self.camera.GetTLDeviceNodeMap()
        self.camera.Init()
        self.nodeMap = self.camera.GetNodeMap()

        # set BufferHandlingMode to NewestOnly (necessary to update the image)
        sNodemap = self.camera.GetTLStreamNodeMap()
        node_bufferhandling_mode = PySpin.CEnumerationPtr(sNodemap.GetNode('StreamBufferHandlingMode'))
        node_newestonly = node_bufferhandling_mode.GetEntryByName('NewestOnly')
        node_newestonly_mode = node_newestonly.GetValue()
        node_bufferhandling_mode.SetIntValue(node_newestonly_mode)

        # set gain
        node_gainauto_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode("GainAuto"))
        node_gainauto_mode_off = node_gainauto_mode.GetEntryByName("Off")
        node_gainauto_mode.SetIntValue(node_gainauto_mode_off.GetValue())
        node_gain = PySpin.CFloatPtr(self.nodeMap.GetNode("Gain"))
        node_gain.SetValue(25.0)

        # set exposure time
        node_expauto_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode("ExposureAuto"))
        node_expauto_mode_off = node_expauto_mode.GetEntryByName("Off")
        node_expauto_mode.SetIntValue(node_expauto_mode_off.GetValue())
        node_exptime = PySpin.CFloatPtr(self.nodeMap.GetNode("ExposureTime"))
        node_exptime.SetValue(1e5)

        # begin acquisition
        self.beginAcquisition()

        self.initialized = True
        self.msgLog.post('1 camera initialized')
        self.msgLog.post('FLIR Library Version is %s' % self.libVerString)

        self.captureButton.setEnabled(True)

    def clean(self):

        if (self.initialized):
            print('cleaning up SpinSDK')
            time.sleep(1)
            self.camera.EndAcquisition()
            del self.camera
            self.cameras.Clear()
            self.instance.ReleaseInstance()


    def initGui(self):

        mainLayout = QVBoxLayout()

        #bogusData = np.random.randint(255, size=(3000,4000), dtype=np.uint8)
        bogusData = np.zeros((3000,4000), dtype=np.uint8)

        self.screen = ScreenWidget()
        self.screen.setData(bogusData)

        self.initializeButton = QPushButton('Initialize Cameras')
        self.initializeButton.clicked.connect(self.initCameras)
        self.captureButton = QPushButton('Capture Frame')
        self.captureButton.setEnabled(False)
        self.captureButton.clicked.connect(self.capture)
        self.saveButton = QPushButton('Save Last Frame')
        self.saveButton.setEnabled(False)
        self.saveButton.clicked.connect(self.save)

        mainLayout.addWidget(self.initializeButton)
        mainLayout.addWidget(self.screen)
        mainLayout.addWidget(self.captureButton)
        mainLayout.addWidget(self.saveButton)

        self.setLayout(mainLayout)


    def beginAcquisition(self):

        # set acquisition mode continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode('AcquisitionMode'))
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        self.camera.BeginAcquisition()

        self.msgLog.post('Continuous acquisition has begun.')


    def capture(self):

        self.msgLog.post('capturing')

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        strTime = '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

        if self.lastImage:
            self.lastImage.Release()

        image = self.camera.GetNextImage(1000)
        while image.IsIncomplete():
            print('waiting')

        # then display to screen
        image_data = image.GetNDArray()
        self.screen.setData(image_data)

        self.lastImage = image
        self.lastStrTime= strTime
        self.saveButton.setEnabled(True)

    def save(self):

        image_converted = self.lastImage.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        filename = 'capture_%s.jpg' % self.lastStrTime
        image_converted.Save(filename)
        self.msgLog.post('Saved %s' % filename)


