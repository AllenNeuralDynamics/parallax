from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import socket
socket.setdefaulttimeout(0.020)  # 20 ms timeout

from Helper import *
from Stage import Stage
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
        State.STAGES = {}
        for i in range(1,256):
            ip = '%d.%d.%d.%d' % (self.b1, self.b2, self.b3, i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
                s.close()
            else:
                State.STAGES[ip] = Stage(s)
            self.progress.emit(i)
        self.finished.emit()


class StageItem(QListWidgetItem):

    def __init__(self, *args, **kwargs):
        QListWidgetItem.__init__(self, *args, **kwargs)

    def mousePressEvent(self, e):
        print('uh')
        if (e.button() == Qt.LeftButton):
            print('stage item left')
        elif (e.button() == Qt.RightButton):
            print('stage item right')


class StageManager(QFrame):

    def __init__(self):
        QFrame.__init__(self)

        # widgets
        self.scanButton = QPushButton('Scan for stages')
        self.scanButton.clicked.connect(self.scan)
        self.list = QListWidget()
        self.list.setDragEnabled(True)

        # layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.scanButton)
        mainLayout.addWidget(self.list)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def scan(self):
        # shortcut
        ip = '10.128.49.22'
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
            s.close()
        else:
            State.STAGES[ip] = Stage(s)
            self.handleScanFinished()
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
        for ip in State.STAGES.keys():
            QListWidgetItem(ip, self.list)

    def reportProgress(self, i):
        print(i)

class StageManager_old(QFrame):
    selected = pyqtSignal(object)

    def __init__(self):
        QFrame.__init__(self)

        # widgets
        self.scanButton = QPushButton('Scan for stages')
        self.scanButton.clicked.connect(self.scan)
        self.table = QTableWidget()
        #self.table = DragTableWidget()
        self.buildTable()

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

    def buildTable(self):
        self.table.setRowCount(10)
        self.table.setColumnCount(3)

        self.table.setItem(0,0, QTableWidgetItem('IP'))
        self.table.setItem(0,1, QTableWidgetItem('Status'))
        self.table.setItem(0,2, QTableWidgetItem('FW Version'))
        self.table.item(0,0).setFont(FONT_BOLD)
        self.table.item(0,1).setFont(FONT_BOLD)
        self.table.item(0,2).setFont(FONT_BOLD)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(100)
        self.table.setMaximumHeight(100)
        self.table.cellDoubleClicked.connect(self.handleDoubleClick)

    def handleDoubleClick(self, row, col):
        stage = State.STAGES[row-1]
        self.selected.emit(stage)

    def scan(self):
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

    def handleScanFinished(self):
        self.buildTable()
        for i,stage in enumerate(State.STAGES):
            self.table.setItem(1+i, 0, DragTableWidgetItem(stage.getIP()))
            self.table.setItem(1+i, 1, QTableWidgetItem("Online"))
            self.table.setItem(1+i, 2, QTableWidgetItem(stage.getFirmwareVersion()))

    def reportProgress(self, i):
        print(i)


