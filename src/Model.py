#!/usr/bin/python3

import PySpin
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, QThread, pyqtSignal

import numpy as np
import os
import pickle
import socket

from Camera import Camera
from Stage import Stage
from Calibration import Calibration
from CalibrationWorker import CalibrationWorker
from lib import *
from Helper import *

from Dialogs import ScanStageDialog


class ScanStageWorker_new(QObject):
    finished = pyqtSignal()
    progressMade = pyqtSignal(str)

    def __init__(self, subnet, parent=None):
        QObject.__init__(self)
        """
        subnet is a tuple: (byte1, byte2, byte3)
        """
        self.b1 = subnet[0]
        self.b2 = subnet[1]
        self.b3 = subnet[2]

        self.stages = []

    def run(self):
        self.stages = []
        socket.setdefaulttimeout(0.020)  # 20 ms timeout
        for i in range(1,256):
            ip = '%d.%d.%d.%d' % (self.b1, self.b2, self.b3, i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
                s.close()
            else:
                self.stages.append((ip, Stage(s)))
            self.progressMade.emit(ip)
        self.finished.emit()


class Model(QObject):
    stageScanFinished = pyqtSignal()
    cameraScanFinished = pyqtSignal()
    calFinished = pyqtSignal()
    calPointReached = pyqtSignal()
    msgPosted = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)

        self.initCameras()
        self.initStages()

        self.calibration = None
        self.lcorr, self.rcorr = False, False

        self.objPoint_last = None

    def triangulate(self):
        objPoint = self.calibration.triangulate(self.lcorr, self.rcorr)
        self.objPoint_last = objPoint
        return objPoint # x,y,z

    def setCalibration(self, calibration):
        self.calibration = calibration

    def saveCalibration(self, filename):
        if not self.calibration:
            self.msgPosted.emit('No calibration loaded.')
            return
        with open(filename, 'wb') as f:
            pickle.dump(self.calibration, f)

    def loadCalibration(self, filename):
        with open(filename, 'rb') as f:
            self.calibration = pickle.load(f)
        x,y,z = self.calibration.getOrigin()
        self.msgPosted.emit('Calibration loaded, with origin = '
                            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))

    def setLcorr(self, xc, yc):
        self.lcorr = [xc, yc]

    def clearLcorr(self):
        self.lcorr = False

    def setRcorr(self, xc, yc):
        self.rcorr = [xc, yc]

    def clearRcorr(self):
        self.rcorr = False

    def registerCorrPoints_cal(self):
        if (self.lcorr and self.rcorr):
            self.imgPoints1_cal.append(self.lcorr)
            self.imgPoints2_cal.append(self.rcorr)
            self.msgPosted.emit('Correspondence points registered: (%d,%d) and (%d,%d)' % \
                                    (self.lcorr[0],self.lcorr[1],self.rcorr[0], self.rcorr[1]))
            self.calWorker.carryOn()
        else:
            self.msgPosted.emit('Highlight correspondence points and press C to continue')

    def initCameras(self):
        self.pyspin_instance = PySpin.System.GetInstance()
        self.pyspin_cameras = self.pyspin_instance.GetCameras()
        self.cameras = {}
        self.ncameras = 0

    def initStages(self):
        self.stages = {}
        self.calStage = None

    def scanForCameras(self):
        self.initCameras()
        self.pyspin_cameras = self.pyspin_instance.GetCameras()
        self.ncameras = self.pyspin_cameras.GetSize()
        for i in range(self.ncameras):
            self.cameras[i] = Camera(self.pyspin_cameras.GetByIndex(i))

    def scanForStages(self):
        dlg = ScanStageDialog()
        if dlg.exec_():
            self.initStages()
            self.scanThread = QThread()
            self.scanWorker = ScanStageWorker_new(dlg.subnetWidget.getSubnet())
            self.scanWorker.moveToThread(self.scanThread)
            self.scanThread.started.connect(self.scanWorker.run)
            self.scanWorker.finished.connect(self.scanThread.quit)
            self.scanWorker.finished.connect(self.scanWorker.deleteLater)
            self.scanThread.finished.connect(self.scanThread.deleteLater)
            self.scanThread.finished.connect(self.handleStageScanFinished)
            self.scanWorker.progressMade.connect(self.reportStageScanProgress)
            self.scanThread.start()

    def handleStageScanFinished(self):
        for item in self.scanWorker.stages:
            ip, stage = item
            self.addStage(ip, stage)

    def reportStageScanProgress(self, s):
        print('Scanning: ', s)

    def addStage(self, ip, stage):
        self.stages[ip] = stage

    def setCalStage(self, stage):
        self.calStage = stage

    def startCalibration(self, resolution, extent_um):
        self.imgPoints1_cal = []
        self.imgPoints2_cal = []
        self.calThread = QThread()
        self.calWorker = CalibrationWorker(self.calStage, resolution, extent_um)
        self.calWorker.moveToThread(self.calThread)
        self.calThread.started.connect(self.calWorker.run)
        self.calWorker.calibrationPointReached.connect(self.handleCalPointReached)
        self.calThread.finished.connect(self.handleCalFinished)
        self.calWorker.finished.connect(self.calThread.quit)
        self.calWorker.finished.connect(self.calWorker.deleteLater)
        self.calThread.finished.connect(self.calThread.deleteLater)
        self.msgPosted.emit('Starting Calibration...')
        self.calThread.start()

    def handleCalPointReached(self, n, numCal, x,y,z):
        self.msgPosted.emit('Calibration point %d (of %d) reached: [%f, %f, %f]' % (n+1,numCal, x,y,z))
        self.msgPosted.emit('Highlight correspondence points and press C to continue')
        self.calPointReached.emit()

    def handleCalFinished(self):
        self.calibration = Calibration()
        imgPoints1_cal = np.array([self.imgPoints1_cal], dtype=np.float32)
        imgPoints2_cal = np.array([self.imgPoints2_cal], dtype=np.float32)
        objPoints_cal = self.calWorker.getObjectPoints()
        origin = self.calWorker.stage.getOrigin()
        self.calibration.calibrate(imgPoints1_cal, imgPoints2_cal, objPoints_cal, origin)
        self.msgPosted.emit('Calibration finished. RMSE1 = %f, RMSE2 = %f' % \
                                (self.calibration.rmse1, self.calibration.rmse2))
        self.calFinished.emit()

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

    def haltAllStages(self):
        for stage in self.stages.values():
            stage.halt()
        self.msgPosted.emit('Halting all stages.')


if __name__ == '__main__':
    model = Model()
    model.scanCameras()
    print('ncameras = ', model.ncameras)
    model.clean()

