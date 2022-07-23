from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import PySpin

import socket
socket.setdefaulttimeout(0.020)  # 20 ms timeout

from Helper import *
from Stage import Stage
from Camera import Camera
from ScanStageDialog import ScanStageDialog
import State


class ScanWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, subnet, parent=None):
        QObject.__init__(self)
        """
        subnet is a tuple: (byte1, byte2, byte3)
        """
        self.b1 = subnet[0]
        self.b2 = subnet[1]
        self.b3 = subnet[2]

    def run(self):
        State.STAGES = []
        State.STAGES.append(Stage('10.128.49.7'))
        State.STAGES.append(Stage('10.128.49.8'))
        State.STAGES.append(Stage('10.128.49.9'))
        # TODO implement
        """
        for i in range(1,256):
            ip = '%d.%d.%d.%d' % (self.b1, self.b2, self.b3, i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
                s.close()
            else:
                State.STAGES.append(Stage(s))
            self.progress.emit(i)
        """
        self.finished.emit()


class CameraManager(QFrame):
    selected = pyqtSignal(object)

    def __init__(self):
        QFrame.__init__(self)

        # widgets
        self.scanButton = QPushButton('Scan for cameras')
        self.scanButton.clicked.connect(self.scan)
        self.table = QTableWidget()
        self.table.setRowCount(10)
        self.table.setColumnCount(3)

        self.table.setItem(0,0, QTableWidgetItem('Serial No.'))
        self.table.setItem(0,1, QTableWidgetItem('Status'))
        self.table.setItem(0,2, QTableWidgetItem('FW Version'))
        self.table.item(0,0).setFont(FONT_BOLD)
        self.table.item(0,1).setFont(FONT_BOLD)
        self.table.item(0,2).setFont(FONT_BOLD)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(100)
        self.table.setMaximumHeight(100)
        self.table.cellDoubleClicked.connect(self.handleDoubleClick)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.scanButton)
        mainLayout.addWidget(self.table)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def handleDoubleClick(self, row, col):
        stage = State.STAGES[row-1]
        self.selected.emit(stage)

    def scan(self):
        # quick init
        self.instance = PySpin.System.GetInstance()
        self.cameras_pyspin = self.instance.GetCameras()
        State.CAMERAS[0] = Camera(self.cameras_pyspin.GetByIndex(0))
        State.CAMERAS[1] = Camera(self.cameras_pyspin.GetByIndex(1))
        # TODO reimplement general scan
        """
        dlg = ScanStageDialog()
        if dlg.exec_():
            self.scanThread = QThread()
            self.scanWorker = ScanWorker(dlg.subnetWidget.getSubnet())
            self.scanWorker.moveToThread(self.scanThread)
            self.scanThread.started.connect(self.scanWorker.run)
            self.scanWorker.finished.connect(self.scanThread.quit)
            self.scanWorker.finished.connect(self.scanWorker.deleteLater)
            self.scanThread.finished.connect(self.scanThread.deleteLater)
            self.scanThread.finished.connect(self.handleScanFinished)
            self.scanWorker.progress.connect(self.reportProgress)
            self.scanThread.start()
        """

    def handleScanFinished(self):
        self.table.setRowCount(0)
        for i,stage in enumerate(State.STAGES):
            self.table.setItem(1+i, 0, QTableWidgetItem(stage.getIP()))
            self.table.setItem(1+i, 1, QTableWidgetItem("Online"))
            self.table.setItem(1+i, 2, QTableWidgetItem(stage.getFirmwareVersion()))

    def reportProgress(self, i):
        pass    # TODO show progress bar


