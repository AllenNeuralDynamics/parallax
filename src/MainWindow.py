from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMenu
from PyQt5.QtCore import Qt, QTimer

from MessageLog import MessageLog
from ScreenWidget import ScreenWidget
from ControlPanel import ControlPanel
from TriangulationPanel import TriangulationPanel
from StageManager import StageManager
from CameraManager import CameraManager

import time


class MainWindow(QWidget):

    def __init__(self, model, parent=None):
        QWidget.__init__(self) 
        self.model = model

        self.deviceManager = QWidget()
        hlayout = QHBoxLayout()
        self.cameraManager = CameraManager(self.model)
        self.stageManager = StageManager(self.model)
        hlayout.addWidget(self.cameraManager)
        hlayout.addWidget(self.stageManager)
        self.deviceManager.setLayout(hlayout)

        self.screens = QWidget()
        hlayout = QHBoxLayout()
        self.lscreen = ScreenWidget(model=self.model)
        self.rscreen = ScreenWidget(model=self.model)
        hlayout.addWidget(self.lscreen)
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        self.controls = QWidget()
        self.controlPanel1 = ControlPanel(self.model)
        self.controlPanel2 = ControlPanel(self.model)
        self.triPanel = TriangulationPanel(self.model)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.controlPanel1)
        hlayout.addWidget(self.triPanel)
        hlayout.addWidget(self.controlPanel2)
        self.controls.setLayout(hlayout)

        self.refreshTimer = QTimer()
        self.refreshTimer.timeout.connect(self.refresh)
        self.refreshTimer.start(250)

        # connections
        self.msgLog = MessageLog()
        self.controlPanel1.msgPosted.connect(self.msgLog.post)
        self.controlPanel2.msgPosted.connect(self.msgLog.post)
        self.controlPanel1.targetReached.connect(self.zoomOut)
        self.controlPanel2.targetReached.connect(self.zoomOut)
        self.triPanel.msgPosted.connect(self.msgLog.post)
        self.model.calPointReached.connect(self.clearSelected)
        self.model.calPointReached.connect(self.zoomOut)
        self.model.msgPosted.connect(self.msgLog.post)
        self.lscreen.selected.connect(self.model.setLcorr)
        self.lscreen.cleared.connect(self.model.clearLcorr)
        self.rscreen.selected.connect(self.model.setRcorr)
        self.rscreen.cleared.connect(self.model.clearRcorr)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.deviceManager)
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.controls)
        mainLayout.addWidget(self.msgLog)
        self.setLayout(mainLayout)

        self.setWindowTitle('MISGUIde')

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            if (e.modifiers() & Qt.ControlModifier):
                self.clearSelected()
                self.zoomOut()
                e.accept()
        elif e.key() == Qt.Key_S:
            if (e.modifiers() & Qt.ControlModifier):
                self.saveCameraFrames()
                e.accept()
        elif e.key() == Qt.Key_C:
            self.model.registerCorrPoints_cal()
        elif e.key() == Qt.Key_Escape:
            self.model.haltAllStages()

    def refresh(self):
        self.lscreen.refresh()
        self.rscreen.refresh()

    def clearSelected(self):
        self.lscreen.clearSelected()
        self.rscreen.clearSelected()

    def zoomOut(self):
        self.lscreen.zoomOut()
        self.rscreen.zoomOut()

    def saveCameraFrames(self):
        for i,camera in enumerate(self.model.cameras.values()):
            if camera.lastImage:
                filename = 'camera%d_%s.png' % (i, camera.getLastCaptureTime())
                camera.saveLastImage(filename)
                self.msgLog.post('Saved camera frame: %s' % filename)

    def exit(self):
        pass # TODO

