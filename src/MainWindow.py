from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMenu
from PyQt5.QtCore import Qt

"""
from FlirTab import FlirTab
from ZaberTab import ZaberTab
from NewScaleTab import NewScaleTab
from ProbeTrackingTab import ProbeTrackingTab
"""

from MessageLog import MessageLog
from ScreenWidget import ScreenWidget
from ControlPanel import ControlPanel
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
        self.c1 = ControlPanel(self.model)
        self.c2 = ControlPanel(self.model)
        self.c3 = ControlPanel(self.model)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.c1)
        hlayout.addWidget(self.c2)
        hlayout.addWidget(self.c3)
        self.controls.setLayout(hlayout)

        self.msgLog = MessageLog()
        self.c1.msgPosted.connect(self.msgLog.post)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.deviceManager)
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.controls)
        mainLayout.addWidget(self.msgLog)
        self.setLayout(mainLayout)

        self.setWindowTitle('MISGUIde')

    def mousePressEvent(self, e):
        if e.button == Qt.RightButton:
            contextMenu = QMenu(self)
            scanCamerasAction = contextMenu.addAction("Scan for Cameras")
            scanStagesAction = contextMenu.addAction("Scan for Stages")
            action = contextMenu.exec_(self.mapToGlobal(e.pos()))
            if action == scanCamerasAction:
                print('TODO: scan cameras')
            elif action == scanStagesAction:
                print('TODO: scan stages')
            e.accept()

    def exit(self):
        pass # TODO
        #self.flirTab.clean()
        #self.probeTrackingTab.clean()

