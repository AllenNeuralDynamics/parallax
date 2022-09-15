from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMenu, QMainWindow, QAction
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

from MessageLog import MessageLog
from ScreenWidget import ScreenWidget
from ControlPanel import ControlPanel
from TriangulationPanel import TriangulationPanel
from Dialogs import AboutDialog

import time


class MainWindow(QMainWindow):

    def __init__(self, model):
        QMainWindow.__init__(self)
        self.model = model

        self.widget = MainWidget(model)
        self.setCentralWidget(self.widget)

        # menubar actions
        self.saveFramesAction = QAction("Save Camera Frames")
        self.saveFramesAction.triggered.connect(self.widget.saveCameraFrames)
        self.saveFramesAction.setShortcut("Ctrl+F")
        self.saveCalAction = QAction("Save Calibration")
        self.saveCalAction.triggered.connect(self.widget.triPanel.save)
        self.saveCalAction.setShortcut("Ctrl+S")
        self.loadCalAction = QAction("Load Calibration")
        self.loadCalAction.triggered.connect(self.widget.triPanel.load)
        self.loadCalAction.setShortcut("Ctrl+O")
        self.editPrefsAction = QAction("Preferences")
        self.editPrefsAction.setEnabled(False)
        self.refreshCamerasAction = QAction("Refresh Camera List")
        self.refreshCamerasAction.triggered.connect(self.model.scanForCameras)
        self.refreshStagesAction = QAction("Refresh Stage List")
        self.refreshStagesAction.triggered.connect(self.model.scanForStages)
        self.aboutAction = QAction("About")
        self.aboutAction.triggered.connect(self.launchAbout)

        # build the menubar
        self.fileMenu = self.menuBar().addMenu("File")
        self.fileMenu.addAction(self.saveFramesAction)
        self.fileMenu.addSeparator()    # not visible on linuxmint?
        self.fileMenu.addAction(self.saveCalAction)
        self.fileMenu.addAction(self.loadCalAction)

        self.editMenu = self.menuBar().addMenu("Edit")
        self.editMenu.addAction(self.editPrefsAction)

        self.deviceMenu = self.menuBar().addMenu("Devices")
        self.deviceMenu.addAction(self.refreshCamerasAction)
        self.deviceMenu.addAction(self.refreshStagesAction)

        self.helpMenu = self.menuBar().addMenu("Help")
        self.helpMenu.addAction(self.aboutAction)

    def launchAbout(self):
        dlg = AboutDialog()
        dlg.exec_()


class MainWidget(QWidget):

    def __init__(self, model):
        QWidget.__init__(self) 
        self.model = model

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
        mainLayout.addWidget(self.screens)
        mainLayout.addWidget(self.controls)
        mainLayout.addWidget(self.msgLog)
        self.setLayout(mainLayout)

        self.setWindowTitle('MISGUIde')
        self.setWindowIcon(QIcon('../img/sextant.png'))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            if (e.modifiers() & Qt.ControlModifier):
                self.clearSelected()
                self.zoomOut()
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

