from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import numpy as np

import State
import time

class CalibrationWorker(QObject):
    finished = pyqtSignal()
    imagePointsRequested = pyqtSignal(int, int)

    def __init__(self, stage, parent=None):
        QObject.__init__(self)
        self.stage = stage

        self.readyToGo = False

        self.objectPoints = []  # units are mm

    def carryOn(self):
        self.readyToGo = True

    def run(self):

        # +x
        self.stage.moveToTarget_mm3d(5,0,0)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(1, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([5,0,0], dtype=float))

        # -y
        self.stage.moveToTarget_mm3d(5,-5,0)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(2, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([5,-5,0], dtype=float))

        # +z
        self.stage.moveToTarget_mm3d(5,-5,5)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(3, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([5,-5,5], dtype=float))

        # +y
        self.stage.moveToTarget_mm3d(5,0,5)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(4, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([5,0,5], dtype=float))

        # -x
        self.stage.moveToTarget_mm3d(0,0,5)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(5, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([0,0,5], dtype=float))

        # -z
        self.stage.moveToTarget_mm3d(0,0,0)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(6, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([0,0,0], dtype=float))

        # -y
        self.stage.moveToTarget_mm3d(0,-5,0)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(7, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([0,-5,0], dtype=float))

        # +z
        self.stage.moveToTarget_mm3d(0,-5,5)
        time.sleep(2)
        self.readyToGo = False
        self.imagePointsRequested.emit(8, 8)
        while not self.readyToGo:
            time.sleep(0.1)
        self.objectPoints.append(np.array([0,-5,5], dtype=float))

        self.finished.emit()

    def getObjectPoints(self):
        return self.objectPoints

