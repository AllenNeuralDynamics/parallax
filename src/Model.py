#!/usr/bin/python3

import PySpin
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from Camera import Camera
from Stage import Stage


class Model(QObject):
    stageScanFinished = pyqtSignal()
    cameraScanFinished = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)

        self.initCameras()
        self.initStages()

    def initCameras(self):
        self.cameras = {}
        self.pyspin_instance = PySpin.System.GetInstance()
        self.pyspin_cameras = self.pyspin_instance.GetCameras()

    def initStages(self):
        self.stages = {}

    def scanForCameras(self):
        self.pyspin_cameras = self.pyspin_instance.GetCameras()
        self.ncameras = self.pyspin_cameras.GetSize()
        for i in range(self.ncameras):
            self.cameras[i] = Camera(self.pyspin_cameras.GetByIndex(i))

    def addStage(self, ip, stage):
        self.stages[ip] = stage

    def clean(self):
        self.cleanCameras()
        self.cleanStages()

    def cleanCameras(self):
        print('cleaning up SpinSDK')
        for camera in self.cameras.values():
            camera.clean()
        self.pyspin_cameras.Clear()
        self.pyspin_instance.ReleaseInstance()

    def cleanStages(self):
        pass


if __name__ == '__main__':
    model = Model()
    model.scanCameras()
    print('ncameras = ', model.ncameras)
    model.clean()

