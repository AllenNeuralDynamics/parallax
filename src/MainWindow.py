from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMenu
from PyQt5.QtCore import Qt

from MessageLog import MessageLog
from ScreenWidget import ScreenWidget
from ControlPanel import ControlPanel
from CalibrationPanel import CalibrationPanel
from ReconstructionPanel import ReconstructionPanel
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
        self.lscreen = ScreenWidget(self.model)
        self.rscreen = ScreenWidget(self.model)
        hlayout.addWidget(self.lscreen)
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        self.controls = QWidget()
        self.controlPanel = ControlPanel(self.model)
        self.calPanel = CalibrationPanel()
        self.reconPanel = ReconstructionPanel()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.controlPanel)
        hlayout.addWidget(self.calPanel)
        hlayout.addWidget(self.reconPanel)
        self.controls.setLayout(hlayout)

        self.msgLog = MessageLog()
        self.controlPanel.msgPosted.connect(self.msgLog.post)
        self.calPanel.msgPosted.connect(self.msgLog.post)
        self.reconPanel.msgPosted.connect(self.msgLog.post)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.deviceManager)
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.controls)
        mainLayout.addWidget(self.msgLog)
        self.setLayout(mainLayout)

        self.setWindowTitle('MISGUIde')

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            self.lscreen.refresh()
            self.rscreen.refresh()
            e.accept()

    def exit(self):
        pass # TODO

