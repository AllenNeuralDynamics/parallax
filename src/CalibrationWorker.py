from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import numpy as np

import time

class CalibrationWorker(QObject):
    finished = pyqtSignal()
    calibrationPointReached = pyqtSignal(int, int, float, float, float)

    def __init__(self, stage, stepsPerDim=3, extent_um=2000, parent=None):
        # stepsPerDim is steps per dimension, for 3 dimensions
        # (so default value of 3 will yield 3^3 = 27 calibration points)
        # extent_um is the extent in microns for each dimension, centered on zero
        QObject.__init__(self)
        self.stage = stage
        self.stepsPerDim = stepsPerDim
        self.extent_um = extent_um

        self.readyToGo = False
        self.objectPoints = []  # units are mm
        self.numCal = self.stepsPerDim**3

    def carryOn(self):
        self.readyToGo = True

    def run(self):

        n = 0
        mx =  self.extent_um / 2.
        mn =  (-1) * mx
        #mx = 7500 + self.extent_um / 2.
        #mn = 7500 - self.extent_um / 2.
        for x in np.linspace(mn, mx, self.stepsPerDim):
            for y in np.linspace(mn, mx, self.stepsPerDim):
                for z in np.linspace(mn, mx, self.stepsPerDim):
                    self.stage.moveToTarget3d_rel(x,y,z)
                    self.calibrationPointReached.emit(n,self.numCal, x,y,z)
                    self.readyToGo = False
                    while not self.readyToGo:
                        time.sleep(0.1)
                    self.objectPoints.append([x,y,z])
                    n += 1

        self.finished.emit()

    def getObjectPoints(self):
        return np.array([self.objectPoints], dtype=np.float32)

