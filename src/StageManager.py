from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import socket

from Helper import *
from Stage import Stage
from Dialogs import *


class StageListItem(QListWidgetItem):

    def __init__(self, *args, **kwargs):
        QListWidgetItem.__init__(self, *args, **kwargs)

    def mousePressEvent(self, e):
        if (e.button() == Qt.LeftButton):
            print('stage item left')
        elif (e.button() == Qt.RightButton):
            print('stage item right')


class ScanStageWorker(QObject):
    finished = pyqtSignal()
    progressMade = pyqtSignal(str)

    def __init__(self, model, subnet, parent=None):
        QObject.__init__(self)
        self.model = model
        """
        subnet is a tuple: (byte1, byte2, byte3)
        """
        self.b1 = subnet[0]
        self.b2 = subnet[1]
        self.b3 = subnet[2]

    def run(self):
        self.model.initStages() # clear the dict
        socket.setdefaulttimeout(0.020)  # 20 ms timeout
        for i in range(1,256):
            ip = '%d.%d.%d.%d' % (self.b1, self.b2, self.b3, i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
                s.close()
            else:
                self.model.addStage(ip, Stage(s))
            self.progressMade.emit(ip)
        self.finished.emit()


class StageManager(QFrame):

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # widgets
        self.scanButton = QPushButton('Scan for Stages')
        self.scanButton.clicked.connect(self.scan)
        self.list = QListWidget()
        #self.list.setDragEnabled(True)

        # layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.scanButton)
        mainLayout.addWidget(self.list)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def scan(self):
        dlg = ScanStageDialog()
        if dlg.exec_():
            self.scanThread = QThread()
            self.scanWorker = ScanStageWorker(self.model, dlg.subnetWidget.getSubnet())
            self.scanWorker.moveToThread(self.scanThread)
            self.scanThread.started.connect(self.scanWorker.run)
            self.scanWorker.finished.connect(self.scanThread.quit)
            self.scanWorker.finished.connect(self.scanWorker.deleteLater)
            self.scanThread.finished.connect(self.scanThread.deleteLater)
            self.scanThread.finished.connect(self.handleScanFinished)
            self.scanWorker.progressMade.connect(self.reportProgress)
            self.scanThread.start()

    def scan_shortcut(self):
        ip = '10.128.49.22'
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
            s.close()
        else:
            self.model.addStage(ip, Stage(s))
            self.handleScanFinished()

    def handleScanFinished(self):
        for ip in self.model.stages.keys():
            QListWidgetItem(ip, self.list) # TODO use StageListItem?

    def reportProgress(self, ip):
        print('Scanning: ', ip)

