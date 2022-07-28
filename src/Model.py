#!/usr/bin/python3

import PySpin
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, QThread, pyqtSignal

import numpy as np

from Camera import Camera
from Stage import Stage
from lib import *


class Model(QObject):
    stageScanFinished = pyqtSignal()
    cameraScanFinished = pyqtSignal()
    msgPosted = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)

        self.initCameras()
        self.initStages()

        self.intrinsicsLoaded = False
        self.calLoaded = False
        self.lcorr, self.rcorr = False, False

    def setIntrinsics(self, mtx1, mtx2, dist1, dist2):

        self.imtx1 = mtx1
        self.imtx2 = mtx2
        self.idist1 = dist1
        self.idist2 = dist2

        self.intrinsicsLoaded = True

    def setCalibration(self, mtx1, mtx2, dist1, dist2, proj1, proj2):
        
        self.mtx1 = mtx1
        self.mtx2 = mtx2
        self.dist1 = dist1
        self.dist2 = dist2
        self.proj1 = proj1
        self.proj2 = proj2

        self.calLoaded = True

    def setLcorr(self, xc, yc):
        self.lcorr = [xc, yc]

    def setRcorr(self, xc, yc):
        self.rcorr = [xc, yc]

    def triangulate(self):

        if not (self.lcorr and self.rcorr):
            self.msgPosted.emit('Error: please select corresponding points in both frames to triangulate')
            return

        if not self.calLoaded:
            self.msgPosted.emit('Error: please run calibration or load previous')
            return

        imgPoints1 = np.array([[self.lcorr]], dtype=np.float32)
        imgPoints2 = np.array([[self.rcorr]], dtype=np.float32)

        # undistort
        imgPoints1 = undistortImagePoints(imgPoints1, self.mtx1, self.dist1)
        imgPoints2 = undistortImagePoints(imgPoints2, self.mtx2, self.dist2)

        imgPoint1 = imgPoints1[0,0]
        imgPoint2 = imgPoints2[0,0]
        objPoint_recon = triangulateFromImagePoints(imgPoint1, imgPoint2, self.proj1, self.proj2)
        x,y,z = objPoint_recon
        self.msgPosted.emit('Reconstructed object point: (%f, %f, %f)' % (x,y,z))

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

